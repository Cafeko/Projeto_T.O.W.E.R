"""Avaliar relatório — janela para validar/corrigir atividade+etapa foto a foto.

Mesmo espírito do modo_treino, mas para o modelo montar_relatorio:
- uma foto pode ter N vínculos (atividade+etapa) — ex: 02/durante + 03/depois;
- modo foto única e modo miniaturas usam a MESMA ordem (por grupo);
- na grade, 1 clique seleciona e edita no painel, 2 cliques abre grande;
- voltar para a grade revela a foto onde estava (não volta ao topo);
- salva no evidencia.csv do relatório (pronto p/ distribuir);
- botão Distribuir roda o montar_relatorio.py sem sair da janela
  (marque "só boas" p/ pastas finais do relatório).

Uso:
    python features/montar_relatorio/avaliar_relatorio.py --relatorio gna

Rode sempre a partir da RAIZ do projeto.
"""

from __future__ import annotations

import argparse
import csv
import sys as _sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

_sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fit_fotos"))
try:
    import fit_fotos as FF
except ImportError:
    FF = None

try:
    from .montar_relatorio import (
        ATIVIDADE_SITE,
        BASE_RELATORIOS,
        CABECALHO_CSV,
        ETAPAS,
        NOME_ESCOPO,
        NOME_EVIDENCIA,
        NOME_VIEWER,
        PASTA_FOTOS,
        QUALIDADES,
        carregar_escopo,
        distribuir,
        pares_evidencia,
        pasta_relatorio,
        resolver_origem,
        tem_vinculo,
    )
except ImportError:  # chamado como script direto
    from montar_relatorio import (
        ATIVIDADE_SITE,
        BASE_RELATORIOS,
        CABECALHO_CSV,
        ETAPAS,
        NOME_ESCOPO,
        NOME_EVIDENCIA,
        NOME_VIEWER,
        PASTA_FOTOS,
        QUALIDADES,
        carregar_escopo,
        distribuir,
        pares_evidencia,
        pasta_relatorio,
        resolver_origem,
        tem_vinculo,
    )

ETAPA_NENHUMA = "Não identificada"
CONFIANCAS = ("alta", "media", "baixa")


# ============================================================
# Lógica pura (sem GUI)
# ============================================================

def listar_relatorios(base: Path | str | None = None) -> list[str]:
    base = Path(base) if base else BASE_RELATORIOS
    if not base.is_dir():
        return []
    rels = [p.name for p in base.iterdir()
            if p.is_dir() and (p / NOME_EVIDENCIA).exists()]
    return sorted(rels)


def carregar_linhas(pasta_rel: Path) -> list[dict]:
    """Lê evidencia.csv como lista de dicts (ordem do arquivo)."""
    csv_path = pasta_rel / NOME_EVIDENCIA
    linhas: list[dict] = []
    if not csv_path.exists():
        return linhas
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if not (row.get("Arquivo") or "").strip():
                continue
            linhas.append({k: (row.get(k) or "") for k in CABECALHO_CSV})
    return linhas


def salvar_linhas(pasta_rel: Path, linhas: list[dict]) -> None:
    csv_path = pasta_rel / NOME_EVIDENCIA
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CABECALHO_CSV)
        w.writeheader()
        for item in linhas:
            w.writerow({k: item.get(k, "") for k in CABECALHO_CSV})


def opcoes_atividade(escopo: dict | None) -> list[tuple[str, str]]:
    """[(id, 'id — titulo')]. Sem opção vazia: não identificado = sem vínculo
    (botão Limpar). SITE = fotos do site."""
    ops = [(ATIVIDADE_SITE, f"{ATIVIDADE_SITE} — Fotos do site")]
    if not escopo:
        return ops
    for ativ in escopo.get("atividades", []):
        aid = str(ativ.get("id") or "").strip()
        if aid and aid.upper() != ATIVIDADE_SITE:
            ops.append((aid, f"{aid} — {ativ.get('titulo', '')}"))
    return ops


def rotulo_atividade(ops: list[tuple[str, str]], aid: str) -> str:
    return next((t for i, t in ops if i == aid), ETAPA_NENHUMA)


# ============================================================
# GUI
# ============================================================

class Avaliador(tk.Tk):
    def __init__(self, relatorio: str | None = None):
        super().__init__()
        self.title("Avaliar relatório — atividade + etapa")
        self.geometry("1200x760")

        self.pasta_rel: Path | None = None
        self.origem: Path | None = None
        self.linhas: list[dict] = []
        self.visiveis: list[int] = []  # após filtro (ordem do CSV)
        self.grupos: list[tuple[str, str, str, list[int]]] = []
        self.ordem: list[int] = []  # ordem de exibição (grupos) — vale p/ os 2 modos
        self.pos = 0
        self.ops: list[tuple[str, str]] = [(ATIVIDADE_SITE, "SITE")]
        self.vincs: list[tuple[str, str]] = []  # vínculos da foto atual
        self.foto_img: Image.Image | None = None
        self.zoom = 0.0  # 0 = ajustar; >0 = escala
        self._tk_img = None

        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)
        ttk.Label(top, text="Relatório:").pack(side="left")
        self.cb_rel = ttk.Combobox(top, values=listar_relatorios(),
                                   state="readonly", width=40)
        self.cb_rel.pack(side="left", padx=6)
        self.cb_rel.bind("<<ComboboxSelected>>", lambda _e: self.trocar_relatorio())
        ttk.Label(top, text="Mostrar:").pack(side="left", padx=(12, 0))
        self.cb_filtro = ttk.Combobox(top, state="readonly", width=28)
        self.cb_filtro.pack(side="left", padx=6)
        self.cb_filtro.bind("<<ComboboxSelected>>", lambda _e: self.aplicar_filtro())
        self.btn_foto = ttk.Button(top, text="Foto única",
                                   command=lambda: self._modo("foto"))
        self.btn_foto.pack(side="left", padx=(12, 0))
        self.btn_grade = ttk.Button(top, text="Miniaturas",
                                    command=lambda: self._modo("grade"))
        self.btn_grade.pack(side="left", padx=4)
        self.uso = "avaliar"  # avaliar | copiar
        self.btn_uso_aval = ttk.Button(top, text="Avaliar",
                                       command=lambda: self._uso("avaliar"))
        self.btn_uso_aval.pack(side="left", padx=(12, 0))
        self.btn_uso_cop = ttk.Button(top, text="Copiar p/ Excel",
                                      command=lambda: self._uso("copiar"))
        self.btn_uso_cop.pack(side="left", padx=4)
        self.lbl_cont = ttk.Label(top, text="")
        self.lbl_cont.pack(side="right")

        meio = ttk.Frame(self)
        meio.pack(fill="both", expand=True, padx=8)

        self.modo = "foto"  # foto | grade
        self.centro = ttk.Frame(meio)
        self.centro.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(self.centro, bg="black")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<MouseWheel>", self._zoom_roda)
        self.canvas.bind("<Button-4>", lambda _e: self._zoom_passo(1.25))
        self.canvas.bind("<Button-5>", lambda _e: self._zoom_passo(1 / 1.25))

        # Modo miniaturas: rolagem vertical com grupos por atividade/etapa.
        self.grade_frame = ttk.Frame(self.centro)
        self.grade_canvas = tk.Canvas(self.grade_frame, bg="#1e1e1e",
                                      highlightthickness=0)
        self.grade_scroll = ttk.Scrollbar(self.grade_frame, orient="vertical",
                                          command=self.grade_canvas.yview)
        self.grade_canvas.configure(yscrollcommand=self.grade_scroll.set)
        self.grade_scroll.pack(side="right", fill="y")
        self.grade_canvas.pack(side="left", fill="both", expand=True)
        self.grade_inner = ttk.Frame(self.grade_canvas)
        self._grade_win = self.grade_canvas.create_window(
            (0, 0), window=self.grade_inner, anchor="nw")
        self.grade_inner.bind(
            "<Configure>",
            lambda _e: self.grade_canvas.configure(
                scrollregion=self.grade_canvas.bbox("all")))
        self.grade_canvas.bind(
            "<Configure>",
            lambda e: self.grade_canvas.itemconfig(self._grade_win, width=e.width))
        self.grade_canvas.bind("<MouseWheel>", self._grade_rolar)
        self._thumbs: dict[str, ImageTk.PhotoImage] = {}
        self._thumb_btns: dict[int, tk.Button] = {}  # pos na ordem -> botão
        self._grade_montada = False
        self._grade_suja = True

        lado = ttk.Frame(meio, width=330)
        lado.pack(side="right", fill="y", padx=(8, 0))
        lado.pack_propagate(False)

        # Painel lateral com rolagem: cabe tudo em qualquer altura de janela.
        lado_canvas = tk.Canvas(lado, highlightthickness=0)
        lado_scroll = ttk.Scrollbar(lado, orient="vertical",
                                    command=lado_canvas.yview)
        lado_canvas.configure(yscrollcommand=lado_scroll.set)
        lado_scroll.pack(side="right", fill="y")
        lado_canvas.pack(side="left", fill="both", expand=True)
        lado_inner = ttk.Frame(lado_canvas)
        lado_win = lado_canvas.create_window((0, 0), window=lado_inner, anchor="nw")
        lado_inner.bind("<Configure>", lambda _e: lado_canvas.configure(
            scrollregion=lado_canvas.bbox("all")))
        lado_canvas.bind("<Configure>", lambda e: lado_canvas.itemconfig(
            lado_win, width=e.width))
        lado_canvas.bind("<MouseWheel>", lambda e: lado_canvas.yview_scroll(
            -1 if e.delta > 0 else 1, "units"))
        lado = lado_inner

        # Textos com altura FIXA: o painel lateral nunca muda de tamanho
        # ao trocar de foto.
        self.lbl_info = tk.Label(lado, text="", wraplength=310, justify="left",
                                 font=("", 10, "bold"), height=4, anchor="nw")
        self.lbl_info.pack(anchor="w", pady=(0, 2), fill="x")
        self.lbl_obs_ia = tk.Label(lado, text="", wraplength=310, justify="left",
                                   height=4, anchor="nw", fg="#555555")
        self.lbl_obs_ia.pack(anchor="w", pady=(0, 4), fill="x")

        ttk.Label(lado, text="Vínculos desta foto (1 foto = N atividades):").pack(anchor="w")
        self.lb_vinc = tk.Listbox(lado, height=3, width=44)
        self.lb_vinc.pack(anchor="w", pady=(0, 2))
        self._sel_manual = False  # True só quando CLICA num vínculo da lista
        self.lb_vinc.bind("<<ListboxSelect>>", lambda _e: self._ao_selecionar_vinc())

        ttk.Label(lado, text="Atividade:").pack(anchor="w")
        self.cb_ativ = ttk.Combobox(lado, state="readonly", width=42)
        self.cb_ativ.pack(anchor="w", pady=(0, 2))

        vincf = ttk.Frame(lado)
        vincf.pack(anchor="w", pady=(0, 4))
        ttk.Button(vincf, text="+ Juntar", command=self.adicionar_vinc).pack(side="left")
        ttk.Button(vincf, text="Trocar", command=self.trocar_vinc).pack(side="left", padx=4)
        ttk.Button(vincf, text="− Tirar", command=self.remover_vinc).pack(side="left")
        ttk.Button(vincf, text="Limpar", command=self.limpar_vincs).pack(side="left", padx=(4, 0))

        ttk.Label(lado, text="Etapa:").pack(anchor="w")
        self.etapa_var = tk.StringVar(value="")
        self._sync_vinc = False  # True só p/ clique do usuário (não ao carregar)
        self.etapa_var.trace_add("write", lambda *_a: self._ao_mudar_etapa())
        etaf = ttk.Frame(lado)
        etaf.pack(anchor="w", pady=(0, 2))
        self.rb_etapas: list[ttk.Radiobutton] = []
        for valor, texto in [(e, e) for e in ETAPAS]:
            rb = ttk.Radiobutton(etaf, text=texto, value=valor,
                                 variable=self.etapa_var)
            rb.pack(side="left")
            self.rb_etapas.append(rb)

        ttk.Label(lado, text="Qualidade p/ relatório:").pack(anchor="w", pady=(4, 0))
        self.cb_qual = ttk.Combobox(lado, values=[q for q in QUALIDADES if q],
                                    state="readonly", width=12)
        self.cb_qual.pack(anchor="w", pady=(0, 2))
        ttk.Label(lado, text="boa entra · ruim fraca · duplicada similar a outra",
                  wraplength=310, justify="left").pack(anchor="w", pady=(0, 4))

        ttk.Label(lado, text="Observação:").pack(anchor="w")
        self.tx_obs = tk.Text(lado, height=6, width=40)
        self.tx_obs.pack(anchor="w", pady=(0, 4), fill="x")

        nav = ttk.Frame(lado)
        nav.pack(anchor="w", pady=2)
        ttk.Button(nav, text="◀ Anterior", command=self.anterior).pack(side="left")
        ttk.Button(nav, text="Salvar (Enter)", command=self.salvar).pack(side="left", padx=6)
        ttk.Button(nav, text="Próxima ▶", command=self.proxima).pack(side="left")

        zoomf = ttk.Frame(lado)
        zoomf.pack(anchor="w", pady=2)
        ttk.Button(zoomf, text="Ajustar", command=self._zoom_ajustar).pack(side="left")
        ttk.Button(zoomf, text="1:1", command=self._zoom_um).pack(side="left", padx=4)
        ttk.Button(zoomf, text="−", command=lambda: self._zoom_passo(1 / 1.25),
                   width=3).pack(side="left")
        ttk.Button(zoomf, text="+", command=lambda: self._zoom_passo(1.25),
                   width=3).pack(side="left", padx=4)

        distf = ttk.Frame(lado)
        distf.pack(anchor="w", pady=(6, 0))
        ttk.Button(distf, text="Distribuir (montar pastas)",
                   command=self._distribuir).pack(side="left")
        self.var_soboas = tk.BooleanVar(value=False)
        ttk.Checkbutton(distf, text="só boas", variable=self.var_soboas).pack(side="left", padx=6)
        ttk.Label(lado, text="Atalhos: ← → navega · scroll zoom · Enter salva · 1/2/3 etapa · 0 limpa.\nEtapa troca direto · + Juntar adiciona outro · Trocar edita o selecionado · Miniaturas: 1 clique edita, 2 abre.",
                  wraplength=310, justify="left").pack(anchor="w", pady=(6, 0))

        self.status = ttk.Label(self, text="", relief="sunken", anchor="w")
        self.status.pack(fill="x", side="bottom")
        # Layout do modo avaliar (p/ alternar com o modo copiar).
        self._aval_layout = [(w, dict(w.pack_info()))
                             for w in lado_inner.winfo_children()]
        self.painel_copy = ttk.Frame(lado_inner)
        self._montar_painel_copia()
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)
        # Scroll do painel lateral em qualquer ponto (menos em caixas de
        # texto/lista, que têm rolagem própria).
        self._lado_bind_wheel(lado_inner, lado_canvas)

        self.bind("<Left>", lambda _e: self.anterior())
        self.bind("<Right>", lambda _e: self.proxima())
        self.bind("<Return>", lambda _e: self.salvar())
        self.bind("1", lambda _e: self._tecla_etapa("antes"))
        self.bind("2", lambda _e: self._tecla_etapa("durante"))
        self.bind("3", lambda _e: self._tecla_etapa("depois"))
        self.bind("0", lambda _e: self._tecla_limpar())
        self.bind("<Control-c>", self._atalho_copiar)
        self.bind("<Control-e>", self._atalho_enviar)
        self.bind("<Configure>", lambda _e: self._redesenhar())

        if relatorio:
            self.cb_rel.set(relatorio)
            self.trocar_relatorio()
        elif self.cb_rel["values"]:
            self.cb_rel.current(0)
            self.trocar_relatorio()

    # ----- dados -----

    def trocar_relatorio(self):
        nome = self.cb_rel.get().strip()
        if not nome:
            return
        self.pasta_rel = pasta_relatorio(nome)
        self.origem = resolver_origem(self.pasta_rel)
        self.linhas = carregar_linhas(self.pasta_rel)
        escopo = carregar_escopo(self.pasta_rel)
        self.ops = opcoes_atividade(escopo)
        self.cb_ativ["values"] = [t for _, t in self.ops]
        filtros = ["Todas"] + [t for _, t in self.ops] + [
            "Boas p/ relatório", "Não selecionadas"]
        self.cb_filtro["values"] = filtros
        self.cb_filtro.current(0)
        self._thumbs.clear()
        self._grade_suja = True
        self.aplicar_filtro()
        self._msg(f"Relatório '{nome}': {len(self.linhas)} fotos em {self.origem}")

    def _grupos_para(self, idxs: list[int]):
        """Agrupa índices por atividade/etapa na ordem do escopo.

        Retorna (grupos, ordem) — a ordem vale p/ foto única e miniaturas.
        """
        grupos: list[tuple[str, str, str, list[int]]] = []
        ativs = [(a, t) for a, t in self.ops if a.upper() != ATIVIDADE_SITE]
        for aid, rotulo in ativs:
            for etapa in ETAPAS:
                membros = [i for i in idxs if tem_vinculo(self.linhas[i], aid, etapa)]
                if membros:
                    grupos.append(("ativ", rotulo, etapa, membros))
        site = [i for i in idxs if tem_vinculo(self.linhas[i], ATIVIDADE_SITE)]
        if site:
            grupos.append(("site", f"{ATIVIDADE_SITE} — Fotos do site", "", site))
        ni = [i for i in idxs if not pares_evidencia(self.linhas[i])]
        if ni:
            grupos.append(("ni", ETAPA_NENHUMA, "", ni))
        if not grupos and idxs:
            grupos.append(("todas", self.cb_filtro.get() or "Fotos", "", list(idxs)))
        ordem = [i for _, _, _, membros in grupos for i in membros]
        return grupos, ordem

    def aplicar_filtro(self):
        f = self.cb_filtro.get()
        idx = list(range(len(self.linhas)))
        if f == "Boas p/ relatório":
            idx = [i for i in idx if self.linhas[i]["Qualidade"] == "boa"]
        elif f == "Não selecionadas":
            idx = [i for i in idx if self.linhas[i]["Qualidade"] != "boa"]
        elif f not in ("Todas", ""):
            aid = f.split(" —")[0]
            idx = [i for i in idx if tem_vinculo(self.linhas[i], aid)]
        self.visiveis = idx
        self.grupos, self.ordem = self._grupos_para(idx)
        self.pos = 0
        if self.modo == "grade":
            self._grade_montar(scroll="topo")
        else:
            self.mostrar()

    def _foco_texto(self) -> bool:
        """True se o foco está em campo de digitação (não roubar teclas)."""
        foco = self.focus_get()
        return isinstance(foco, (tk.Entry, tk.Text))

    def _tecla_etapa(self, etapa: str):
        if self._foco_texto():
            return
        self.etapa_var.set(etapa)

    def _tecla_limpar(self):
        if self._foco_texto():
            return
        self.limpar_vincs()

    def _atalho_copiar(self, event):
        if self.uso != "copiar" or self._foco_texto():
            return None
        self._copiar_atual()
        return "break"

    def _atalho_enviar(self, event):
        if self.uso != "copiar" or self._foco_texto():
            return None
        self._enviar_atual()
        return "break"

    # ----- navegação (mesma ordem nos 2 modos) -----

    def _atual(self) -> dict | None:
        if not self.ordem:
            return None
        return self.linhas[self.ordem[self.pos]]

    def _texto_vincs(self) -> str:
        partes = []
        for aid, etapa in self.vincs:
            if aid == ATIVIDADE_SITE:
                partes.append(ATIVIDADE_SITE)
            else:
                partes.append(f"{aid}/{etapa}")
        return " + ".join(partes) if partes else ETAPA_NENHUMA

    def _refrescar_vincs(self, manter_sel=None, manual=None):
        self.lb_vinc.delete(0, "end")
        for aid, etapa in self.vincs:
            rot = rotulo_atividade(self.ops, aid)
            self.lb_vinc.insert("end",
                                f"{rot}" + (f" / {etapa}" if etapa else ""))
        if manter_sel is not None and 0 <= manter_sel < len(self.vincs):
            self.lb_vinc.selection_set(manter_sel)
            self.lb_vinc.see(manter_sel)
        if manual is not None:
            self._sel_manual = manual

    def mostrar(self):
        item = self._atual()
        if item is None or self.origem is None:
            self.lbl_info.config(text="Nada para mostrar neste filtro.")
            self.lbl_obs_ia.config(text="")
            self.vincs = []
            self._refrescar_vincs()
            self.canvas.delete("all")
            self._contadores()
            return
        caminho = self.origem / item["Arquivo"]
        try:
            self.foto_img = Image.open(caminho).convert("RGB")
        except Exception as exc:
            self.lbl_info.config(text=f"Erro ao abrir {item['Arquivo']}: {exc}")
            return
        self.zoom = 0.0
        self._redesenhar()
        self.vincs = pares_evidencia(item)
        self._refrescar_vincs(manter_sel=0 if self.vincs else None, manual=False)
        self._sync_vinc = False
        if self.vincs:
            aid0, etapa0 = self.vincs[0]
            self.cb_ativ.set(rotulo_atividade(self.ops, aid0))
            self.etapa_var.set(etapa0 if etapa0 in ETAPAS else "")
        else:
            self.cb_ativ.set("")
            self.etapa_var.set("")
        self._sync_vinc = True
        self.cb_qual.set(item["Qualidade"] if item["Qualidade"] in QUALIDADES else "")
        self.tx_obs.delete("1.0", "end")
        self.tx_obs.insert("1.0", item["Observacao"])
        total = len(self.ordem)
        self.lbl_info.config(
            text=f"{item['Arquivo']}  ({self.pos + 1}/{total})\n"
                 f"Ordem {item['Ordem']} · {item['DataHora'] or 'sem data'} · "
                 f"atual: {self._texto_vincs()} [{item['Status'] or '?'}] · "
                 f"qualidade: {item['Qualidade'] or '—'}")
        self.lbl_obs_ia.config(text=f"IA: {item['Observacao']}" if item["Observacao"] else "")
        self._contadores()
        self._destacar_miniatura()
        self._copy_info_refresh()

    def _contadores(self):
        tot = len(self.linhas)
        boas = sum(1 for r in self.linhas if r["Qualidade"] == "boa")
        nsel = tot - boas
        ni = sum(1 for r in self.linhas if not pares_evidencia(r))
        multi = sum(1 for r in self.linhas if len(pares_evidencia(r)) > 1)
        self.lbl_cont.config(
            text=f"boas {boas} · não sel. {nsel} · N/I {ni} · multi {multi} · total {tot}")

    def anterior(self):
        if self.modo != "foto":
            return
        if self.ordem:
            self.pos = (self.pos - 1) % len(self.ordem)
            self.mostrar()

    def proxima(self):
        if self.modo != "foto":
            return
        if self.ordem:
            self.pos = (self.pos + 1) % len(self.ordem)
            self.mostrar()

    # ----- vínculos (etapa direta; + Juntar / Trocar explícitos) -----

    def _ao_selecionar_vinc(self):
        # Clicar num vínculo carrega ele no Atividade/Etapa p/ editar.
        sel = self.lb_vinc.curselection()
        if not sel:
            self._sel_manual = False
            return
        self._sel_manual = True
        i = sel[0]
        if 0 <= i < len(self.vincs):
            aid, etapa = self.vincs[i]
            self._sync_vinc = False
            self.cb_ativ.set(rotulo_atividade(self.ops, aid))
            self.etapa_var.set(etapa if etapa in ETAPAS else "")
            self._sync_vinc = True

    def _ao_mudar_etapa(self):
        # 1) vínculo CLICADO na lista: a etapa vale p/ ele (qualquer atividade);
        # 2) sem clique: só edita direto se for vínculo único e o combo conferir
        #    (se trocou de atividade junto, está compondo outro: usa Juntar).
        if not self._sync_vinc:
            return
        e = self.etapa_var.get()
        if e not in ETAPAS:
            return
        if self._sel_manual:
            sel = self.lb_vinc.curselection()
            if not sel:
                self._sel_manual = False
                return
            i = sel[0]
            aid, _old = self.vincs[i]
            if aid == ATIVIDADE_SITE:
                self._msg("SITE não tem etapa.")
                return
            self.vincs[i] = (aid, e)
            self.cb_ativ.set(rotulo_atividade(self.ops, aid))
            self._refrescar_vincs(manter_sel=i)
            return
        if len(self.vincs) != 1:
            return
        aid, _old = self.vincs[0]
        if aid == ATIVIDADE_SITE:
            self._msg("SITE não tem etapa.")
            return
        rotulo = self.cb_ativ.get()
        combo_aid = next((x for x, t in self.ops if t == rotulo), "")
        if combo_aid and combo_aid != aid:
            return
        self.vincs[0] = (aid, e)
        self._refrescar_vincs(manter_sel=0)

    def _pendente(self):
        """Vínculo montado em Atividade+Etapa (sem mexer na lista)."""
        rotulo = self.cb_ativ.get()
        aid = next((i for i, t in self.ops if t == rotulo), "")
        if not aid:
            return None
        if aid == ATIVIDADE_SITE:
            return (ATIVIDADE_SITE, "")
        etapa = self.etapa_var.get()
        if etapa not in ETAPAS:
            return None
        return (aid, etapa)

    def adicionar_vinc(self):
        vinc = self._pendente()
        if vinc is None:
            self._msg("Escolha atividade + etapa para juntar.")
            return
        if vinc not in self.vincs:
            self.vincs.append(vinc)
        self._refrescar_vincs(manter_sel=self.vincs.index(vinc), manual=False)

    def trocar_vinc(self):
        vinc = self._pendente()
        if vinc is None:
            self._msg("Escolha atividade + etapa para trocar.")
            return
        sel = self.lb_vinc.curselection()
        i = sel[0] if sel else (0 if len(self.vincs) == 1 else -1)
        if i < 0:
            self._msg("Selecione o vínculo na lista para trocar.")
            return
        self.vincs[i] = vinc
        # remove repetidos preservando ordem
        unicos: list[tuple[str, str]] = []
        for v in self.vincs:
            if v not in unicos:
                unicos.append(v)
        self.vincs = unicos
        self._refrescar_vincs(manter_sel=self.vincs.index(vinc), manual=False)

    def remover_vinc(self):
        sel = self.lb_vinc.curselection()
        if not sel:
            return
        i = sel[0]
        del self.vincs[i]
        self._refrescar_vincs(manter_sel=min(i, len(self.vincs) - 1), manual=False)

    def limpar_vincs(self):
        self.vincs = []
        self._refrescar_vincs(manual=False)
        self.cb_ativ.set("")
        self.etapa_var.set("")

    def salvar(self):
        item = self._atual()
        if item is None or self.pasta_rel is None:
            return
        validos = [(a, e) for a, e in self.vincs
                   if a == ATIVIDADE_SITE or (a and e in ETAPAS)]
        # remove repetidos preservando ordem
        unicos: list[tuple[str, str]] = []
        for v in validos:
            if v not in unicos:
                unicos.append(v)
        self.vincs = unicos
        if unicos:
            item["Atividade"] = ";".join(a for a, _ in unicos)
            item["Etapa"] = ";".join(e for _, e in unicos)
            item["Status"] = "OK"
        else:
            item["Atividade"] = ""
            item["Etapa"] = ""
            item["Status"] = "NAO_IDENTIFICADA"
        item["Confianca"] = item.get("Confianca") or ""
        qual = self.cb_qual.get()
        item["Qualidade"] = qual if qual in QUALIDADES else ""
        item["Observacao"] = self.tx_obs.get("1.0", "end").strip()
        try:
            salvar_linhas(self.pasta_rel, self.linhas)
        except PermissionError:
            messagebox.showerror("Salvar",
                                 "Não consegui gravar evidencia.csv — feche o arquivo "
                                 "se ele estiver aberto no Excel e tente de novo.")
            return
        except OSError as exc:
            messagebox.showerror("Salvar", f"Erro ao gravar evidencia.csv:\n{exc}")
            return
        self._grade_suja = True
        self._msg(f"Salvo {item['Arquivo']}: {self._texto_vincs()}")
        if self.modo == "foto":
            self.proxima()
        else:
            # Reconstrói a grade (a foto salva pode ter mudado de grupo) e
            # avança para a próxima da ordem antiga.
            proxima_linha = None
            if self.ordem and self.pos + 1 < len(self.ordem):
                proxima_linha = self.ordem[self.pos + 1]
            self._reagrupar()
            if proxima_linha is not None and proxima_linha in self.ordem:
                self.pos = self.ordem.index(proxima_linha)
            else:
                self.pos = min(self.pos, max(0, len(self.ordem) - 1))
            self._grade_montar(scroll="manter")
            self.mostrar()
            self._grade_revelar(self.pos)

    def _distribuir(self):
        if self.pasta_rel is None:
            return
        so_boas = self.var_soboas.get()
        txt = ("Salvar e montar as pastas SÓ com qualidade boa?"
               if so_boas else "Salvar e montar as pastas atividade/etapa agora?")
        if not messagebox.askyesno("Distribuir", txt):
            return
        realizados = distribuir(self.pasta_rel.name, so_boas=so_boas)
        self._msg(f"Distribuído: {len(realizados)} cópias.")
        messagebox.showinfo("Distribuir", f"{len(realizados)} cópias criadas.")

    def _lado_bind_wheel(self, widget, canvas):
        if not isinstance(widget, (tk.Text, tk.Listbox)):
            widget.bind("<MouseWheel>", lambda e: canvas.yview_scroll(
                -1 if e.delta > 0 else 1, "units"))
        for filho in widget.winfo_children():
            self._lado_bind_wheel(filho, canvas)

    def _reagrupar(self):
        """Recalcula grupos/ordem do filtro atual (após salvar)."""
        self.grupos, self.ordem = self._grupos_para(self.visiveis)

    def _msg(self, texto: str):
        self.status.config(text=texto)

    # ----- modo avaliar / copiar -----

    def _uso(self, uso: str):
        if uso == self.uso:
            return
        if uso == "copiar" and FF is None:
            messagebox.showwarning("Copiar", "fit_fotos não carregou — só avaliação.")
            return
        if self.uso == "copiar":
            self._salvar_cfg_copia()
            self.painel_copy.pack_forget()
            for w, info in self._aval_layout:
                try:
                    w.pack(**info)
                except tk.TclError:
                    pass
        else:
            for w, _info in self._aval_layout:
                try:
                    w.pack_forget()
                except tk.TclError:
                    pass
            self.painel_copy.pack(anchor="w", fill="x")
            self._copy_info_refresh()
        self.uso = uso
        self._msg("Modo " + ("avaliação." if uso == "avaliar" else "cópia p/ Excel."))

    def _montar_painel_copia(self):
        p = self.painel_copy
        ttk.Label(p, text="Copiar para o Excel", font=("", 10, "bold")).pack(anchor="w", pady=(0, 2))
        self.copy_info = tk.Label(p, text="", wraplength=310, justify="left", height=3, anchor="nw")
        self.copy_info.pack(anchor="w", fill="x", pady=(0, 4))

        tamf = ttk.Frame(p)
        tamf.pack(anchor="w", pady=(0, 2))
        ttk.Label(tamf, text="Tam:").pack(side="left")
        self.cp_larg = tk.StringVar(value="6")
        self.cp_alt = tk.StringVar(value="4")
        self.cp_uni = tk.StringVar(value="cm")
        self.cp_dpi = tk.StringVar(value="96")
        ttk.Entry(tamf, textvariable=self.cp_larg, width=7).pack(side="left", padx=2)
        ttk.Label(tamf, text="x").pack(side="left")
        ttk.Entry(tamf, textvariable=self.cp_alt, width=7).pack(side="left", padx=2)
        ttk.Radiobutton(tamf, text="cm", variable=self.cp_uni, value="cm",
                        command=self._copy_info_refresh).pack(side="left")
        ttk.Radiobutton(tamf, text="px", variable=self.cp_uni, value="px",
                        command=self._copy_info_refresh).pack(side="left")
        ttk.Label(tamf, text="DPI").pack(side="left", padx=(6, 0))
        ttk.Entry(tamf, textvariable=self.cp_dpi, width=6).pack(side="left", padx=2)

        self.cp_prop = tk.BooleanVar(value=True)
        self.cp_alta = tk.BooleanVar(value=True)
        ttk.Checkbutton(p, text="manter proporção", variable=self.cp_prop).pack(anchor="w")
        ttk.Checkbutton(p, text="alta resolução", variable=self.cp_alta,
                        command=self._copy_info_refresh).pack(anchor="w")
        self.copy_px = tk.Label(p, text="", wraplength=310, justify="left", fg="#555555")
        self.copy_px.pack(anchor="w", fill="x", pady=(0, 4))
        for v in (self.cp_larg, self.cp_alt, self.cp_dpi):
            v.trace_add("write", lambda *_a: self._copy_info_refresh())
        try:
            cfg = FF.carregar_config() if FF else {}
        except Exception:
            cfg = {}
        if isinstance(cfg, dict) and cfg:
            self.cp_larg.set(str(cfg.get("largura", "6")))
            self.cp_alt.set(str(cfg.get("altura", "4")))
            self.cp_uni.set(cfg.get("unidade", "cm"))
            self.cp_dpi.set(str(cfg.get("dpi", "96")))
            self.cp_prop.set(bool(cfg.get("manter_proporcao", True)))
            self.cp_alta.set(bool(cfg.get("alta", True)))

        btnf = ttk.Frame(p)
        btnf.pack(anchor="w", pady=2)
        ttk.Button(btnf, text="Copiar (Ctrl+C)", command=self._copiar_atual).pack(side="left")
        ttk.Button(btnf, text="Enviar (Ctrl+E)", command=self._enviar_atual).pack(side="left", padx=4)
        ttk.Button(p, text="Salvar foto atual", command=self._salvar_atual).pack(anchor="w", pady=2)
        ttk.Button(p, text="Salvar visíveis (filtro)", command=self._salvar_visiveis).pack(anchor="w", pady=2)
        ttk.Label(p, text="Destino:").pack(anchor="w", pady=(4, 0))
        self.cp_dest = tk.StringVar(value="Arquivos/Fotos_Fit")
        ttk.Entry(p, textvariable=self.cp_dest, width=42).pack(anchor="w", fill="x")
        if isinstance(cfg, dict) and cfg.get("destino"):
            self.cp_dest.set(str(cfg["destino"]))
        ttk.Label(p, text="Mesmo tamanho do fit_fotos; a config é compartilhada.",
                  wraplength=310, justify="left").pack(anchor="w", pady=(6, 0))

    def _salvar_cfg_copia(self):
        if FF is None:
            return
        try:
            FF.salvar_config({"largura": self.cp_larg.get().strip(),
                              "altura": self.cp_alt.get().strip(),
                              "unidade": self.cp_uni.get(),
                              "dpi": self.cp_dpi.get().strip(),
                              "manter_proporcao": bool(self.cp_prop.get()),
                              "alta": bool(self.cp_alta.get()),
                              "destino": self.cp_dest.get().strip()})
        except Exception:
            pass

    def _ao_fechar(self):
        if self.uso == "copiar":
            self._salvar_cfg_copia()
        self.destroy()

    def _img_atual(self):
        item = self._atual()
        if item is None or self.origem is None:
            return None, None
        try:
            return Image.open(self.origem / item["Arquivo"]).convert("RGB"), item["Arquivo"]
        except Exception as exc:
            messagebox.showerror("Abrir foto", f"Erro ao abrir {item['Arquivo']}:\n{exc}")
            return None, None

    def _copy_info_refresh(self):
        if self.uso != "copiar":
            return
        item = self._atual()
        if item is None:
            return
        try:
            base = self.origem / item["Arquivo"]
            with Image.open(base) as img:
                ow, oh = img.size
        except Exception:
            ow, oh = 0, 0
        self.copy_info.config(text=f"{item['Arquivo']} — original {ow}x{oh} px")
        try:
            larg = float(self.cp_larg.get().replace(",", "."))
            alt = float(self.cp_alt.get().replace(",", "."))
            dpi = int(self.cp_dpi.get())
            uni = self.cp_uni.get()
            if self.cp_alta.get() and ow:
                lw, lh = FF.pedido_para_cm(larg, alt, uni, dpi)
                (dx, _dy), (dw, dh) = FF.calcular_dpi(ow, oh, lw, lh, self.cp_prop.get())
                self.copy_px.config(text=f"= exibe {dw:.1f} x {dh:.1f} cm (DPI {dx:.0f})")
            else:
                w, h = FF.converter_tamanho(larg, alt, uni, dpi)
                self.copy_px.config(text=f"= {w} x {h} px")
        except (ValueError, AttributeError):
            self.copy_px.config(text="")

    def _ler_pedido_copia(self):
        try:
            larg = float(self.cp_larg.get().replace(",", "."))
            alt = float(self.cp_alt.get().replace(",", "."))
            if larg <= 0 or alt <= 0:
                raise ValueError
            uni = self.cp_uni.get()
            dpi = int(self.cp_dpi.get()) if uni == "cm" else FF.DPI_PADRAO
            if dpi <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Tamanho inválido",
                                   "Digite largura, altura (e DPI) maiores que zero.")
            return None
        return larg, alt, uni, dpi

    def _copiar_atual(self, _event=None):
        if FF is None:
            return
        img, nome = self._img_atual()
        if img is None:
            return
        pedido = self._ler_pedido_copia()
        if pedido is None:
            return
        larg, alt, uni, dpi_base = pedido
        try:
            if self.cp_alta.get():
                lw, lh = FF.pedido_para_cm(larg, alt, uni, dpi_base)
                (dx, dy), (dw, dh) = FF.calcular_dpi(*img.size, lw, lh, self.cp_prop.get())
                FF.copiar_para_clipboard(img, dpi=(dx, dy), tamanho_emf_cm=(dw, dh))
                self._msg(f"{nome} copiada em alta — cole no Excel com Ctrl+V.")
            else:
                w, h = FF.converter_tamanho(larg, alt, uni, dpi_base)
                final = FF.redimensionar(img, w, h, self.cp_prop.get())
                FF.copiar_para_clipboard(final)
                self._msg(f"{nome} copiada ({final.size[0]}x{final.size[1]} px) — cole no Excel.")
        except Exception as exc:
            messagebox.showerror("Erro ao copiar", str(exc))

    def _enviar_atual(self, _event=None):
        if FF is None:
            return
        img, nome = self._img_atual()
        if img is None:
            return
        pedido = self._ler_pedido_copia()
        if pedido is None:
            return
        larg, alt, uni, dpi_base = pedido
        lw, lh = FF.pedido_para_cm(larg, alt, uni, dpi_base)
        _dpi, (dw, dh) = FF.calcular_dpi(*img.size, lw, lh, self.cp_prop.get())
        try:
            onde = FF.enviar_para_excel(img, dw, dh)
        except Exception as exc:
            messagebox.showerror("Erro ao enviar", str(exc))
            return
        self._msg(f"{nome} inserida no Excel em {onde}.")

    def _salvar_atual(self):
        if FF is None:
            return
        img, nome = self._img_atual()
        if img is None:
            return
        pedido = self._ler_pedido_copia()
        if pedido is None:
            return
        larg, alt, uni, dpi_base = pedido
        from pathlib import Path as _P
        destino = _P(self.cp_dest.get().strip())
        if not destino.is_absolute():
            destino = FF.RAIZ_PROJETO / destino
        destino.mkdir(parents=True, exist_ok=True)
        try:
            if self.cp_alta.get():
                lw, lh = FF.pedido_para_cm(larg, alt, uni, dpi_base)
                (dx, dy), _ex = FF.calcular_dpi(*img.size, lw, lh, self.cp_prop.get())
                FF.salvar_copia(img, destino / nome, dpi=(dx, dy))
            else:
                w, h = FF.converter_tamanho(larg, alt, uni, dpi_base)
                FF.salvar_copia(FF.redimensionar(img, w, h, self.cp_prop.get()),
                                destino / nome)
        except Exception as exc:
            messagebox.showerror("Erro ao salvar", str(exc))
            return
        self._msg(f"{nome} salva em {destino}.")

    def _salvar_visiveis(self):
        if FF is None or not self.ordem or self.origem is None:
            return
        pedido = self._ler_pedido_copia()
        if pedido is None:
            return
        larg, alt, uni, dpi_base = pedido
        from pathlib import Path as _P
        destino = _P(self.cp_dest.get().strip())
        if not destino.is_absolute():
            destino = FF.RAIZ_PROJETO / destino
        destino.mkdir(parents=True, exist_ok=True)
        ok, erros = 0, 0
        for idx in self.ordem:
            caminho = self.origem / self.linhas[idx]["Arquivo"]
            try:
                with Image.open(caminho) as img:
                    img.load()
                    if self.cp_alta.get():
                        lw, lh = FF.pedido_para_cm(larg, alt, uni, dpi_base)
                        (dx, dy), _ex = FF.calcular_dpi(*img.size, lw, lh, self.cp_prop.get())
                        FF.salvar_copia(img, destino / caminho.name, dpi=(dx, dy))
                    else:
                        w, h = FF.converter_tamanho(larg, alt, uni, dpi_base)
                        FF.salvar_copia(FF.redimensionar(img, w, h, self.cp_prop.get()),
                                        destino / caminho.name)
                ok += 1
            except Exception:
                erros += 1
        self._msg(f"Salvas {ok} fotos em {destino} ({erros} erros).")

    # ----- modo foto única / miniaturas -----

    def _modo(self, modo: str):
        if modo == self.modo:
            return
        self.modo = modo
        if modo == "grade":
            self.canvas.pack_forget()
            self.grade_frame.pack(fill="both", expand=True)
            if self._grade_suja or not self._grade_montada:
                self._grade_montar(scroll="topo")
            self._grade_revelar(self.pos)
        else:
            self.grade_frame.pack_forget()
            self.canvas.pack(fill="both", expand=True)
            self.mostrar()

    def _cor_status(self, status: str) -> str:
        return {"OK": "#2e7d32", "SUGERIDA": "#ef6c00", "PENDENTE": "#757575",
                "NAO_IDENTIFICADA": "#c62828"}.get(status, "#757575")

    def _thumb(self, caminho: Path, nome: str) -> ImageTk.PhotoImage | None:
        if nome in self._thumbs:
            return self._thumbs[nome]
        try:
            img = Image.open(caminho).convert("RGB")
            img.thumbnail((192, 144), Image.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)
        except Exception:
            return None
        self._thumbs[nome] = tk_img
        return tk_img

    def _largura_colunas(self) -> int:
        largura = self.grade_canvas.winfo_width()
        if largura < 100:  # ainda sem geometria → estimativa
            return 4
        return max(2, largura // 220)

    def _grade_montar(self, scroll: str = "topo"):
        for w in self.grade_inner.winfo_children():
            w.destroy()
        self._thumb_btns = {}
        if not self.ordem or self.origem is None:
            ttk.Label(self.grade_inner, text="Nada para mostrar neste filtro.").pack(pady=20)
            self._grade_montada = True
            self._grade_suja = False
            return
        self._msg(f"Carregando {len(self.ordem)} miniaturas…")
        self.update_idletasks()
        ncol = self._largura_colunas()

        def faixa_com_miniaturas(membros: list[int], recuo: int, titulo: str, grande: bool):
            ttk.Label(self.grade_inner, text=titulo,
                      font=("", 11 if grande else 10, "bold")).pack(
                          anchor="w", padx=6 if grande else 18,
                          pady=(12, 0) if grande else (4, 2))
            faixa = ttk.Frame(self.grade_inner)
            faixa.pack(anchor="w", padx=18, fill="x")
            col = 0
            for idx_linha in membros:
                item = self.linhas[idx_linha]
                pos_ord = self.ordem.index(idx_linha)
                img = self._thumb(self.origem / item["Arquivo"], item["Arquivo"])
                legenda = f"{item['Arquivo']}\n{item['Qualidade'] or '—'}"
                btn = tk.Button(faixa, image=img, text=legenda, compound="top",
                                font=("", 8), relief="flat",
                                highlightbackground=self._cor_status(item["Status"]),
                                highlightthickness=3,
                                command=lambda p=pos_ord: self._grade_selecionar(p))
                btn.bind("<Double-Button-1>", lambda _e, p=pos_ord: self._grade_abrir(p))
                btn.grid(row=0, column=col, padx=4, pady=4)
                self._thumb_btns[pos_ord] = btn
                if col >= ncol - 1:
                    faixa = ttk.Frame(self.grade_inner)
                    faixa.pack(anchor="w", padx=18, fill="x")
                    col = 0
                else:
                    col += 1

        n_grupos = 0
        # Tópico maior = atividade, com antes/durante/depois aninhados.
        vistos: set[str] = set()
        for kind, rotulo, etapa, membros in self.grupos:
            if kind != "ativ":
                continue
            aid = rotulo.split(" —")[0]
            if aid in vistos:
                continue
            vistos.add(aid)
            blocos = [(e, m) for k, r, e, m in self.grupos
                      if k == "ativ" and r == rotulo]
            total = sum(len(m) for _, m in blocos)
            n_grupos += 1
            ttk.Label(self.grade_inner, text=f"{rotulo}  ({total})",
                      font=("", 11, "bold")).pack(anchor="w", padx=6, pady=(12, 0))
            for e, m in blocos:
                faixa_com_miniaturas(m, 18, f"{e}  ({len(m)})", False)
        for kind, rotulo, _etapa, membros in self.grupos:
            if kind == "ativ":
                continue
            n_grupos += 1
            faixa_com_miniaturas(membros, 6 if kind == "site" else 18,
                                 f"{rotulo}  ({len(membros)})", True)
        # Scroll funcionando em qualquer ponto da grade (miniaturas e
        # rótulos consomem o evento, então amarra em cada widget).
        self._grade_bind_wheel(self.grade_inner)
        self._grade_montada = True
        self._grade_suja = False
        if scroll == "topo":
            self.grade_canvas.yview_moveto(0)
        self._destacar_miniatura()
        self._msg(f"{len(self.ordem)} fotos em {n_grupos} grupos — "
                  "1 clique edita, 2 cliques abre grande.")

    def _grade_bind_wheel(self, widget):
        widget.bind("<MouseWheel>", self._grade_rolar)
        widget.bind("<Button-4>",
                    lambda _e: self.grade_canvas.yview_scroll(-1, "units"))
        widget.bind("<Button-5>",
                    lambda _e: self.grade_canvas.yview_scroll(1, "units"))
        for filho in widget.winfo_children():
            self._grade_bind_wheel(filho)

    def _grade_selecionar(self, pos_ord: int):
        # 1 clique: seleciona e carrega no painel p/ editar (sem abrir grande).
        self.pos = pos_ord
        self.mostrar()

    def _grade_abrir(self, pos_ord: int):
        # 2 cliques (ou botão Foto única): abre grande.
        self.pos = pos_ord
        self._modo("foto")

    def _destacar_miniatura(self):
        for p, btn in self._thumb_btns.items():
            try:
                btn.config(relief="sunken" if p == self.pos else "flat")
            except tk.TclError:
                pass

    def _grade_atualizar_thumb(self, pos_ord: int):
        btn = self._thumb_btns.get(pos_ord)
        if btn is None:
            return
        item = self.linhas[self.ordem[pos_ord]]
        try:
            btn.config(highlightbackground=self._cor_status(item["Status"]),
                       text=f"{item['Arquivo']}\n{item['Qualidade'] or '—'}")
        except tk.TclError:
            pass

    def _grade_revelar(self, pos_ord: int):
        # Rola a grade até a foto atual (em vez de voltar ao topo).
        if not self._thumb_btns:
            return
        btn = self._thumb_btns.get(pos_ord)
        if btn is None:
            return
        self.grade_inner.update_idletasks()
        try:
            y = btn.winfo_rooty() - self.grade_inner.winfo_rooty()
            bbox = self.grade_canvas.bbox("all")
            if not bbox:
                return
            vh = self.grade_canvas.winfo_height()
            frac = max(0.0, min(1.0, (y - vh / 2) / max(1, bbox[3])))
            self.grade_canvas.yview_moveto(frac)
        except tk.TclError:
            pass

    def _grade_rolar(self, event):
        self.grade_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    # ----- imagem / zoom -----

    def _redesenhar(self):
        if self.foto_img is None or self.modo != "foto":
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            self.after(100, self._redesenhar)
            return
        img = self.foto_img
        if self.zoom <= 0:
            escala = min(cw / img.width, ch / img.height)
        else:
            escala = self.zoom
        w, h = max(1, int(img.width * escala)), max(1, int(img.height * escala))
        self._tk_img = ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS))
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self._tk_img)

    def _zoom_passo(self, fator: float):
        if self.foto_img is None:
            return
        base = min(self.canvas.winfo_width() / self.foto_img.width,
                   self.canvas.winfo_height() / self.foto_img.height)
        atual = base if self.zoom <= 0 else self.zoom
        self.zoom = max(base / 4, min(atual * fator, 8.0))
        self._redesenhar()

    def _zoom_roda(self, event):
        self._zoom_passo(1.25 if event.delta > 0 else 1 / 1.25)

    def _zoom_ajustar(self):
        self.zoom = 0.0
        self._redesenhar()

    def _zoom_um(self):
        self.zoom = 1.0
        self._redesenhar()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Avalia o relatório foto a foto "
                                             "(atividade + etapa).")
    ap.add_argument("--relatorio", default=None,
                    help="nome do relatório (pasta em Arquivos/Relatorios/)")
    args = ap.parse_args(argv)
    app = Avaliador(relatorio=args.relatorio)
    app.mainloop()


if __name__ == "__main__":
    main()
