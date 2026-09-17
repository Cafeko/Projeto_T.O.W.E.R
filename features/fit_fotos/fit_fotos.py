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
import struct
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


def pedido_para_cm(larg: float, alt: float, unidade: str,
                   dpi: int = DPI_PADRAO) -> tuple[float, float]:
    """Tamanho pedido -> (larg_cm, alt_cm) para exibição."""
    if unidade == "cm":
        return larg, alt
    return larg / dpi * 2.54, alt / dpi * 2.54


def calcular_dpi(larg_px: int, alt_px: int, larg_cm: float, alt_cm: float,
                 manter_proporcao: bool = True):
    """DPI que faz a imagem original (larg_px x alt_px) ser EXIBIDA no
    tamanho pedido, sem cortar nenhum pixel. Retorna ((dpi_x, dpi_y),
    (exibe_larg_cm, exibe_alt_cm)). Com proporção o DPI é uniforme."""
    if manter_proporcao:
        f = min(larg_cm / larg_px, alt_cm / alt_px)
        dw, dh = larg_px * f, alt_px * f
    else:
        dw, dh = larg_cm, alt_cm
    return (larg_px / dw * 2.54, alt_px / dh * 2.54), (dw, dh)


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


def imagem_para_dib(img: Image.Image, dpi: tuple[float, float] | None = None) -> bytes:
    """Imagem -> bytes DIB prontos p/ o clipboard. Com dpi=(dx, dy), grava
    pixels-por-metro no cabeçalho para o Excel exibir no tamanho certo."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "BMP")
    dados = bytearray(buf.getvalue())
    buf.close()
    if dpi is not None:
        struct.pack_into("<i", dados, 38, int(round(dpi[0] / 0.0254)))
        struct.pack_into("<i", dados, 42, int(round(dpi[1] / 0.0254)))
    return bytes(dados[14:])  # tira o cabecalho BMP, sobra o DIB


def dpi_fisico_tela() -> tuple[float, float]:
    """DPI físico real da tela (px/mm do monitor). Diferente do lógico 96:
    é ele que o Excel usa para dimensionar o EMF (telas ~101dpi a 100%)."""
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    gdi32.GetDeviceCaps.restype = ctypes.c_int
    gdi32.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
    hdc = user32.GetDC(None)
    try:
        hr, vr = gdi32.GetDeviceCaps(hdc, 8), gdi32.GetDeviceCaps(hdc, 10)
        hs, vs = gdi32.GetDeviceCaps(hdc, 4), gdi32.GetDeviceCaps(hdc, 6)
    finally:
        user32.ReleaseDC(None, hdc)
    if hr <= 0 or vr <= 0 or hs <= 0 or vs <= 0:
        return (96.0, 96.0)
    return (hr / hs * 25.4, vr / vs * 25.4)


def criar_emf(img: Image.Image, larg_cm: float, alt_cm: float):
    """Cria um HANDLE de EMF via GDI: foto em resolução TOTAL num quadro que
    o Excel exibe EXATAMENTE no tamanho pedido (compensa o DPI físico da
    tela, que o Excel usa como referência). Dá para ampliar/imprimir sem
    pixelar.

    Retorna o HANDLE: quem recebe passa ao clipboard (vira dono) ou libera
    com gdi32.DeleteEnhMetaFile."""
    from ctypes import wintypes
    gdi32 = ctypes.windll.gdi32
    gdi32.CreateEnhMetaFileW.restype = wintypes.HDC
    gdi32.CreateEnhMetaFileW.argtypes = [wintypes.HDC, wintypes.LPCWSTR,
                                         ctypes.POINTER(ctypes.c_long),
                                         wintypes.LPCWSTR]
    gdi32.StretchDIBits.restype = ctypes.c_int
    gdi32.StretchDIBits.argtypes = [wintypes.HDC,
                                    ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int,
                                    ctypes.c_void_p, ctypes.c_void_p,
                                    wintypes.UINT, wintypes.DWORD]
    gdi32.CloseEnhMetaFile.restype = wintypes.HANDLE
    gdi32.CloseEnhMetaFile.argtypes = [wintypes.HDC]
    gdi32.DeleteEnhMetaFile.restype = wintypes.BOOL
    gdi32.DeleteEnhMetaFile.argtypes = [wintypes.HANDLE]

    dib = imagem_para_dib(img, None)  # bmi (40) + bits (BGR, de baixo p/ cima)
    bmi, bits = dib[:40], dib[40:]
    buf_bmi = ctypes.create_string_buffer(bmi)
    buf_bits = ctypes.create_string_buffer(bits)
    W, H = img.size
    # Destino em px "96dpi" + quadro encolhido por 96/fisico: o conteúdo
    # preenche o quadro e o Excel exibe no tamanho pedido exato.
    fdx, fdy = dpi_fisico_tela()
    dw, dh = int(round(larg_cm / 2.54 * 96)), int(round(alt_cm / 2.54 * 96))
    fx, fy = int(round(larg_cm * 1000 * 96 / fdx)), int(round(alt_cm * 1000 * 96 / fdy))
    rect = (ctypes.c_long * 4)(0, 0, fx, fy)
    hdc = gdi32.CreateEnhMetaFileW(None, None, rect, None)
    if not hdc:
        raise RuntimeError("Falha ao criar EMF.")
    try:
        n = gdi32.StretchDIBits(hdc, 0, 0, dw, dh, 0, 0, W, H,
                                buf_bits, buf_bmi, 0, 0x00CC0020)
        if n <= 0:
            raise RuntimeError("Falha ao desenhar no EMF.")
    except Exception:
        hemf = gdi32.CloseEnhMetaFile(hdc)
        if hemf:
            gdi32.DeleteEnhMetaFile(hemf)
        raise
    hemf = gdi32.CloseEnhMetaFile(hdc)
    if not hemf:
        raise RuntimeError("Falha ao fechar EMF.")
    return hemf


def copiar_para_clipboard(img: Image.Image,
                           dpi: tuple[float, float] | None = None,
                           tamanho_emf_cm: tuple[float, float] | None = None) -> None:
    """Copia a imagem para a area de transferencia (Windows) — pronta para
    colar no Excel com Ctrl+V. Com tamanho_emf_cm=(larg_cm, alt_cm), cola
    também um EMF (foto full-res + quadro no tamanho): o Excel exibe no
    tamanho certo sem cortar pixels; o bitmap vai junto como reserva."""
    if os.name != "nt":
        raise RuntimeError("Copiar p/ clipboard so funciona no Windows.")
    dib = imagem_para_dib(img, dpi)
    CF_DIB, CF_EMF, GMEM_MOVEABLE = 8, 14, 2
    from ctypes import wintypes
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
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
    gdi32.DeleteEnhMetaFile.restype = wintypes.BOOL
    gdi32.DeleteEnhMetaFile.argtypes = [wintypes.HANDLE]

    def alocar(conteudo: bytes):
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(conteudo))
        if not h_mem:
            raise RuntimeError("Falha ao alocar memoria do clipboard.")
        ptr = kernel32.GlobalLock(h_mem)
        ctypes.memmove(ptr, conteudo, len(conteudo))
        kernel32.GlobalUnlock(h_mem)
        return h_mem

    # HANDLE do EMF criado pela GDI (não é bloco de memória).
    hemf = None
    if tamanho_emf_cm is not None:
        hemf = criar_emf(img, *tamanho_emf_cm)
    try:
        if not user32.OpenClipboard(None):
            raise RuntimeError("Nao abri o clipboard (feche o Excel e tente de novo).")
        user32.EmptyClipboard()
        h_dib = alocar(dib)
        if not user32.SetClipboardData(CF_DIB, h_dib):
            kernel32.GlobalFree(h_dib)
            raise RuntimeError("Falha ao copiar para o clipboard.")
        # dono do h_dib agora é o clipboard — não liberar
        if hemf:
            if not user32.SetClipboardData(CF_EMF, hemf):
                raise RuntimeError("Falha ao copiar EMF para o clipboard.")
            hemf = None  # dono agora é o clipboard — não deletar
    finally:
        user32.CloseClipboard()
        if hemf:
            gdi32.DeleteEnhMetaFile(hemf)


def salvar_copia(img: Image.Image, destino: Path,
                 dpi: tuple[float, float] | None = None) -> None:
    """Salva a imagem. Com dpi (jpg/png/tif), grava a resolução para o
    Excel exibir no tamanho certo ao inserir, sem cortar pixels."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.suffix.lower() in (".jpg", ".jpeg") and img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    if dpi is not None and destino.suffix.lower() in (".jpg", ".jpeg", ".png", ".tif", ".tiff"):
        img.save(destino, dpi=(round(dpi[0]), round(dpi[1])))
    else:
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
        self.alta_var = tk.BooleanVar(value=True)
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
                        variable=self.proporcao_var,
                        command=self.atualizar_px).grid(row=1, column=0, columnspan=5,
                                                        sticky="w", pady=(4, 0))
        ttk.Label(ctrl, textvariable=self.px_var, foreground="gray").grid(
            row=1, column=5, columnspan=3, sticky="e")
        ttk.Checkbutton(ctrl, text="Alta resolução (exibe no tamanho sem perder qualidade)",
                        variable=self.alta_var,
                        command=self.atualizar_px).grid(row=2, column=0, columnspan=8,
                                                        sticky="w")
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

    def ler_pedido(self):
        """Lê os campos de tamanho. Retorna (larg, alt, unidade, dpi) ou None."""
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
                                   "Digite largura, altura (e DPI) maiores que zero.")
            return None
        return larg, alt, unidade, dpi

    def ler_tamanho(self) -> tuple[int, int] | None:
        pedido = self.ler_pedido()
        if pedido is None:
            return None
        larg, alt, unidade, dpi = pedido
        return converter_tamanho(larg, alt, unidade, dpi)

    def atualizar_px(self):
        try:
            larg = float(self.larg_var.get().replace(",", "."))
            alt = float(self.alt_var.get().replace(",", "."))
            dpi = int(self.dpi_var.get())
            unidade = self.unidade_var.get()
            if self.alta_var.get() and self.img_original is not None:
                ow, oh = self.img_original.size
                lw, lh = pedido_para_cm(larg, alt, unidade, dpi)
                (dx, _dy), (dw, dh) = calcular_dpi(ow, oh, lw, lh,
                                                   self.proporcao_var.get())
                self.px_var.set(f"= exibe {dw:.1f} x {dh:.1f} cm (DPI {dx:.0f})")
                self.info_var.set(f"{self.img_nome} — {ow}x{oh} px em alta, "
                                  f"exibe {dw:.1f}x{dh:.1f} cm")
                return
            w, h = converter_tamanho(larg, alt, unidade, dpi)
            uni = f" (DPI {dpi})" if unidade == "cm" else ""
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
                self.status(f"{self.img_nome} copiada em alta ({ow}x{oh} px, "
                            f"exibe {dw:.1f}x{dh:.1f} cm) — cole no Excel com Ctrl+V.")
            else:
                w, h = converter_tamanho(larg, alt, unidade, dpi_base)
                final = redimensionar(self.img_original, w, h,
                                      self.proporcao_var.get())
                copiar_para_clipboard(final)
                self.status(f"{self.img_nome} copiada ({final.size[0]}x{final.size[1]} px) — cole no Excel com Ctrl+V.")
        except Exception as e:
            messagebox.showerror("Erro ao copiar", str(e))
            return

    def salvar_todas(self):
        if not self.fotos:
            messagebox.showinfo("Nada a salvar", "Carregue uma pasta com fotos primeiro.")
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
        for caminho in self.fotos:
            try:
                with Image.open(caminho) as img:
                    img.load()
                    if alta:
                        lw, lh = pedido_para_cm(larg, alt, unidade, dpi_base)
                        (dx, dy), _exibe = calcular_dpi(*img.size, lw, lh,
                                                        self.proporcao_var.get())
                        salvar_copia(img, destino / caminho.name, dpi=(dx, dy))
                    else:
                        w, h = converter_tamanho(larg, alt, unidade, dpi_base)
                        salvar_copia(redimensionar(img, w, h,
                                                   self.proporcao_var.get()),
                                     destino / caminho.name)
                ok += 1
            except Exception:
                erros += 1
        modo = " em alta" if alta else ""
        self.status(f"Salvas {ok} fotos{modo} em '{destino}'" + (f" ({erros} erros)." if erros else "."))
        if erros:
            messagebox.showwarning("Concluído com erros",
                                   f"{ok} salvas, {erros} com erro. Veja a barra de status.")


def extrair_pasta(argv=None) -> str | None:
    """Extrai o caminho da pasta de argv, tolerando caminho com espaços
    que chegou quebrado (sem aspas): junta os fragmentos com espaço.

    Ex: --pasta C:\\Minhas Fotos\\X vira "C:\\Minhas Fotos\\X".
    Flags desconhecidas (--xyz) continuam dando erro."""
    ap = argparse.ArgumentParser(
        description="fit_fotos: veja as fotos, escolha o tamanho (px ou cm) e "
                    "copie p/ o Excel ou salve redimensionadas.")
    ap.add_argument("--pasta", default=None,
                    help="pasta das fotos para já abrir nela "
                         "(absoluta ou relativa à raiz do projeto)")
    ap.add_argument("fragmentos", nargs="*", help=argparse.SUPPRESS)
    args, sobras = ap.parse_known_args(argv)
    estranhos = [s for s in sobras if s.startswith("-")]
    if estranhos:
        ap.error(f"argumentos desconhecidos: {' '.join(estranhos)}")
    partes = ([args.pasta] if args.pasta else []) + (args.fragmentos or []) \
        + [s for s in sobras if not s.startswith("-")]
    return " ".join(partes) or None


def main(argv=None) -> None:
    app = FitFotosApp(pasta_inicial=resolver_pasta(extrair_pasta(argv)))
    app.mainloop()


if __name__ == "__main__":
    main()
