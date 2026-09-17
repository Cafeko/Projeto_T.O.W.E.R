"""fit_fotos — fotos no tamanho certo para colar no Excel.

Janela grafica: olhe as fotos de uma pasta, escolha o tamanho (px ou cm,
como no Excel) e copie para a area de transferencia ou salve redimensionadas.

Uso humano (janela):
    python features/fit_fotos/fit_fotos.py
    python features/fit_fotos/fit_fotos.py --pasta Arquivos/Fotos

Uso via agente externo: o agente SO abre o programa para o usuario
(ver features/fit_fotos/AGENTS.md). Opcionalmente passa --pasta para o
programa ja abrir direto na pasta das fotos.

Rode sempre a partir da RAIZ do projeto.
"""

from __future__ import annotations

import argparse
import ctypes
import io
import os
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

# Raiz do projeto = 2 niveis acima deste script (features/fit_fotos/ -> raiz).
RAIZ_PROJETO = Path(__file__).resolve().parents[2]

EXTENSOES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
DPI_PADRAO = 96  # DPI de tela do Windows (base do "cm" do Excel)
PASTA_SAIDA_PADRAO = RAIZ_PROJETO / "Arquivos" / "Fotos_Fit"


# ============================================================
# Logica pura (sem GUI — testavel)
# ============================================================

def cm_para_px(cm: float, dpi: int = DPI_PADRAO) -> int:
    """Converte cm em pixels (mesma conta do tamanho em cm do Excel)."""
    return max(1, round(cm / 2.54 * dpi))


def converter_tamanho(larg: float, alt: float, unidade: str,
                      dpi: int = DPI_PADRAO) -> tuple[int, int]:
    """(largura, altura) pedidas -> (w_px, h_px). Unidade: 'px' ou 'cm'."""
    if unidade == "cm":
        return cm_para_px(larg, dpi), cm_para_px(alt, dpi)
    return max(1, int(larg)), max(1, int(alt))


def chave_natural(nome: str) -> list:
    """Chave de ordenação natural: números valem pelo valor, não pela letra.

    Detecta qualquer numeração no nome — 'Foto (2)' < 'Foto (10)',
    'foto2.jpg' < 'foto10.jpg', '02 - x.jpg' < '10 - x.jpg' — sem precisar
    configurar formato.
    """
    return [int(p) if p.isdigit() else p
            for p in re.split(r"(\d+)", nome.lower())]


def listar_fotos(pasta: Path) -> list[Path]:
    """Retorna as imagens da pasta em ordem natural (Foto (2) antes de
    Foto (10), independente do formato da numeração)."""
    pasta = Path(pasta)
    if not pasta.is_dir():
        return []
    return sorted((p for p in pasta.iterdir()
                   if p.is_file() and p.suffix.lower() in EXTENSOES),
                  key=lambda p: chave_natural(p.name))


def redimensionar(img: Image.Image, larg_px: int, alt_px: int,
                  manter_proporcao: bool = True) -> Image.Image:
    """Redimensiona. Com proporcao: encaixa dentro de larg x alt sem
    distorcer. Sem proporcao: forca o tamanho exato (distorce)."""
    if manter_proporcao:
        copia = img.copy()
        copia.thumbnail((larg_px, alt_px), Image.LANCZOS)
        return copia
    return img.resize((larg_px, alt_px), Image.LANCZOS)


def copiar_para_clipboard(img: Image.Image) -> None:
    """Copia a imagem para a area de transferencia (Windows, CF_DIB) —
    pronta para colar no Excel com Ctrl+V."""
    if os.name != "nt":
        raise RuntimeError("Copiar p/ clipboard so funciona no Windows.")
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "BMP")
    dados = buf.getvalue()[14:]  # tira o cabecalho BMP, sobra o DIB
    buf.close()
    CF_DIB, GMEM_MOVEABLE = 8, 2
    from ctypes import wintypes
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    # Sem restype/argtypes o ctypes trunca ponteiros 64-bit (vira int 32-bit).
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.CloseClipboard.restype = wintypes.BOOL
    h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(dados))
    if not h_mem:
        raise RuntimeError("Falha ao alocar memoria do clipboard.")
    ptr = kernel32.GlobalLock(h_mem)
    ctypes.memmove(ptr, dados, len(dados))
    kernel32.GlobalUnlock(h_mem)
    try:
        if not user32.OpenClipboard(None):
            raise RuntimeError("Nao abri o clipboard (feche o Excel e tente de novo).")
        user32.EmptyClipboard()
        if not user32.SetClipboardData(CF_DIB, h_mem):
            raise RuntimeError("Falha ao copiar para o clipboard.")
        h_mem = None  # dono agora e o clipboard — nao liberar
    finally:
        user32.CloseClipboard()
        if h_mem:
            kernel32.GlobalFree(h_mem)


def salvar_copia(img: Image.Image, destino: Path) -> None:
    """Salva a imagem redimensionada (converte p/ RGB se o formato pedir)."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.suffix.lower() in (".jpg", ".jpeg") and img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    img.save(destino)


def resolver_pasta(texto: str | None) -> Path | None:
    """Resolve --pasta: absoluto vale como esta, relativo e contra a raiz."""
    if not texto:
        return None
    p = Path(texto.strip().strip('"').strip("'")).expanduser()
    if not p.is_absolute():
        p = RAIZ_PROJETO / p
    return p


# ============================================================
# Janela grafica
# ============================================================

class FitFotosApp(tk.Tk):
    def __init__(self, pasta_inicial: Path | None = None):
        super().__init__()
        self.title("fit_fotos — fotos no tamanho do Excel")
        self.geometry("900x600")
        self.fotos: list[Path] = []
        self.img_original: Image.Image | None = None
        self.img_nome: str = ""
        self.preview_ref = None  # guarda o PhotoImage (evita garbage collector)

        self._montar()
        padrao = pasta_inicial or (RAIZ_PROJETO / "Arquivos" / "Fotos")
        if padrao.is_dir():
            self.pasta_var.set(str(padrao))
            self.carregar_pasta()

    # ---------- montagem ----------

    def _montar(self):
        self.pasta_var = tk.StringVar()
        self.larg_var = tk.StringVar(value="6")
        self.alt_var = tk.StringVar(value="4")
        self.unidade_var = tk.StringVar(value="cm")
        self.dpi_var = tk.StringVar(value=str(DPI_PADRAO))
        self.proporcao_var = tk.BooleanVar(value=True)
        self.destino_var = tk.StringVar(value=str(PASTA_SAIDA_PADRAO))
        self.info_var = tk.StringVar(value="Escolha a pasta das fotos.")
        self.px_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Pronto.")

        topo = ttk.Frame(self, padding=8)
        topo.pack(fill="x")
        ttk.Label(topo, text="Pasta:").pack(side="left")
        ttk.Entry(topo, textvariable=self.pasta_var, width=60).pack(side="left", padx=4, fill="x", expand=True)
        ttk.Button(topo, text="Procurar…", command=self.procurar_pasta).pack(side="left", padx=2)
        ttk.Button(topo, text="Carregar", command=self.carregar_pasta).pack(side="left", padx=2)

        meio = ttk.Frame(self, padding=(8, 0, 8, 8))
        meio.pack(fill="both", expand=True)

        esq = ttk.Frame(meio)
        esq.pack(side="left", fill="y")
        ttk.Label(esq, text="Fotos (← → navega):").pack(anchor="w")
        self.lista = tk.Listbox(esq, width=32, height=20)
        self.lista.pack(side="left", fill="y")
        self.lista.bind("<<ListboxSelect>>", self._ao_selecionar)
        rolagem = ttk.Scrollbar(esq, command=self.lista.yview)
        rolagem.pack(side="left", fill="y")
        self.lista.config(yscrollcommand=rolagem.set)

        dir_ = ttk.Frame(meio, padding=(12, 0, 0, 0))
        dir_.pack(side="left", fill="both", expand=True)
        self.preview = ttk.Label(dir_, text="(nenhuma foto)", anchor="center",
                                 relief="sunken", width=60)
        self.preview.pack(fill="both", expand=True)
        ttk.Label(dir_, textvariable=self.info_var, wraplength=500).pack(pady=4)

        ctrl = ttk.LabelFrame(self, text="Tamanho desejado", padding=8)
        ctrl.pack(fill="x", padx=8)
        ttk.Label(ctrl, text="Largura:").grid(row=0, column=0, sticky="e")
        ttk.Entry(ctrl, textvariable=self.larg_var, width=8).grid(row=0, column=1, padx=4)
        ttk.Label(ctrl, text="Altura:").grid(row=0, column=2, sticky="e")
        ttk.Entry(ctrl, textvariable=self.alt_var, width=8).grid(row=0, column=3, padx=4)
        ttk.Radiobutton(ctrl, text="cm (Excel)", variable=self.unidade_var,
                        value="cm", command=self.atualizar_px).grid(row=0, column=4, padx=4)
        ttk.Radiobutton(ctrl, text="px", variable=self.unidade_var,
                        value="px", command=self.atualizar_px).grid(row=0, column=5, padx=4)
        ttk.Label(ctrl, text="DPI:").grid(row=0, column=6, sticky="e", padx=(8, 0))
        self.dpi_entry = ttk.Entry(ctrl, textvariable=self.dpi_var, width=6)
        self.dpi_entry.grid(row=0, column=7, padx=4)
        ttk.Checkbutton(ctrl, text="Manter proporção (sem distorcer)",
                        variable=self.proporcao_var).grid(row=1, column=0, columnspan=5,
                                                          sticky="w", pady=(4, 0))
        ttk.Label(ctrl, textvariable=self.px_var, foreground="gray").grid(
            row=1, column=5, columnspan=3, sticky="e")
        for v in (self.larg_var, self.alt_var, self.dpi_var):
            v.trace_add("write", lambda *a: self.atualizar_px())

        saidas = ttk.LabelFrame(self, text="Saída", padding=8)
        saidas.pack(fill="x", padx=8, pady=8)
        ttk.Label(saidas, text="Salvar em:").pack(side="left")
        ttk.Entry(saidas, textvariable=self.destino_var, width=45).pack(side="left", padx=4, fill="x", expand=True)
        ttk.Button(saidas, text="Procurar…", command=self.procurar_destino).pack(side="left", padx=2)
        ttk.Button(saidas, text="Copiar selecionada (Ctrl+C)",
                   command=self.copiar_selecionada).pack(side="left", padx=8)
        ttk.Button(saidas, text="Salvar todas",
                   command=self.salvar_todas).pack(side="left", padx=2)

        ttk.Label(self, textvariable=self.status_var, relief="sunken",
                  anchor="w").pack(fill="x", side="bottom")
        self.bind("<Control-c>", lambda e: self.copiar_selecionada())
        self.bind("<Left>", lambda e: self.mover_foto(-1, e))
        self.bind("<Right>", lambda e: self.mover_foto(1, e))

    # ---------- pasta / lista ----------

    def procurar_pasta(self):
        p = filedialog.askdirectory(title="Pasta com as fotos")
        if p:
            self.pasta_var.set(p)
            self.carregar_pasta()

    def procurar_destino(self):
        p = filedialog.askdirectory(title="Pasta de saída")
        if p:
            self.destino_var.set(p)

    def carregar_pasta(self):
        pasta = Path(self.pasta_var.get().strip().strip('"').strip("'"))
        if not pasta.is_absolute():
            pasta = RAIZ_PROJETO / pasta
        fotos = listar_fotos(pasta)
        self.fotos = fotos
        self.lista.delete(0, "end")
        for f in fotos:
            self.lista.insert("end", f.name)
        if fotos:
            self.lista.selection_set(0)
            self._mostrar(fotos[0])
            self.status(f"{len(fotos)} fotos em '{pasta}'.")
        else:
            self.img_original = None
            self.preview.config(image="", text="(nenhuma foto)")
            self.info_var.set(f"Nenhuma imagem em '{pasta}'.")
            self.status("Nenhuma foto encontrada.")

    def _ao_selecionar(self, _evt=None):
        sel = self.lista.curselection()
        if sel:
            self._mostrar(self.fotos[sel[0]])

    def mover_foto(self, delta: int, evento=None):
        """Passa para a anterior (delta=-1, seta ←) ou próxima (delta=+1,
        seta →). Ignora se o foco está num campo de texto, para não roubar
        as setas da digitação."""
        if evento is not None and isinstance(
                evento.widget, (tk.Entry, ttk.Entry, tk.Text)):
            return None
        if not self.fotos:
            return None
        sel = self.lista.curselection()
        idx = sel[0] if sel else (0 if delta > 0 else len(self.fotos) - 1)
        novo = min(max(idx + delta, 0), len(self.fotos) - 1)
        self.lista.selection_clear(0, "end")
        self.lista.selection_set(novo)
        self.lista.see(novo)
        self._mostrar(self.fotos[novo])
        return "break"

    def _mostrar(self, caminho: Path):
        try:
            self.img_original = Image.open(caminho)
            self.img_original.load()
        except Exception as e:
            self.info_var.set(f"Erro ao abrir {caminho.name}: {e}")
            return
        self.img_nome = caminho.name
        prev = self.img_original.copy()
        prev.thumbnail((560, 380), Image.LANCZOS)
        self.preview_ref = ImageTk.PhotoImage(prev)
        self.preview.config(image=self.preview_ref, text="")
        self.atualizar_px()

    # ---------- tamanho ----------

    def ler_tamanho(self) -> tuple[int, int] | None:
        try:
            larg = float(self.larg_var.get().replace(",", "."))
            alt = float(self.alt_var.get().replace(",", "."))
            dpi = int(self.dpi_var.get()) if self.unidade_var.get() == "cm" else DPI_PADRAO
            if larg <= 0 or alt <= 0 or dpi <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Tamanho inválido",
                                   "Digite largura, altura (e DPI) maiores que zero.")
            return None
        return converter_tamanho(larg, alt, self.unidade_var.get(), dpi)

    def atualizar_px(self):
        try:
            larg = float(self.larg_var.get().replace(",", "."))
            alt = float(self.alt_var.get().replace(",", "."))
            dpi = int(self.dpi_var.get())
            w, h = converter_tamanho(larg, alt, self.unidade_var.get(), dpi)
            uni = f" (DPI {dpi})" if self.unidade_var.get() == "cm" else ""
            self.px_var.set(f"= {w} x {h} px{uni}")
            if self.img_original is not None:
                ow, oh = self.img_original.size
                self.info_var.set(f"{self.img_nome} — original {ow}x{oh} px → saída {w}x{h} px")
        except ValueError:
            self.px_var.set("")

    def status(self, texto: str):
        self.status_var.set(texto)

    # ---------- acoes ----------

    def copiar_selecionada(self):
        if self.img_original is None:
            messagebox.showinfo("Nada a copiar", "Carregue uma pasta e selecione uma foto.")
            return
        tam = self.ler_tamanho()
        if tam is None:
            return
        try:
            final = redimensionar(self.img_original, *tam, self.proporcao_var.get())
            copiar_para_clipboard(final)
        except Exception as e:
            messagebox.showerror("Erro ao copiar", str(e))
            return
        self.status(f"{self.img_nome} copiada ({final.size[0]}x{final.size[1]} px) — cole no Excel com Ctrl+V.")

    def salvar_todas(self):
        if not self.fotos:
            messagebox.showinfo("Nada a salvar", "Carregue uma pasta com fotos primeiro.")
            return
        tam = self.ler_tamanho()
        if tam is None:
            return
        destino = Path(self.destino_var.get().strip())
        if not destino.is_absolute():
            destino = RAIZ_PROJETO / destino
        ok, erros = 0, 0
        for caminho in self.fotos:
            try:
                with Image.open(caminho) as img:
                    img.load()
                    final = redimensionar(img, *tam, self.proporcao_var.get())
                    salvar_copia(final, destino / caminho.name)
                ok += 1
            except Exception:
                erros += 1
        self.status(f"Salvas {ok} fotos em '{destino}'" + (f" ({erros} erros)." if erros else "."))
        if erros:
            messagebox.showwarning("Concluído com erros",
                                   f"{ok} salvas, {erros} com erro. Veja a barra de status.")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(
        description="fit_fotos: veja as fotos, escolha o tamanho (px ou cm) e "
                    "copie p/ o Excel ou salve redimensionadas.")
    ap.add_argument("--pasta", default=None,
                    help="pasta das fotos para já abrir nela "
                         "(absoluta ou relativa à raiz do projeto)")
    args = ap.parse_args(argv)
    app = FitFotosApp(pasta_inicial=resolver_pasta(args.pasta))
    app.mainloop()


if __name__ == "__main__":
    main()
