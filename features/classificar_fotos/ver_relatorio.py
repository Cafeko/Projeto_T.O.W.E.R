"""Ver relatório — janela para navegar nas fotos classificadas.

Mostra as classes do relatório (com contadores), as fotos de cada classe
em ordem e a prévia com zoom. Para copiar no tamanho do Excel, abre a
classe direto no fit_fotos.

Uso:
    python features/classificar_fotos/ver_relatorio.py --relatorio gna_fonte

Rode sempre a partir da RAIZ do projeto.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk

from PIL import Image, ImageTk

try:
    from .classificar_fotos import (
        BASE_CLASSIFICADAS,
        NOME_CSV,
        PASTA_FOTOS_REL,
        PASTA_ORIGEM_PADRAO,
        chave_natural,
        listar_fotos,
    )
    from .modo_treino import enquadrar_zoom, listar_relatorios
    from .modo_treino import (
        NAO_IDENTIFICADO,
        atualizar_classificacao,
        registrar_exemplo,
        todas_classes,
    )
except ImportError:  # chamado como script direto
    from classificar_fotos import (
        BASE_CLASSIFICADAS,
        NOME_CSV,
        PASTA_FOTOS_REL,
        PASTA_ORIGEM_PADRAO,
        chave_natural,
        listar_fotos,
    )
    from modo_treino import enquadrar_zoom, listar_relatorios
    from modo_treino import (
        NAO_IDENTIFICADO,
        atualizar_classificacao,
        classes_salvas,
        registrar_exemplo,
        todas_classes,
    )

import sys as _sys
_sys.path.insert(0, str((Path(__file__).resolve().parents[1] / "fit_fotos")))
try:
    from fit_fotos import (
        DPI_PADRAO,
        calcular_dpi,
        converter_tamanho,
        copiar_para_clipboard,
        enviar_para_excel,
        pedido_para_cm,
        redimensionar,
        salvar_copia,
    )
except ImportError:  # fit_fotos ausente: cópia desabilitada
    DPI_PADRAO = 96
    calcular_dpi = converter_tamanho = copiar_para_clipboard = None
    enviar_para_excel = pedido_para_cm = redimensionar = salvar_copia = None

RAIZ_PROJETO = Path(__file__).resolve().parents[2]


# ============================================================
# Lógica pura (sem GUI — testável)
# ============================================================

def carregar_relatorio(relatorio: str,
                       base: Path | str | None = None) -> dict:
    """Lê o estado atual do relatório: fotos, classes e contadores.

    Fotos vêm de <relatorio>/fotos/ (ou Fotos_Ordenadas se ainda não
    preparado); classes do classificacao.csv (validadas até agora).
    """
    import csv as _csv

    base_p = Path(base) if base else BASE_CLASSIFICADAS
    try:
        from classificar_fotos import sanitizar_nome as _sn
    except ImportError:
        from .classificar_fotos import sanitizar_nome as _sn
    pasta_rel = base_p / _sn(relatorio)
    fotos_dir = pasta_rel / PASTA_FOTOS_REL
    if not (fotos_dir.is_dir() and listar_fotos(fotos_dir)):
        fotos_dir = PASTA_ORIGEM_PADRAO
    fotos = listar_fotos(fotos_dir)

    salvas: dict[str, list[str]] = {}
    csv_path = pasta_rel / NOME_CSV
    if csv_path.is_file():
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            for row in _csv.DictReader(f):
                arq = (row.get("Arquivo") or "").strip()
                if not arq:
                    continue
                bruto = (row.get("Classes") or "").strip()
                salvas[arq] = [c.strip() for c in bruto.replace("|", ";").split(";")
                               if c.strip()]
    cont: dict[str, int] = {}
    aguard = 0
    linhas = []
    for i, foto in enumerate(fotos, start=1):
        cls = salvas.get(foto.name, [])
        linhas.append({"arquivo": foto.name, "ordem": i, "classes": cls,
                       "caminho": foto})
        if cls:
            for c in cls:
                cont[c] = cont.get(c, 0) + 1
        else:
            aguard += 1
    return {"relatorio": relatorio, "pasta": pasta_rel, "fotos_dir": fotos_dir,
            "fotos": linhas, "classes": sorted(cont),
            "contadores": cont, "aguardando": aguard}


# ============================================================
# Janela gráfica
# ============================================================

class VerApp(tk.Tk):
    def __init__(self, relatorio_inicial: str = ""):
        super().__init__()
        self.title("ver relatório — fotos por classe")
        self.geometry("1000x700")
        self.minsize(880, 600)
        self.dados: dict | None = None
        self.visiveis: list[int] = []
        self.img_original = None
        self.zoom_z = 1.0
        self.zoom_ox = 0
        self.zoom_oy = 0
        self.mostrar_chave = "todas"
        self.check_vars: dict = {}
        self.preview_ref = None
        self._montar()
        self.rel_box.config(values=listar_relatorios(BASE_CLASSIFICADAS))
        if relatorio_inicial:
            self.rel_var.set(relatorio_inicial)
        elif listar_relatorios(BASE_CLASSIFICADAS):
            self.rel_var.set(listar_relatorios(BASE_CLASSIFICADAS)[0])
        if self.rel_var.get().strip():
            self.carregar()
        else:
            self.status("Selecione o relatório e pressione Carregar.")

    def _montar(self):
        self.rel_var = tk.StringVar()
        self.mostrar_var = tk.StringVar(value="Todas")
        self.zoom_var = tk.StringVar(value="100%")
        self.info_var = tk.StringVar(value="Nenhum relatório.")
        self.status_var = tk.StringVar(value="Pronto.")
        self.larg_var = tk.StringVar(value="6")
        self.alt_var = tk.StringVar(value="4")
        self.unidade_var = tk.StringVar(value="cm")
        self.dpi_var = tk.StringVar(value=str(DPI_PADRAO))
        self.proporcao_var = tk.BooleanVar(value=True)
        self.alta_var = tk.BooleanVar(value=True)
        self.destino_var = tk.StringVar(
            value=str(RAIZ_PROJETO / "Arquivos" / "Fotos_Fit"))
        self.px_var = tk.StringVar(value="")

        topo = ttk.Frame(self, padding=8)
        topo.pack(fill="x")
        ttk.Label(topo, text="Relatório:").pack(side="left")
        self.rel_box = ttk.Combobox(topo, textvariable=self.rel_var,
                                    width=34, values=[])
        self.rel_box.pack(side="left", padx=4)
        ttk.Button(topo, text="Carregar", command=self.carregar).pack(side="left", padx=2)

        meio = ttk.Frame(self, padding=(8, 0, 8, 8))
        meio.pack(fill="both", expand=True)

        esq = ttk.Frame(meio)
        esq.pack(side="left", fill="y")
        ttk.Label(esq, text="Classes:").pack(anchor="w")
        self.lista_classes = tk.Listbox(esq, width=26, height=6)
        self.lista_classes.pack(fill="x")
        self.lista_classes.bind("<<ListboxSelect>>", self._ao_trocar_classe)
        ttk.Label(esq, text="Fotos (← → navega):").pack(anchor="w", pady=(6, 0))
        self.lista = tk.Listbox(esq, width=38, height=14)
        self.lista.pack(side="left", fill="y")
        self.lista.bind("<<ListboxSelect>>", self._ao_selecionar)
        rol = ttk.Scrollbar(esq, command=self.lista.yview)
        rol.pack(side="left", fill="y")
        self.lista.config(yscrollcommand=rol.set)

        centro = ttk.Frame(meio, padding=(12, 0, 0, 0))
        centro.pack(side="left", fill="both", expand=True)
        self.preview = ttk.Label(centro, text="(nenhuma foto)", anchor="center",
                                 relief="sunken", width=58)
        self.preview.pack(fill="both", expand=True)
        ttk.Label(centro, textvariable=self.info_var, wraplength=520,
                  anchor="w").pack(pady=2, fill="x")
        zoom_bar = ttk.Frame(centro)
        zoom_bar.pack(pady=(0, 2))
        ttk.Label(zoom_bar, text="Zoom:").pack(side="left")
        ttk.Button(zoom_bar, text="−", width=3,
                   command=lambda: self.zoom_por(1 / 1.25)).pack(side="left", padx=2)
        ttk.Label(zoom_bar, textvariable=self.zoom_var, width=6,
                  anchor="center").pack(side="left")
        ttk.Button(zoom_bar, text="+", width=3,
                   command=lambda: self.zoom_por(1.25)).pack(side="left", padx=2)
        ttk.Button(zoom_bar, text="Ajustar",
                   command=self.zoom_ajustar).pack(side="left", padx=2)
        ttk.Button(zoom_bar, text="1:1",
                   command=self.zoom_um_para_um).pack(side="left", padx=2)
        tam = ttk.LabelFrame(centro, text="Tamanho p/ Excel", padding=6)
        tam.pack(pady=(2, 0))
        ttk.Label(tam, text="L:").pack(side="left")
        ttk.Entry(tam, textvariable=self.larg_var, width=6).pack(side="left", padx=2)
        ttk.Label(tam, text="A:").pack(side="left")
        ttk.Entry(tam, textvariable=self.alt_var, width=6).pack(side="left", padx=2)
        ttk.Radiobutton(tam, text="cm", variable=self.unidade_var,
                        value="cm", command=self.atualizar_px).pack(side="left")
        ttk.Radiobutton(tam, text="px", variable=self.unidade_var,
                        value="px", command=self.atualizar_px).pack(side="left")
        ttk.Checkbutton(tam, text="Proporção", variable=self.proporcao_var,
                        command=self.atualizar_px).pack(side="left", padx=4)
        ttk.Checkbutton(tam, text="Alta", variable=self.alta_var,
                        command=self.atualizar_px).pack(side="left")
        ttk.Label(tam, textvariable=self.px_var, foreground="gray").pack(side="left", padx=4)
        for v in (self.larg_var, self.alt_var):
            v.trace_add("write", lambda *a: self.atualizar_px())

        base = ttk.Frame(self, padding=8)
        base.pack(fill="x")
        ttk.Label(base, text="Salvar em:").pack(side="left")
        ttk.Entry(base, textvariable=self.destino_var, width=30).pack(side="left", padx=4)
        ttk.Button(base, text="Copiar foto (Ctrl+C)",
                   command=self.copiar_selecionada).pack(side="left", padx=4)
        ttk.Button(base, text="Enviar p/ Excel (Ctrl+E)",
                   command=self.enviar_selecionada).pack(side="left", padx=2)
        ttk.Button(base, text="Salvar visíveis",
                   command=self.salvar_visiveis).pack(side="left", padx=2)
        ttk.Button(base, text="Corrigir (F2)",
                   command=self.abrir_correcao).pack(side="left", padx=2)
        ttk.Label(self, textvariable=self.status_var, relief="sunken",
                  anchor="w").pack(fill="x", side="bottom")
        self.bind("<Left>", lambda e: self.mover(-1, e))
        self.bind("<Right>", lambda e: self.mover(1, e))
        self.bind("<Control-c>", lambda e: self.copiar_selecionada())
        self.bind("<Control-e>", lambda e: self.enviar_selecionada())
        self.bind("<F2>", lambda e: self.abrir_correcao())
        self.preview.bind("<MouseWheel>", self.zoom_girar)
        self.preview.bind("<ButtonPress-1>", self.zoom_iniciar_arrasto)
        self.preview.bind("<B1-Motion>", self.zoom_arrastar)
        self.preview.bind("<Configure>", lambda _e: self.render_preview())

    # ---------- dados ----------

    def relatorio(self) -> str:
        return self.rel_var.get().strip()

    def carregar(self):
        rel = self.relatorio()
        if not rel:
            messagebox.showinfo("Informe o relatório", "Selecione o relatório.")
            return
        self.dados = carregar_relatorio(rel, BASE_CLASSIFICADAS)
        self.lista_classes.delete(0, "end")
        self.lista_classes.insert("end",
                                  f"Todas ({len(self.dados['fotos'])})")
        self.lista_classes.insert("end",
                                  f"Não classificadas ({self.dados['aguardando']})")
        for c in self.dados["classes"]:
            self.lista_classes.insert("end", f"{c} ({self.dados['contadores'][c]})")
        self.lista_classes.selection_set(0)
        self.mostrar_chave = "todas"
        self._atualizar_fotos()
        if self.visiveis:
            self.lista.selection_set(0)
            self._mostrar(0)
        self.status(f"Relatório '{rel}': {len(self.dados['fotos'])} fotos, "
                    f"{len(self.dados['classes'])} classes, "
                    f"{self.dados['aguardando']} aguardando.")

    def _ao_trocar_classe(self, _evt=None):
        sel = self.lista_classes.curselection()
        if not sel or not self.dados:
            return
        txt = self.lista_classes.get(sel[0])
        if txt.startswith("Não classificadas"):
            self.mostrar_chave = "aguardando"
        elif txt.startswith("Todas"):
            self.mostrar_chave = "todas"
        else:
            self.mostrar_chave = ("classe", txt.rsplit(" (", 1)[0])
        self._atualizar_fotos()
        if self.visiveis:
            self.lista.selection_set(0)
            self._mostrar(0)

    def _atualizar_fotos(self):
        assert self.dados is not None
        self.visiveis = []
        for i, f in enumerate(self.dados["fotos"]):
            if self.mostrar_chave == "todas":
                self.visiveis.append(i)
            elif self.mostrar_chave == "aguardando":
                if not f["classes"]:
                    self.visiveis.append(i)
            elif isinstance(self.mostrar_chave, tuple) and self.mostrar_chave[1] in f["classes"]:
                self.visiveis.append(i)
        self.lista.delete(0, "end")
        for i in self.visiveis:
            f = self.dados["fotos"][i]
            suf = f"  ✓ {'; '.join(f['classes'])}" if f["classes"] else ""
            self.lista.insert("end", f"Foto ({f['ordem']}) — {f['arquivo']}{suf}")

    # ---------- navegação ----------

    def _ao_selecionar(self, _evt=None):
        sel = self.lista.curselection()
        if sel:
            self._mostrar(sel[0])

    def mover(self, delta: int, evento=None):
        if evento is not None and isinstance(evento.widget, (tk.Entry, ttk.Entry, tk.Text)):
            return None
        if not self.visiveis:
            return None
        sel = self.lista.curselection()
        idx = sel[0] if sel else (0 if delta > 0 else len(self.visiveis) - 1)
        novo = min(max(idx + delta, 0), len(self.visiveis) - 1)
        self.lista.selection_clear(0, "end")
        self.lista.selection_set(novo)
        self.lista.see(novo)
        self.lista.xview_moveto(0)
        self._mostrar(novo)
        return "break"

    def _mostrar(self, pos: int):
        assert self.dados is not None
        if not self.visiveis:
            return
        pos = min(max(pos, 0), len(self.visiveis) - 1)
        f = self.dados["fotos"][self.visiveis[pos]]
        try:
            img = Image.open(f["caminho"])
            img.load()
        except Exception as e:
            self.info_var.set(f"Erro ao abrir {f['arquivo']}: {e}")
            return
        self.img_original = img
        self.zoom_z, self.zoom_ox, self.zoom_oy = 1.0, 0, 0
        self.render_preview()
        cls_txt = "; ".join(f["classes"]) if f["classes"] else "aguardando"
        self.info_var.set(f"Foto ({f['ordem']}) — {f['arquivo']} — "
                          f"{img.size[0]}x{img.size[1]} px — {cls_txt}")

    # ---------- correção da foto atual (popup) ----------

    def foto_exibida(self):
        if not self.dados or not self.visiveis:
            return None
        sel = self.lista.curselection()
        pos = sel[0] if sel else 0
        return self.dados["fotos"][self.visiveis[min(pos, len(self.visiveis) - 1)]]

    def abrir_correcao(self):
        f = self.foto_exibida()
        if f is None:
            return
        pop = tk.Toplevel(self)
        pop.title(f"Corrigir — {f['arquivo']}")
        pop.geometry("460x420")
        pop.transient(self)
        ttk.Label(pop, text=f"Foto ({f['ordem']}) — marque N classes:",
                  padding=(8, 8, 8, 0)).pack(anchor="w")
        rol = ttk.Scrollbar(pop, orient="vertical")
        rol.pack(side="right", fill="y")
        canvas = tk.Canvas(pop, highlightthickness=0, yscrollcommand=rol.set)
        canvas.pack(side="left", fill="both", expand=True)
        rol.config(command=canvas.yview)
        area = ttk.Frame(canvas)
        jan = canvas.create_window((0, 0), window=area, anchor="nw")
        area.bind("<Configure>", lambda _e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(jan, width=e.width))
        base = set(f["classes"])
        vars_popup: dict = {}
        for i, cls in enumerate(todas_classes(BASE_CLASSIFICADAS)):
            var = tk.BooleanVar(value=(cls in base))
            vars_popup[cls] = var
            ttk.Checkbutton(area, text=cls, variable=var).grid(
                row=i // 2, column=i % 2, sticky="w", padx=8, pady=2)
        for _c in range(2):
            area.columnconfigure(_c, weight=1, uniform="pop")
        botoes = ttk.Frame(pop, padding=8)
        botoes.pack(fill="x")
        ttk.Button(botoes, text="Salvar correção",
                   command=lambda: self._salvar_popup(pop, vars_popup, f)).pack(side="left", padx=4)
        ttk.Button(botoes, text="Não identificado",
                   command=lambda: self._salvar_popup(
                       pop, vars_popup, f, so_nao_identificado=True)).pack(side="left", padx=4)
        ttk.Button(botoes, text="Cancelar",
                   command=pop.destroy).pack(side="right", padx=4)
        pop.grab_set()
        pop.focus_set()

    def _salvar_popup(self, pop, vars_popup: dict, f: dict,
                      so_nao_identificado: bool = False):
        if so_nao_identificado:
            classes = [NAO_IDENTIFICADO]
        else:
            classes = [c for c, v in vars_popup.items() if v.get()] or [NAO_IDENTIFICADO]
        registrar_exemplo(f["arquivo"], str(self.dados["fotos_dir"]),
                          self.relatorio(), classes, f["classes"], False, "",
                          BASE_CLASSIFICADAS)
        atualizar_classificacao(self.relatorio(), f["arquivo"], classes, "",
                                BASE_CLASSIFICADAS)
        self.status(f"{f['arquivo']} corrigida → [{'; '.join(classes)}].")
        pop.destroy()
        self._recarregar_dados(f["arquivo"])

    def _recarregar_dados(self, manter_nome: str | None = None):
        """Recarrega CSV/contadores mantendo a posição (pós-correção)."""
        rel = self.relatorio()
        self.dados = carregar_relatorio(rel, BASE_CLASSIFICADAS)
        self.lista_classes.delete(0, "end")
        self.lista_classes.insert("end", f"Todas ({len(self.dados['fotos'])})")
        self.lista_classes.insert("end",
                                  f"Não classificadas ({self.dados['aguardando']})")
        for c in self.dados["classes"]:
            self.lista_classes.insert("end", f"{c} ({self.dados['contadores'][c]})")
        self.visiveis = []
        for i, f in enumerate(self.dados["fotos"]):
            if self.mostrar_chave == "todas":
                self.visiveis.append(i)
            elif self.mostrar_chave == "aguardando":
                if not f["classes"]:
                    self.visiveis.append(i)
            elif isinstance(self.mostrar_chave, tuple) and self.mostrar_chave[1] in f["classes"]:
                self.visiveis.append(i)
        self.lista.delete(0, "end")
        for i in self.visiveis:
            f = self.dados["fotos"][i]
            suf = f"  ✓ {'; '.join(f['classes'])}" if f["classes"] else ""
            self.lista.insert("end", f"Foto ({f['ordem']}) — {f['arquivo']}{suf}")
        pos = 0
        if manter_nome:
            for p, i in enumerate(self.visiveis):
                if self.dados["fotos"][i]["arquivo"] == manter_nome:
                    pos = p
                    break
        if self.visiveis:
            self.lista.selection_clear(0, "end")
            self.lista.selection_set(pos)
            self.lista.see(pos)
            self.lista.xview_moveto(0)
            self._mostrar(pos)

    # ---------- zoom ----------

    def caixa_zoom(self) -> tuple:
        try:
            larg = self.preview.winfo_width()
            alt = self.preview.winfo_height()
        except Exception:
            larg, alt = 520, 340
        return min(520, max(200, larg)), min(340, max(200, alt))

    def render_preview(self):
        if self.img_original is None:
            return
        larg, alt = self.caixa_zoom()
        vista, _b = enquadrar_zoom(self.img_original, larg, alt,
                                   self.zoom_z, self.zoom_ox, self.zoom_oy)
        self.preview_ref = ImageTk.PhotoImage(vista)
        self.preview.config(image=self.preview_ref, text="")
        self.zoom_var.set(f"{int(round(self.zoom_z * 100))}%")

    def zoom_por(self, fator: float):
        if self.img_original is None:
            return
        larg, alt = self.caixa_zoom()
        z_antes = self.zoom_z
        z_novo = min(8.0, max(0.2, z_antes * fator))
        if z_novo == z_antes:
            return
        ow, oh = self.img_original.size
        f = min(larg / ow, alt / oh)
        ant_larg, ant_alt = max(1, int(ow * f * z_antes)), max(1, int(oh * f * z_antes))
        nova_larg, nova_alt = max(1, int(ow * f * z_novo)), max(1, int(oh * f * z_novo))
        cx = (self.zoom_ox + min(ant_larg, larg) / 2) / ant_larg
        cy = (self.zoom_oy + min(ant_alt, alt) / 2) / ant_alt
        self.zoom_z = z_novo
        self.zoom_ox = int(nova_larg * cx - larg / 2)
        self.zoom_oy = int(nova_alt * cy - alt / 2)
        self.render_preview()

    def zoom_ajustar(self):
        if self.img_original is None:
            return
        self.zoom_z, self.zoom_ox, self.zoom_oy = 1.0, 0, 0
        self.render_preview()

    def zoom_um_para_um(self):
        if self.img_original is None:
            return
        larg, alt = self.caixa_zoom()
        ow, oh = self.img_original.size
        f = min(larg / ow, alt / oh) or 1.0
        self.zoom_z = min(8.0, max(0.2, 1.0 / f))
        ow_s, oh_s = max(1, int(ow * f * self.zoom_z)), max(1, int(oh * f * self.zoom_z))
        self.zoom_ox, self.zoom_oy = max(0, (ow_s - larg) // 2), max(0, (oh_s - alt) // 2)
        self.render_preview()

    def zoom_girar(self, evento):
        if self.img_original is None:
            return None
        self.zoom_por(1.25 if evento.delta > 0 else 1 / 1.25)
        return "break"

    def zoom_iniciar_arrasto(self, evento):
        self._arrasto = (evento.x, evento.y, self.zoom_ox, self.zoom_oy)

    def zoom_arrastar(self, evento):
        if self.img_original is None or not hasattr(self, "_arrasto"):
            return None
        x0, y0, ox, oy = self._arrasto
        self.zoom_ox, self.zoom_oy = ox - (evento.x - x0), oy - (evento.y - y0)
        self.render_preview()
        return "break"

    # ---------- ações ----------

    # ---------- tamanho + cópia (igual ao fit_fotos) ----------

    def sem_copia(self) -> bool:
        if copiar_para_clipboard is None:
            messagebox.showinfo("Sem cópia", "fit_fotos não encontrado — só visualização.")
            return True
        return False

    def ler_pedido(self):
        try:
            larg = float(self.larg_var.get().replace(",", "."))
            alt = float(self.alt_var.get().replace(",", "."))
            if larg <= 0 or alt <= 0:
                raise ValueError
            unidade = self.unidade_var.get()
            dpi = int(self.dpi_var.get()) if unidade == "cm" else DPI_PADRAO
            if dpi <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Tamanho inválido",
                                   "Digite largura e altura maiores que zero.")
            return None
        return larg, alt, unidade, dpi

    def atualizar_px(self):
        if converter_tamanho is None:
            return
        try:
            larg = float(self.larg_var.get().replace(",", "."))
            alt = float(self.alt_var.get().replace(",", "."))
            unidade = self.unidade_var.get()
            if self.alta_var.get() and self.img_original is not None:
                ow, oh = self.img_original.size
                lw, lh = pedido_para_cm(larg, alt, unidade, DPI_PADRAO)
                (dx, _dy), (dw, dh) = calcular_dpi(ow, oh, lw, lh,
                                                   self.proporcao_var.get())
                self.px_var.set(f"= exibe {dw:.1f}x{dh:.1f} cm (DPI {dx:.0f})")
                return
            w, h = converter_tamanho(larg, alt, unidade, DPI_PADRAO)
            self.px_var.set(f"= {w}x{h} px")
        except ValueError:
            self.px_var.set("")

    def foto_atual(self):
        if not self.visiveis:
            return None
        sel = self.lista.curselection()
        pos = sel[0] if sel else 0
        pos = min(pos, len(self.visiveis) - 1)
        assert self.dados is not None
        return self.dados["fotos"][self.visiveis[pos]]

    def copiar_selecionada(self):
        if self.sem_copia():
            return
        if self.img_original is None:
            messagebox.showinfo("Nada a copiar", "Selecione uma foto.")
            return
        pedido = self.ler_pedido()
        if pedido is None:
            return
        larg, alt, unidade, dpi_base = pedido
        try:
            if self.alta_var.get():
                ow, oh = self.img_original.size
                lw, lh = pedido_para_cm(larg, alt, unidade, dpi_base)
                (dx, dy), (dw, dh) = calcular_dpi(ow, oh, lw, lh,
                                                  self.proporcao_var.get())
                copiar_para_clipboard(
                    self.img_original, dpi=(dx, dy), tamanho_emf_cm=(dw, dh))
                f = self.foto_atual()
                nome = f["arquivo"] if f else "foto"
                self.status(f"{nome} copiada em alta — cole no Excel com Ctrl+V.")
            else:
                w, h = converter_tamanho(larg, alt, unidade, dpi_base)
                final = redimensionar(self.img_original, w, h,
                                      self.proporcao_var.get())
                copiar_para_clipboard(final)
                self.status("Foto copiada — cole no Excel com Ctrl+V.")
        except Exception as e:
            messagebox.showerror("Erro ao copiar", str(e))

    def enviar_selecionada(self):
        if self.sem_copia():
            return
        if self.img_original is None:
            messagebox.showinfo("Nada a enviar", "Selecione uma foto.")
            return
        pedido = self.ler_pedido()
        if pedido is None:
            return
        larg, alt, unidade, dpi_base = pedido
        lw, lh = pedido_para_cm(larg, alt, unidade, dpi_base)
        _dpi, (dw, dh) = calcular_dpi(*self.img_original.size, lw, lh,
                                      self.proporcao_var.get())
        try:
            onde = enviar_para_excel(self.img_original, dw, dh)
        except Exception as e:
            messagebox.showerror("Erro ao enviar", str(e))
            return
        self.status(f"Foto inserida no Excel ({dw:.1f}x{dh:.1f} cm) em {onde}.")

    def salvar_visiveis(self):
        if self.sem_copia() or not self.dados or not self.visiveis:
            return
        pedido = self.ler_pedido()
        if pedido is None:
            return
        larg, alt, unidade, dpi_base = pedido
        alta = self.alta_var.get()
        destino = Path(self.destino_var.get().strip())
        if not destino.is_absolute():
            destino = RAIZ_PROJETO / destino
        ok, erros = 0, 0
        from PIL import Image as _Img
        for i in self.visiveis:
            f = self.dados["fotos"][i]
            try:
                with _Img.open(f["caminho"]) as img:
                    img.load()
                    if alta:
                        lw, lh = pedido_para_cm(larg, alt, unidade, dpi_base)
                        (dx, dy), _ex = calcular_dpi(*img.size, lw, lh,
                                                     self.proporcao_var.get())
                        salvar_copia(img, destino / f["arquivo"], dpi=(dx, dy))
                    else:
                        w, h = converter_tamanho(larg, alt, unidade, dpi_base)
                        salvar_copia(redimensionar(img, w, h,
                                                   self.proporcao_var.get()),
                                     destino / f["arquivo"])
                ok += 1
            except Exception:
                erros += 1
        self.status(f"Salvas {ok} fotos em '{destino}'" + (f" ({erros} erros)." if erros else "."))

    def status(self, texto: str):
        self.status_var.set(texto)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(
        description="Ver relatório: navegue nas fotos por classe (com zoom). "
                    "Copia p/ Excel pelo fit_fotos.")
    ap.add_argument("--relatorio", default="",
                    help="relatório (ex: gna_fonte)")
    args = ap.parse_args(argv)
    app = VerApp(relatorio_inicial=(args.relatorio or "").strip())
    app.mainloop()


if __name__ == "__main__":
    main()
