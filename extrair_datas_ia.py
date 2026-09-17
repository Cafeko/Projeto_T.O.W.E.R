"""USO MANUAL APENAS (pessoa no terminal).

PROIBIDO para agentes externos (OpenCode, Claude Code, Cursor, etc.):
agentes externos NÃO devem importar, executar ou reaproveitar este script.
O agente externo extrai as datas SOZINHO (lendo cada imagem com a própria
visão) e grava Arquivos/resultado.csv; a ordenação física é sempre via
organizar_fotos.py. Este script (Ollama local) é só para uma pessoa usar
manualmente no terminal: `python extrair_datas_ia.py`.
"""

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
    "janeiro": 1, "january": 1, "fevereiro": 2, "february": 2, "marco": 3, "março": 3, "march": 3,
    "abril": 4, "april": 4, "maio": 5, "may": 5, "junho": 6, "june": 6,
    "julho": 7, "july": 7, "agosto": 8, "august": 8, "setembro": 9, "september": 9,
    "outubro": 10, "october": 10, "novembro": 11, "november": 11, "dezembro": 12, "december": 12,
}

PROMPT = (
    "Transcribe any date and time visible in this image. "
    "The date can be in any format like '09/09/2024 15:15:55', '2024-09-09 15:15', "
    "'9 de setembro de 2024 17:58:53', 'September 9, 2024 15:15:55' or similar. "
    "The year can be any year, not only 2026. "
    "Reply with the exact text you see, including the full date and time."
)

PROMPT_CROP = (
    "Transcribe any date and time visible in the bottom 30% of this image. "
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
    """Converte varios formatos em datetime e normaliza para DD/MM/AAAA HH:MM:SS."""
    texto = limpar_texto_ia(texto)
    t = texto.strip().lower()
    if "nao encontrada" in t or "não encontrada" in t or not t:
        return None

    # 1) DD/MM/AAAA HH:MM:SS
    m = re.search(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})(?:[.,](\d{1,6}))?", texto)
    if m:
        try:
            dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
            h, mi, s = int(m.group(4)), int(m.group(5)), int(m.group(6))
            frac = m.group(7) or ""
            micro = int(frac.ljust(6, "0")) if frac else 0
            return datetime(ano, mes, dia, h, mi, s, micro)
        except ValueError:
            pass

    # 1b) AAAA-MM-DD HH:MM:SS (ISO)
    m = re.search(r"(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})\s+(\d{1,2}):(\d{2}):(\d{2})", texto)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6)))
        except ValueError:
            pass

    # 2) DD/MM/AAAA sem hora ou com hora parcial
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

    # 2b) AAAA/MM/DD sem hora
    m = re.search(r"(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})", texto)
    if m:
        mh = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", texto)
        h, mi, s = 0, 0, 0
        if mh:
            h, mi = int(mh.group(1)), int(mh.group(2))
            s = int(mh.group(3)) if mh.group(3) else 0
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), h, mi, s)
        except ValueError:
            pass

    # 3) 9 de setembro de 2026 15:15:55 (PT) e 9 September 2026 (EN)
    for nome, num in MESES.items():
        # PT: 9 de setembro de 2026
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
                mh2 = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", texto)
                if mh2:
                    h, mi, s, micro = int(mh2.group(1)), int(mh2.group(2)), int(mh2.group(3)), 0
                else:
                    h = mi = s = micro = 0
            try:
                return datetime(ano, num, dia, h, mi, s, micro)
            except ValueError:
                continue
        # EN: September 9, 2026 ou September 9 2026
        pad_en = re.compile(rf"{nome}\s+(\d{{1,2}})[,\s]+(\d{{4}})", re.IGNORECASE)
        r2 = pad_en.search(texto)
        if r2:
            dia, ano = int(r2.group(1)), int(r2.group(2))
            resto = texto[r2.end():]
            mh = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", resto)
            if not mh:
                mh = re.search(r"(\d{1,2}):(\d{2})", texto)
                if mh:
                    h, mi = int(mh.group(1)), int(mh.group(2))
                    s = int(mh.group(3)) if len(mh.groups()) >= 3 and mh.group(3) else 0
                    micro = 0
                else:
                    h = mi = s = micro = 0
            else:
                h, mi, s = int(mh.group(1)), int(mh.group(2)), int(mh.group(3))
                micro = 0
            try:
                return datetime(ano, num, dia, h, mi, s, micro)
            except ValueError:
                continue
    return None

# ============================================================
# CONSULTA OLLAMA
# ============================================================

def imagem_para_base64(caminho: Path, max_size: int = 896, crop_bottom: float | None = None) -> str:
    """Converte imagem para base64 com redimensionamento e opcional crop do rodape."""
    import io
    with Image.open(caminho) as im:
        if crop_bottom is not None:
            w, h = im.size
            im = im.crop((0, int(h * (1 - crop_bottom)), w, h))
        im.thumbnail((max_size, max_size))
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=92)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

def chamar_ollama(b64: str, prompt: str, timeout: int = 90) -> str:
    payload = {
        "model": MODELO_IA,
        "prompt": prompt,
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 80},
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Ollama {resp.status_code}: {resp.text[:200]}")
    txt = resp.json().get("response", "").strip()
    # detecta alucinacao por sobrecarga (@@@@) - trata como erro para retry
    if txt and set(txt) == {"@"}:
        raise RuntimeError("Resposta invalida @@@ - modelo sobrecarregado")
    return txt

def consultar_ia(caminho: Path) -> tuple[str, datetime | None]:
    """Tenta estrategias generalizadas; com retry e pausa para evitar sobrecarga em lotes grandes."""
    import time
    tentativas = [
        (896, None, PROMPT),
        (1000, 0.30, PROMPT_CROP),
        (1100, None, PROMPT),
    ]
    ultimo_texto = ""
    for max_size, crop, prompt in tentativas:
        try:
            b64 = imagem_para_base64(caminho, max_size=max_size, crop_bottom=crop)
        except Exception as e:
            return f"ERRO ao ler imagem: {e}", None
        for tentativa in range(2):  # retry 1x se @@@
            try:
                texto = chamar_ollama(b64, prompt, timeout=90)
                ultimo_texto = texto
                break
            except RuntimeError as e:
                if "@@@" in str(e) and tentativa == 0:
                    time.sleep(1.5)
                    continue
                ultimo_texto = str(e)
                texto = ""
                break
            except requests.exceptions.ConnectionError:
                return "ERRO: Ollama nao esta rodando. Execute 'ollama serve' no terminal.", None
            except Exception as e:
                ultimo_texto = f"ERRO: {e}"
                texto = ""
                break
        dt = parse_data(ultimo_texto)
        if dt is not None:
            time.sleep(0.3)  # pequena pausa para estabilidade em lotes grandes
            return ultimo_texto, dt
        time.sleep(0.2)
    time.sleep(0.3)
    dt = parse_data(ultimo_texto)
    return ultimo_texto, dt

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

def salvar_csv(resultados, destino: Path | str | None = None):
    destino = Path(destino) if destino else ARQUIVO_RESULTADO
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", newline="", encoding="utf-8-sig") as f:
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

def processar_pasta(pasta: Path | str | None = None,
                    csv_saida: Path | str | None = None):
    """Extrai datas de todas as fotos de `pasta` e salva CSV em `csv_saida`.

    Retorna lista de resultados. Reaproveitado pelo agente LLM.
    """
    pasta = Path(pasta) if pasta else PASTA_FOTOS
    csv_saida = Path(csv_saida) if csv_saida else ARQUIVO_RESULTADO
    if not pasta.exists():
        print(f"Pasta '{pasta}' nao existe. Crie e coloque as fotos.")
        return []
    arquivos = [a for a in pasta.iterdir() if a.is_file() and a.suffix.lower() in EXTENSOES_IMAGENS]
    if not arquivos:
        print("Nenhuma imagem encontrada.")
        return []

    print(f"Foram encontradas {len(arquivos)} fotos em '{pasta}'.\n")
    verificar_ollama()
    print()

    resultados = []
    total = len(arquivos)
    for idx, arq in enumerate(sorted(arquivos), start=1):
        resultados.append(processar_foto(arq, idx, total))

    resultados.sort(key=lambda r: (r["data_hora"] is None, r["data_hora"] if r["data_hora"] else datetime.max))
    mostrar_resultados(resultados)
    salvar_csv(resultados, csv_saida)
    print(f"\nResultado salvo em: {csv_saida}")
    descarregar_modelo()
    return resultados


def main():
    processar_pasta()

if __name__ == "__main__":
    main()
