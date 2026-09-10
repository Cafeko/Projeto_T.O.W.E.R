import base64
import csv
import re
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image  # apenas para validar imagem

# ============================================================
# CONFIGURACAO
# ============================================================

PASTA_FOTOS = Path("Arquivos/fotos")
ARQUIVO_RESULTADO = Path("Arquivos/resultado.csv")
MODELO_IA = "qwen2.5vl:3b"  # ollama pull qwen2.5vl:3b
OLLAMA_URL = "http://localhost:11434/api/generate"

EXTENSOES_IMAGENS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

PROMPT = (
    "Transcribe the timestamp text visible at the bottom of this image. "
    "The timestamp looks like 'quarta-feira, 9 de setembro de 2026 17:58:53'. "
    "Reply with the exact text you see."
)

# ============================================================
# PARSE DA RESPOSTA DA IA (formato unico)
# ============================================================

def limpar_texto_ia(texto: str) -> str:
    """Remove coordenadas e lixo que a IA as vezes inclui: '7,6579S 40,1581W ...'."""
    # remove linha com coordenadas GPS
    texto = re.sub(r"\d+[.,]\d+\s*[NS]\s*\d+[.,]\d+\s*[WE].*", "", texto, flags=re.IGNORECASE)
    # remove linhas com endereco / Brasil / PE-630
    texto = re.sub(r"Francisco.*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"PE-?\d+.*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"#PII?.*", "", texto)
    return texto.strip()

def parse_data(texto: str):
    """Converte varios formatos (DD/MM/AAAA ou '9 de setembro de 2026') em datetime."""
    texto = limpar_texto_ia(texto)
    t = texto.strip().lower()
    if "nao encontrada" in t or "não encontrada" in t or not t:
        return None

    # 1) DD/MM/AAAA HH:MM:SS (formato unico normalizado)
    m = re.search(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})", texto)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), int(m.group(4)), int(m.group(5)), int(m.group(6)))
        except ValueError:
            pass

    # 2) DD/MM/AAAA sem hora
    m = re.search(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})", texto)
    if m:
        mh = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", texto)
        h, mi, s = 0, 0, 0
        if mh:
            h, mi = int(mh.group(1)), int(mh.group(2))
            s = int(mh.group(3)) if mh.group(3) else 0
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), h, mi, s)
        except ValueError:
            pass

    # 3) 9 de setembro de 2026 15:15:55 (formato do carimbo)
    for nome, num in MESES.items():
        pad = re.compile(rf"(\d{{1,2}})\s+(?:de\s+)?{nome}\s+(?:de\s+)?(\d{{4}})", re.IGNORECASE)
        r = pad.search(texto)
        if r:
            dia, ano = int(r.group(1)), int(r.group(2))
            resto = texto[r.end():]
            mh = re.search(r"(\d{1,2}):(\d{2}):(\d{2})(?:[.,](\d{1,6}))?", resto)
            if mh:
                h, mi, s = int(mh.group(1)), int(mh.group(2)), int(mh.group(3))
                micro = int((mh.group(4) or "").ljust(6, "0")) if mh.group(4) else 0
            else:
                h = mi = s = micro = 0
            try:
                return datetime(ano, num, dia, h, mi, s, micro)
            except ValueError:
                continue
    return None

# ============================================================
# CONSULTA OLLAMA
# ============================================================

def imagem_para_base64(caminho: Path) -> str:
    # Reduz para 896px max - qwen/moonDream falham com 1200x1600 direto (gera @@@)
    # e fica 3x mais rapido
    import io
    with Image.open(caminho) as im:
        im.thumbnail((896, 896))
        # converte para JPEG para reduzir base64
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

def consultar_ia(caminho: Path) -> tuple[str, datetime | None]:
    """Envia imagem para Ollama (modelo generico) e retorna (texto_ia, datetime)."""
    try:
        b64 = imagem_para_base64(caminho)
    except Exception as e:
        return f"ERRO ao ler imagem: {e}", None

    payload = {
        "model": MODELO_IA,
        "prompt": PROMPT,
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 60},
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
    except requests.exceptions.ConnectionError:
        return "ERRO: Ollama nao esta rodando. Execute 'ollama serve' no terminal.", None
    except Exception as e:
        return f"ERRO de conexao: {e}", None

    if resp.status_code != 200:
        return f"ERRO Ollama {resp.status_code}: {resp.text[:200]}", None

    try:
        data = resp.json()
        texto = data.get("response", "").strip()
    except Exception as e:
        return f"ERRO ao decodificar resposta: {e}", None

    dt = parse_data(texto)
    return texto, dt

# ============================================================
# PROCESSAR / CSV / MAIN
# ============================================================

def descarregar_modelo():
    """Descarrega o modelo da RAM/VRAM apos terminar."""
    try:
        requests.post(OLLAMA_URL, json={"model": MODELO_IA, "keep_alive": 0}, timeout=5)
        print(f"Modelo {MODELO_IA} descarregado da memoria.")
    except Exception:
        pass

def processar_foto(caminho: Path, idx: int = 0, total: int = 0):
    prefix = f"{idx}/{total} - " if total else ""
    print(f"{prefix}Processando: {caminho.name}")
    texto, dt = consultar_ia(caminho)
    if texto.startswith("ERRO"):
        resultado = {"arquivo": caminho.name, "caminho": str(caminho), "texto": texto, "data_hora": None, "status": texto}
    else:
        if dt is not None:
            texto_limpo = dt.strftime("%d/%m/%Y %H:%M:%S.%f")[:-3]
        else:
            texto_limpo = limpar_texto_ia(texto)
        status = "OK" if dt is not None else "DATA NÃO ENCONTRADA"
        resultado = {"arquivo": caminho.name, "caminho": str(caminho), "texto": texto_limpo, "data_hora": dt, "status": status}
    # feedback imediato com progresso
    dt_txt = resultado["data_hora"].strftime("%d/%m/%Y %H:%M:%S.%f")[:-3] if resultado["data_hora"] else "NÃO ENCONTRADA"
    print(f"  -> {idx}/{total} - {caminho.name} {dt_txt} {resultado['status']}")
    return resultado

def salvar_csv(resultados):
    ARQUIVO_RESULTADO.parent.mkdir(parents=True, exist_ok=True)
    with open(ARQUIVO_RESULTADO, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Arquivo", "Data", "Hora", "Data/Hora", "Status", "Texto IA"])
        for r in resultados:
            dt = r["data_hora"]
            if dt:
                data = dt.strftime("%d/%m/%Y")
                hora = dt.strftime("%H:%M:%S.%f")[:-3]
                dth = dt.strftime("%d/%m/%Y %H:%M:%S.%f")[:-3]
            else:
                data = hora = dth = ""
            w.writerow([r["arquivo"], data, hora, dth, r["status"], r["texto"]])

def mostrar_resultados(resultados):
    print()
    print("=" * 90)
    print("RESULTADO (IA Local)")
    print("=" * 90)
    for r in resultados:
        dt = r["data_hora"]
        txt = dt.strftime("%d/%m/%Y %H:%M:%S.%f")[:-3] if dt else "NÃO ENCONTRADA"
        print(f"{r['arquivo']:<40} {txt:<25} {r['status']}")
    print("=" * 90)

def verificar_ollama():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            modelos = [m["name"] for m in r.json().get("models", [])]
            if not any(MODELO_IA in m for m in modelos):
                print(f"Aviso: modelo '{MODELO_IA}' nao encontrado. Baixe com: ollama pull {MODELO_IA}")
                print(f"Modelos instalados: {modelos if modelos else 'nenhum'}")
            else:
                print(f"Ollama OK - modelo {MODELO_IA} encontrado.")
            return True
    except Exception:
        print("ERRO: Ollama nao esta rodando.")
        print("1. Instale em https://ollama.com/download")
        print(f"2. Execute: ollama pull {MODELO_IA}")
        print("3. Deixe rodando: ollama serve")
        return False
    return False

def main():
    if not PASTA_FOTOS.exists():
        print(f"Pasta '{PASTA_FOTOS}' nao existe. Crie e coloque as fotos.")
        return
    arquivos = [a for a in PASTA_FOTOS.iterdir() if a.is_file() and a.suffix.lower() in EXTENSOES_IMAGENS]
    if not arquivos:
        print("Nenhuma imagem encontrada.")
        return

    print(f"Foram encontradas {len(arquivos)} fotos.\n")
    verificar_ollama()
    print()

    resultados = []
    total = len(arquivos)
    for idx, arq in enumerate(sorted(arquivos), start=1):
        resultados.append(processar_foto(arq, idx, total))

    resultados.sort(key=lambda r: (r["data_hora"] is None, r["data_hora"] if r["data_hora"] else datetime.max))
    mostrar_resultados(resultados)
    salvar_csv(resultados)
    print(f"\nResultado salvo em: {ARQUIVO_RESULTADO}")
    descarregar_modelo()

if __name__ == "__main__":
    main()
