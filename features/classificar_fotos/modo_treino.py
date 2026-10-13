"""Modo treino — valide/corrija a classificação foto a foto.

Janela no mesmo estilo do fit_fotos, mas para TREINAR:
- RELATÓRIO é a pasta de trabalho (selecionado na lista);
- o programa tenta sugerir classes no início (última correção da foto)
  e você diz se acertou ou corrige (Enter = acertou);
- classes por MARCAÇÃO (lista) — digite só ao criar (Nova classe);
- classe "Não identificado" vale quando não dá para classificar;
- cada correção vai para _treino.csv e a imagem para _dataset/<classe>/
  (cópia permanente — pode apagar os originais);
- o classificacao.csv do relatório é atualizado (pronto p/ distribuir).

Uso:
    python features/classificar_fotos/classificar_fotos.py --preparar --relatorio gna_fonte
    python features/classificar_fotos/modo_treino.py --relatorio gna_fonte
    (abre direto em Arquivos/Classificadas/gna_fonte/fotos/)

Rode sempre a partir da RAIZ do projeto.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

from PIL import Image, ImageTk

try:
    from .classificar_fotos import (
        BASE_CLASSIFICADAS,
        CABECALHO_CSV,
        NOME_CSV,
        PASTA_FOTOS_REL,
        PASTA_ORIGEM_PADRAO,
        chave_natural,
        listar_fotos,
        sanitizar_nome,
    )
except ImportError:  # chamado como script direto
    from classificar_fotos import (
        BASE_CLASSIFICADAS,
        CABECALHO_CSV,
        NOME_CSV,
        PASTA_FOTOS_REL,
        PASTA_ORIGEM_PADRAO,
        chave_natural,
        listar_fotos,
        sanitizar_nome,
    )

RAIZ_PROJETO = Path(__file__).resolve().parents[2]

CATALOGO_NOME = "_catalogo.json"
TREINO_NOME = "_treino.csv"
DATASET_NOME = "_dataset"
CABECALHO_TREINO = ["Arquivo", "Origem", "Relatorio", "Filtro", "Classes",
                    "Sugestao", "Acertou", "Observacao"]
NAO_IDENTIFICADO = "Não identificado"


# ============================================================
# Lógica pura (sem GUI — testável)
# ============================================================

def caminho_catalogo(base: Path | str | None = None) -> Path:
    base = Path(base) if base else BASE_CLASSIFICADAS
    return base / CATALOGO_NOME


def caminho_treino(base: Path | str | None = None) -> Path:
    base = Path(base) if base else BASE_CLASSIFICADAS
    return base / TREINO_NOME


def carregar_catalogo(base: Path | str | None = None) -> dict:
    """Catálogo {classes: [todas]}. Sem filtro (removido — formato antigo
    com filtros/relatorios é lido e as classes aproveitadas)."""
    vazio: dict = {"classes": []}
    p = caminho_catalogo(base)
    try:
        if p.is_file():
            dados = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(dados, dict):
                return vazio
            classes = [str(c) for c in dados.get("classes", [])] \
                if isinstance(dados.get("classes"), list) else []
            for chave in ("filtros", "relatorios"):
                val = dados.get(chave, {})
                if isinstance(val, dict):
                    for _k, v in val.items():
                        if isinstance(v, list):
                            for c in v:
                                if str(c) not in classes:
                                    classes.append(str(c))
            return {"classes": sorted(classes)}
    except Exception:
        pass
    return vazio


def salvar_catalogo(catalogo: dict, base: Path | str | None = None) -> Path:
    p = caminho_catalogo(base)
    p.parent.mkdir(parents=True, exist_ok=True)
    normal = {"classes": sorted(catalogo.get("classes", []))}
    p.write_text(json.dumps(normal, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def todas_classes(base: Path | str | None = None) -> list[str]:
    return list(carregar_catalogo(base).get("classes", []))


def registrar_classes(classes: list[str],
                      base: Path | str | None = None) -> dict:
    """Guarda classes no catálogo global."""
    cat = carregar_catalogo(base)
    globais = cat.get("classes", [])
    for c in classes:
        c = (c or "").strip()
        if c and c not in globais:
            globais.append(c)
    if NAO_IDENTIFICADO not in globais:
        globais.append(NAO_IDENTIFICADO)
    cat["classes"] = sorted(globais)
    salvar_catalogo(cat, base)
    return cat


def listar_relatorios(base: Path | str | None = None) -> list[str]:
    """Relatórios = pastas reais em Classificadas (criadas pelo --preparar)."""
    base_p = Path(base) if base else BASE_CLASSIFICADAS
    nomes: set[str] = set()
    if base_p.is_dir():
        for p in base_p.iterdir():
            if p.is_dir() and not p.name.startswith(("_", ".")):
                nomes.add(p.name)
    return sorted(nomes)


def guardar_dataset(origem: str | Path, arquivo: str, relatorio: str,
                    classes: list[str],
                    base: Path | str | None = None) -> int:
    """Salva a imagem validada em _dataset/<classe>/ (cópia permanente).

    Nome único por relatório (`<relatorio>__<arquivo>`) — pode apagar os
    originais sem perder o treino. Retorna nº de cópias feitas.
    """
    base_p = Path(base) if base else BASE_CLASSIFICADAS
    src = Path(origem) / arquivo if origem else Path(arquivo)
    if not src.is_file():
        return 0
    feitas = 0
    for cls in classes or [NAO_IDENTIFICADO]:
        dest_dir = base_p / DATASET_NOME / sanitizar_nome(cls)
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dest_dir / f"{sanitizar_nome(relatorio)}__{arquivo}")
            feitas += 1
        except OSError:
            pass
    return feitas


def ler_treino(base: Path | str | None = None) -> list[dict]:
    p = caminho_treino(base)
    if not p.is_file():
        return []
    with open(p, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    # Compat: treinos antigos não tinham coluna Filtro.
    for r in rows:
        r.setdefault("Filtro", "")
    return rows


def sugerir_classes(arquivo: str, relatorio: str,
                    base: Path | str | None = None) -> list[str]:
    """Sugestão atual da foto: o que já está no classificacao.csv do
    relatório (tentativa de classificação por conteúdo, a confirmar no
    treino). Sem sugestão por nome de arquivo. Vazio = Não identificado.
    """
    return ler_classificacao_relatorio(relatorio, base).get((arquivo or "").strip(), [])


def ler_classificacao_relatorio(relatorio: str,
                                base: Path | str | None = None) -> dict[str, list[str]]:
    """Classes já gravadas no classificacao.csv do relatório (se existir)."""
    base_p = Path(base) if base else BASE_CLASSIFICADAS
    csv_path = base_p / sanitizar_nome(relatorio) / NOME_CSV
    saida: dict[str, list[str]] = {}
    if not csv_path.is_file():
        return saida
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            arq = (row.get("Arquivo") or "").strip()
            if not arq:
                continue
            bruto = (row.get("Classes") or "").strip()
            saida[arq] = [c.strip() for c in bruto.replace("|", ";").split(";")
                          if c.strip()]
    return saida


def classes_salvas(arquivo: str, relatorio: str,
                   base: Path | str | None = None) -> list[str]:
    """Classes já validadas dessa foto (persistidas no classificacao.csv)."""
    return ler_classificacao_relatorio(relatorio, base).get((arquivo or "").strip(), [])


def registrar_exemplo(arquivo: str, origem: str, relatorio: str,
                      classes: list[str], sugestao: list[str],
                      acertou: bool, observacao: str = "",
                      base: Path | str | None = None,
                      filtro: str = "") -> None:
    """Acrescenta uma linha ao _treino.csv, garante as classes no catálogo
    e salva a imagem em _dataset/<classe>/ (cópia permanente)."""
    base_p = Path(base) if base else BASE_CLASSIFICADAS
    base_p.mkdir(parents=True, exist_ok=True)
    p = caminho_treino(base_p)
    nova = not p.is_file()
    with open(p, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CABECALHO_TREINO)
        if nova:
            w.writeheader()
        w.writerow({
            "Arquivo": arquivo, "Origem": origem, "Relatorio": relatorio,
            "Filtro": "",
            "Classes": "; ".join(classes),
            "Sugestao": "; ".join(sugestao),
            "Acertou": "sim" if acertou else "nao",
            "Observacao": observacao,
        })
    registrar_classes(classes, base_p)
    guardar_dataset(origem, arquivo, relatorio, classes, base_p)


def garantir_classificacao_csv(relatorio: str, fotos: list[str],
                               base: Path | str | None = None) -> Path:
    """Cria/atualiza o classificacao.csv do relatório com as fotos da pasta.
    Fotos novas entram PENDENTE (sem sugestão por nome)."""
    base_p = Path(base) if base else BASE_CLASSIFICADAS
    pasta_rel = base_p / sanitizar_nome(relatorio)
    pasta_rel.mkdir(parents=True, exist_ok=True)
    csv_path = pasta_rel / NOME_CSV
    existentes: dict[str, dict] = {}
    if csv_path.is_file():
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if (row.get("Arquivo") or "").strip():
                    existentes[row["Arquivo"].strip()] = row
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CABECALHO_CSV)
        w.writeheader()
        for i, nome in enumerate(sorted(fotos, key=chave_natural), start=1):
            if nome in existentes:
                row = existentes[nome]
                row["Ordem"] = row.get("Ordem") or i
                w.writerow({k: row.get(k, "") for k in CABECALHO_CSV})
            else:
                w.writerow({"Arquivo": nome, "Ordem": i, "Classes": "",
                            "Status": "PENDENTE", "Observacao IA": ""})
    return csv_path


def atualizar_classificacao(relatorio: str, arquivo: str, classes: list[str],
                            observacao: str = "",
                            base: Path | str | None = None) -> None:
    """Grava as classes confirmadas no classificacao.csv do relatório."""
    base_p = Path(base) if base else BASE_CLASSIFICADAS
    csv_path = base_p / sanitizar_nome(relatorio) / NOME_CSV
    linhas: list[dict] = []
    if csv_path.is_file():
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            linhas = list(csv.DictReader(f))
    achou = False
    for row in linhas:
        if (row.get("Arquivo") or "").strip() == arquivo:
            row["Classes"] = "; ".join(classes)
            row["Status"] = "OK" if classes else "PENDENTE"
            if observacao:
                row["Observacao IA"] = observacao
            achou = True
    if not achou:
        linhas.append({"Arquivo": arquivo, "Ordem": len(linhas) + 1,
                       "Classes": "; ".join(classes),
                       "Status": "OK" if classes else "PENDENTE",
                       "Observacao IA": observacao})
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CABECALHO_CSV)
        w.writeheader()
        w.writerows(linhas)


# ============================================================
# Janela gráfica (estilo fit_fotos)
# ============================================================

def enquadrar_zoom(img, caixa_larg: int, caixa_alt: int,
                   z: float, ox: int, oy: int):
    """Foto original -> imagem da prévia com zoom (1.0 = ajustada)."""
    ow, oh = img.size
    f = min(caixa_larg / ow, caixa_alt / oh)
    bw, bh = max(1, int(ow * f)), max(1, int(oh * f))
    sw, sh = max(1, int(bw * z)), max(1, int(bh * z))
    vista = img.resize((sw, sh), Image.LANCZOS)
    if sw <= caixa_larg and sh <= caixa_alt:
        fundo = Image.new("RGB", (caixa_larg, caixa_alt), (240, 240, 240))
        fundo.paste(vista, ((caixa_larg - sw) // 2, (caixa_alt - sh) // 2))
        return fundo, f
    x0 = min(max(ox, 0), sw - caixa_larg)
    y0 = min(max(oy, 0), sh - caixa_alt)
    return vista.crop((x0, y0, x0 + caixa_larg, y0 + caixa_alt)), f


class TreinoApp(tk.Tk):
    def __init__(self, pasta_inicial: Path | None = None,
                 relatorio_inicial: str = ""):
        super().__init__()
        self.title("modo treino — valide a classificação")
        self.geometry("1020x720")
        self.minsize(880, 620)
        self.fotos: list[Path] = []
        self.visiveis: list[int] = []
        self.img_original = None
        self.zoom_z = 1.0
        self.zoom_ox = 0
        self.zoom_oy = 0
        self.sugestao_atual: list[str] = []
        self.salvas_atual: list[str] = []
        self.mostrar_chave = "todas"
        self.check_vars: dict[str, tk.BooleanVar] = {}
        self.preview_ref = None
        self.acertos = 0
        self.total_validados = 0
        self._montar()
        self._atualizar_combos()
        padrao = pasta_inicial or (RAIZ_PROJETO / "Arquivos" / "Fotos_Ordenadas")
        self.pasta_var.set(str(padrao))
        if relatorio_inicial:
            self.rel_var.set(relatorio_inicial)
        elif len(listar_relatorios(BASE_CLASSIFICADAS)) == 1:
            # Um relatório só: já seleciona ele e a pasta fotos/.
            unico = listar_relatorios(BASE_CLASSIFICADAS)[0]
            self.rel_var.set(unico)
            cand = BASE_CLASSIFICADAS / unico / PASTA_FOTOS_REL
            if cand.is_dir():
                self.pasta_var.set(str(cand))
        self.status("Selecione o relatório, carregue e valide foto a foto.")

    def _montar(self):
        self.pasta_var = tk.StringVar()
        self.rel_var = tk.StringVar()
        self.nova_classe_var = tk.StringVar()
        self.obs_var = tk.StringVar()
        self.zoom_var = tk.StringVar(value="100%")
        self.mostrar_var = tk.StringVar(value="Todas")
        self.sug_var = tk.StringVar(value="Sugestão: —")
        self.info_var = tk.StringVar(value="Nenhuma foto.")
        self.status_var = tk.StringVar(value="Pronto.")

        topo = ttk.Frame(self, padding=8)
        topo.pack(fill="x")
        ttk.Label(topo, text="Pasta:").pack(side="left")
        ttk.Entry(topo, textvariable=self.pasta_var, width=42).pack(side="left", padx=4, fill="x", expand=True)
        ttk.Button(topo, text="Procurar…", command=self.procurar_pasta).pack(side="left", padx=2)
        ttk.Button(topo, text="Carregar", command=self.carregar).pack(side="left", padx=2)

        barra_rel = ttk.Frame(self, padding=(8, 0, 8, 4))
        barra_rel.pack(fill="x")
        ttk.Label(barra_rel, text="Relatório:").pack(side="left")
        self.rel_box = ttk.Combobox(barra_rel, textvariable=self.rel_var,
                                    width=30, values=[])
        self.rel_box.pack(side="left", padx=4)
        ttk.Label(barra_rel, text="Nova classe:").pack(side="left", padx=(8, 0))
        ttk.Entry(barra_rel, textvariable=self.nova_classe_var, width=20).pack(side="left", padx=4)
        ttk.Button(barra_rel, text="Adicionar classe", command=self.adicionar_classe).pack(side="left")

        meio = ttk.Frame(self, padding=(8, 0, 8, 8))
        meio.pack(fill="both", expand=True)

        esq = ttk.Frame(meio)
        esq.pack(side="left", fill="y")
        ttk.Label(esq, text="Mostrar:").pack(anchor="w")
        self.mostrar_box = ttk.Combobox(esq, textvariable=self.mostrar_var,
                                        width=28, values=["Todas"], state="readonly")
        self.mostrar_box.pack(anchor="w", pady=(0, 4))
        self.mostrar_box.bind("<<ComboboxSelected>>", self._ao_trocar_mostrar)
        ttk.Label(esq, text="Fotos (← → navega):").pack(anchor="w")
        self.lista = tk.Listbox(esq, width=38, height=8)
        self.lista.pack(side="left", fill="y")
        self.lista.bind("<<ListboxSelect>>", self._ao_selecionar)
        rolagem = ttk.Scrollbar(esq, command=self.lista.yview)
        rolagem.pack(side="left", fill="y")
        self.lista.config(yscrollcommand=rolagem.set)

        centro = ttk.Frame(meio, padding=(12, 0, 0, 0))
        centro.pack(side="left", fill="both", expand=True)
        self.preview = ttk.Label(centro, text="(nenhuma foto)", anchor="center",
                                 relief="sunken", width=52)
        self.preview.pack(fill="both", expand=True)
        ttk.Label(centro, textvariable=self.sug_var, foreground="blue",
                  anchor="w", wraplength=520).pack(pady=1, fill="x")
        ttk.Label(centro, textvariable=self.info_var, wraplength=520,
                  anchor="w").pack(pady=1, fill="x")
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
        self.preview.bind("<MouseWheel>", self.zoom_girar)
        self.preview.bind("<ButtonPress-1>", self.zoom_iniciar_arrasto)
        self.preview.bind("<B1-Motion>", self.zoom_arrastar)
        self.preview.bind("<Configure>", lambda _e: self.render_preview())

        self.caixa_classes = ttk.LabelFrame(
            self, text="Classes (marque N por foto)", padding=8)
        self.caixa_classes.pack(fill="x", padx=8)
        self._rol_classes = ttk.Scrollbar(self.caixa_classes, orient="vertical")
        self._rol_classes.pack(side="right", fill="y")
        self._canvas_classes = tk.Canvas(self.caixa_classes, height=72,
                                         highlightthickness=0,
                                         yscrollcommand=self._rol_classes.set)
        self._canvas_classes.pack(side="left", fill="both", expand=True)
        self._rol_classes.config(command=self._canvas_classes.yview)
        self._area_classes = ttk.Frame(self._canvas_classes)
        self._jan_classes = self._canvas_classes.create_window(
            (0, 0), window=self._area_classes, anchor="nw")
        self._area_classes.bind(
            "<Configure>",
            lambda _e: self._canvas_classes.configure(
                scrollregion=self._canvas_classes.bbox("all")))
        self._canvas_classes.bind(
            "<Configure>",
            lambda e: self._canvas_classes.itemconfig(self._jan_classes, width=e.width))
        self._canvas_classes.bind_all("<MouseWheel>", self._girar_classes, add="+")
        ttk.Label(self._area_classes, text="Todas as classes:").grid(
            row=0, column=0, sticky="w")
        self._linha_classes = ttk.Frame(self._area_classes)
        self._linha_classes.grid(row=1, column=0, sticky="we")
        self._area_classes.columnconfigure(0, weight=1)
        for _c in range(6):
            self._linha_classes.columnconfigure(_c, weight=1, uniform="cls")

        acao = ttk.LabelFrame(self, text="Validação", padding=8)
        acao.pack(fill="x", padx=8, pady=8)
        ttk.Label(acao, text="Obs:").pack(side="left")
        ttk.Entry(acao, textvariable=self.obs_var, width=30).pack(side="left", padx=4)
        ttk.Button(acao, text="Acertou ✓ (Enter)",
                   command=self.acertou).pack(side="left", padx=4)
        ttk.Button(acao, text="Salvar correção",
                   command=self.salvar_correcao).pack(side="left", padx=4)
        ttk.Button(acao, text="Não identificado",
                   command=self.nao_identificado).pack(side="left", padx=4)

        ttk.Label(self, textvariable=self.status_var, relief="sunken",
                  anchor="w").pack(fill="x", side="bottom")
        self.bind("<Left>", lambda e: self.mover(-1, e))
        self.bind("<Right>", lambda e: self.mover(1, e))
        self.bind("<Return>", lambda e: self.acertou())

    # ---------- pasta / relatório ----------

    def relatorio(self) -> str:
        return self.rel_var.get().strip()

    def procurar_pasta(self):
        p = filedialog.askdirectory(title="Pasta com as fotos")
        if p:
            self.pasta_var.set(p)
            self.carregar()

    def _atualizar_combos(self):
        """Recarrega os relatórios selecionáveis (evita digitar e errar nome)."""
        self.rel_box.config(values=listar_relatorios(BASE_CLASSIFICADAS))

    def carregar(self):
        rel = self.relatorio()
        if not rel:
            messagebox.showinfo("Informe o relatório",
                                "Selecione ou digite o relatório (pasta de trabalho).")
            return
        self._atualizar_combos()
        pasta = Path(self.pasta_var.get().strip())
        if not pasta.is_absolute():
            pasta = RAIZ_PROJETO / pasta
        if not pasta.is_dir():
            self.status(f"Pasta não encontrada: '{pasta}'.")
            return
        self.fotos = listar_fotos(pasta)
        self.salvas_atual = []
        self.sugestao_atual = []
        garantir_classificacao_csv(rel, [f.name for f in self.fotos],
                                   BASE_CLASSIFICADAS)
        self._recarregar_checks()
        self.mostrar_chave = "todas"
        self._atualizar_lista()
        if self.visiveis:
            self.lista.selection_set(0)
            self._mostrar(0)
            self.status(f"{len(self.fotos)} fotos de '{pasta}' — relatório '{rel}'.")
        else:
            self.status("Nenhuma foto encontrada.")

    def _ao_trocar_mostrar(self, _evt=None):
        txt = self.mostrar_var.get()
        if txt.startswith("Não classificadas"):
            self.mostrar_chave = "aguardando"
        elif txt.startswith("Todas"):
            self.mostrar_chave = "todas"
        else:
            self.mostrar_chave = ("classe", txt.rsplit(" (", 1)[0])
        self._atualizar_lista()
        if self.visiveis:
            self.lista.selection_set(0)
            self._mostrar(0)

    def _atualizar_lista(self, manter_nome: str | None = None) -> int:
        """Reconstrói a lista de fotos (agrupada/filtrada por classe).

        Cada linha mostra a classe salva (✓). Retorna a posição selecionada.
        """
        salvas_map = ler_classificacao_relatorio(self.relatorio(), BASE_CLASSIFICADAS)
        cont: dict[str, int] = {}
        aguard = 0
        for f in self.fotos:
            cls = salvas_map.get(f.name, [])
            if cls:
                for c in cls:
                    cont[c] = cont.get(c, 0) + 1
            else:
                aguard += 1
        opcoes = [f"Todas ({len(self.fotos)})", f"Não classificadas ({aguard})"]
        for c in sorted(cont):
            opcoes.append(f"{c} ({cont[c]})")
        self.mostrar_box.config(values=opcoes)
        chave = self.mostrar_chave
        if isinstance(chave, tuple):
            nomes = [c for c in sorted(cont) if c == chave[1]]
            rotulo = f"{chave[1]} ({cont.get(chave[1], 0)})"
            self.mostrar_var.set(rotulo if nomes else opcoes[0])
            if not nomes:
                self.mostrar_chave = "todas"
        elif chave == "aguardando":
            self.mostrar_var.set(opcoes[1])
        else:
            self.mostrar_var.set(opcoes[0])
            self.mostrar_chave = "todas"
        chave = self.mostrar_chave
        self.visiveis = []
        for i, f in enumerate(self.fotos):
            cls = salvas_map.get(f.name, [])
            if chave == "todas":
                self.visiveis.append(i)
            elif chave == "aguardando":
                if not cls:
                    self.visiveis.append(i)
            elif isinstance(chave, tuple) and chave[1] in cls:
                self.visiveis.append(i)
        self.lista.delete(0, "end")
        for i in self.visiveis:
            f = self.fotos[i]
            cls = salvas_map.get(f.name, [])
            sufixo = f"  ✓ {'; '.join(cls)}" if cls else ""
            self.lista.insert("end", f.name + sufixo)
        pos = 0
        if manter_nome:
            for p, i in enumerate(self.visiveis):
                if self.fotos[i].name == manter_nome:
                    pos = p
                    break
            else:
                pos = 0
        if self.visiveis:
            self.lista.selection_clear(0, "end")
            self.lista.selection_set(pos)
            self._revelar(pos)
        return pos

    def _recarregar_checks(self):
        # Sempre parte da foto atual: salvas > sugestão. Nada da foto anterior
        # é mantido — ao trocar de foto, recomeça desmarcado (salvo sugestão).
        base_inicial = set(self.salvas_atual or self.sugestao_atual)
        for w in self._linha_classes.winfo_children():
            w.destroy()
        self.check_vars = {}
        colunas = 6
        for i, cls in enumerate(todas_classes(BASE_CLASSIFICADAS)):
            var = tk.BooleanVar(value=(cls in base_inicial))
            self.check_vars[cls] = var
            ttk.Checkbutton(self._linha_classes, text=cls,
                            variable=var).grid(row=i // colunas, column=i % colunas,
                                               sticky="w", padx=6, pady=1)
        self._canvas_classes.yview_moveto(0)
        self._area_classes.update_idletasks()
        self._canvas_classes.configure(scrollregion=self._canvas_classes.bbox("all"))

    def _girar_classes(self, evento):
        try:
            self._canvas_classes.yview_scroll(-1 * (evento.delta // 120), "units")
        except Exception:
            pass

    def adicionar_classe(self):
        nova = self.nova_classe_var.get().strip()
        if not self.relatorio():
            messagebox.showinfo("Informe o relatório", "Selecione o relatório primeiro.")
            return
        if not nova:
            return
        registrar_classes([nova], BASE_CLASSIFICADAS)
        self.nova_classe_var.set("")
        self._recarregar_checks()
        self.status(f"Classe '{nova}' criada. Selecione nas marcações (sem digitar de novo).")

    # ---------- navegação / exibição ----------

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
        self._revelar(novo)
        self._mostrar(novo)
        return "break"

    def _revelar(self, pos: int):
        """Rola até a posição travando a horizontal no início (nomes parados)."""
        self.lista.see(pos)
        self.lista.xview_moveto(0)

    def _mostrar(self, pos: int):
        if not self.visiveis:
            return
        pos = min(max(pos, 0), len(self.visiveis) - 1)
        caminho = self.fotos[self.visiveis[pos]]
        try:
            img = Image.open(caminho)
            img.load()
        except Exception as e:
            self.info_var.set(f"Erro ao abrir {caminho.name}: {e}")
            return
        self.img_original = img
        self.zoom_z, self.zoom_ox, self.zoom_oy = 1.0, 0, 0
        self.render_preview()
        rel = self.relatorio()
        self.salvas_atual = classes_salvas(caminho.name, rel, BASE_CLASSIFICADAS)
        self.sugestao_atual = sugerir_classes(caminho.name, rel, BASE_CLASSIFICADAS)
        self._recarregar_checks()
        sug_txt = "; ".join(self.sugestao_atual) if self.sugestao_atual else NAO_IDENTIFICADO
        self.sug_var.set(f"Sugestão automática: {sug_txt}")
        salvas_txt = "; ".join(self.salvas_atual) if self.salvas_atual else "—"
        self.info_var.set(f"{caminho.name} ({pos+1}/{len(self.visiveis)}) — "
                          f"{img.size[0]}x{img.size[1]} px — salvas: {salvas_txt}")

    # ---------- zoom da prévia (rodinha, botões, arrastar) ----------

    def caixa_zoom(self) -> tuple:
        """Caixa fixa da foto (tamanho de antes), limitada à área visível."""
        try:
            larg = self.preview.winfo_width()
            alt = self.preview.winfo_height()
        except Exception:
            larg, alt = 520, 340
        return min(520, max(200, larg)), min(340, max(200, alt))

    def render_preview(self):
        """Desenha a prévia com o zoom atual (1.0 = ajustada)."""
        if self.img_original is None:
            return
        larg, alt = self.caixa_zoom()
        vista, _base = enquadrar_zoom(self.img_original, larg, alt,
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

    def marcadas(self) -> list[str]:
        return [c for c, v in self.check_vars.items() if v.get()]

    # ---------- validação ----------

    def _salvar(self, classes: list[str], acertou: bool):
        rel = self.relatorio()
        if not rel or not self.visiveis:
            return
        sel = self.lista.curselection()
        pos = sel[0] if sel else 0
        pos = min(pos, len(self.visiveis) - 1)
        caminho = self.fotos[self.visiveis[pos]]
        pasta = Path(self.pasta_var.get().strip())
        registrar_exemplo(caminho.name, str(pasta), rel, classes,
                          self.sugestao_atual, acertou,
                          self.obs_var.get().strip(), BASE_CLASSIFICADAS)
        atualizar_classificacao(rel, caminho.name, classes,
                                self.obs_var.get().strip(), BASE_CLASSIFICADAS)
        self.total_validados += 1
        if acertou:
            self.acertos += 1
        self.obs_var.set("")
        self.status(f"{caminho.name} → [{'; '.join(classes) or NAO_IDENTIFICADO}] "
                    f"({'acertou' if acertou else 'corrigido'}) — "
                    f"{self.acertos}/{self.total_validados} acertos. "
                    "Próxima foto (→).")
        # Atualiza ✓ na lista e contadores; fica na mesma foto (ou próxima
        # se ela saiu do grupo filtrado).
        nova_pos = self._atualizar_lista(manter_nome=caminho.name)
        if self.visiveis:
            if self.fotos[self.visiveis[nova_pos]].name != caminho.name:
                self._mostrar(nova_pos)
            else:
                if nova_pos + 1 < len(self.visiveis):
                    self._mostrar(nova_pos + 1)
                    self.lista.selection_clear(0, "end")
                    self.lista.selection_set(nova_pos + 1)
                    self._revelar(nova_pos + 1)
                else:
                    self._mostrar(nova_pos)

    def acertou(self):
        classes = self.marcadas() or list(self.sugestao_atual) or [NAO_IDENTIFICADO]
        ok = set(classes) == set(self.sugestao_atual) and bool(self.sugestao_atual)
        self._salvar(classes, acertou=ok)

    def salvar_correcao(self):
        self._salvar(self.marcadas() or [NAO_IDENTIFICADO], acertou=False)

    def nao_identificado(self):
        if NAO_IDENTIFICADO in self.check_vars:
            self.check_vars[NAO_IDENTIFICADO].set(True)
        self._salvar([NAO_IDENTIFICADO], acertou=(self.sugestao_atual == [NAO_IDENTIFICADO]))

    def status(self, texto: str):
        self.status_var.set(f"{texto} | catálogo: {caminho_catalogo(BASE_CLASSIFICADAS)}")


def resolver_relatorio(texto: str | None) -> str:
    return (texto or "").strip()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(
        description="Modo treino: valide a sugestão automática foto a foto "
                    "(Enter=acertou). RELATÓRIO é a pasta de trabalho. Guarda "
                    "catálogo em _catalogo.json, exemplos em _treino.csv e "
                    "cópias permanentes em _dataset/<classe>/).")
    ap.add_argument("--pasta", default=None,
                    help="pasta das fotos (padrão: fotos/ do relatório se preparada, "
                         "senão Arquivos/Fotos_Ordenadas)")
    ap.add_argument("--relatorio", default="",
                    help="relatório = pasta de trabalho (ex: gna_fonte_out2026)")
    args = ap.parse_args(argv)
    rel = resolver_relatorio(args.relatorio)
    pasta = Path(args.pasta) if args.pasta else None
    if pasta is None and rel:
        try:
            from classificar_fotos import PASTA_FOTOS_REL, sanitizar_nome as _sn
        except ImportError:
            from .classificar_fotos import PASTA_FOTOS_REL, sanitizar_nome as _sn
        cand = BASE_CLASSIFICADAS / _sn(rel) / PASTA_FOTOS_REL
        if cand.is_dir():
            pasta = cand
    if pasta is not None and not pasta.is_absolute():
        pasta = RAIZ_PROJETO / pasta
    app = TreinoApp(pasta_inicial=pasta, relatorio_inicial=rel)
    app.mainloop()


if __name__ == "__main__":
    main()
