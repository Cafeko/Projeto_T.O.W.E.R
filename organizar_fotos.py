import csv
import shutil
from datetime import datetime
from pathlib import Path

PASTA_FOTOS = Path("Arquivos/fotos")
PASTA_DESTINO = Path("Arquivos/Fotos_Ordenadas")
ARQUIVO_CSV = Path("Arquivos/resultado.csv")

def carregar_ordem():
    """Le resultado.csv e retorna lista ordenada por data_hora."""
    if not ARQUIVO_CSV.exists():
        print(f"ERRO: {ARQUIVO_CSV} nao encontrado. Rode primeiro image_ordenator_ia.py")
        return None

    resultados = []
    with open(ARQUIVO_CSV, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            # Data/Hora no formato 09/09/2026 15:15:52.775
            dth = row.get("Data/Hora", "").strip()
            dt = None
            if dth:
                for fmt in ("%d/%m/%Y %H:%M:%S.%f", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
                    try:
                        dt = datetime.strptime(dth, fmt)
                        break
                    except ValueError:
                        continue
            resultados.append({
                "arquivo": row["Arquivo"],
                "data_hora": dt,
                "status": row.get("Status", ""),
            })

    # separa com data e sem data (sem data vai pro final)
    com_data = [r for r in resultados if r["data_hora"] is not None]
    sem_data = [r for r in resultados if r["data_hora"] is None]
    com_data.sort(key=lambda r: r["data_hora"])
    return com_data, sem_data

def escolher_ordem():
    print("Como ordenar?")
    print("  1 - Mais antiga primeiro (Foto (1) = mais antiga)")
    print("  2 - Mais recente primeiro (Foto (1) = mais recente)")
    while True:
        op = input("Escolha 1 ou 2: ").strip()
        if op in ("1", "2"):
            return op
        print("Opcao invalida. Digite 1 ou 2.")

def copiar_ordenado(ordem: str):
    com_data, sem_data = carregar_ordem() or (None, None)
    if com_data is None:
        return

    # define ordem
    if ordem == "2":  # mais recente primeiro
        com_data = list(reversed(com_data))
        descricao = "mais recente primeiro"
    else:
        descricao = "mais antiga primeiro"

    # lista final: com data ordenada + sem data no final (mantem ordem original)
    lista_final = com_data + sem_data

    # prepara destino
    PASTA_DESTINO.mkdir(parents=True, exist_ok=True)
    # limpa destino antes
    for p in PASTA_DESTINO.iterdir():
        if p.is_file():
            p.unlink()

    print(f"\nOrdenando {len(lista_final)} fotos ({descricao}) -> {PASTA_DESTINO}\n")
    for idx, item in enumerate(lista_final, start=1):
        origem = PASTA_FOTOS / item["arquivo"]
        if not origem.exists():
            print(f"{idx}/{len(lista_final)} - {item['arquivo']} NAO ENCONTRADA na pasta Fotos")
            continue
        # mantem extensao original (.jpeg/.jpg)
        ext = origem.suffix  # .jpeg
        destino = PASTA_DESTINO / f"Foto ({idx}){ext}"
        shutil.copy2(origem, destino)
        dt_txt = item["data_hora"].strftime("%d/%m/%Y %H:%M:%S.%f")[:-3] if item["data_hora"] else "SEM DATA"
        print(f"{idx}/{len(lista_final)} - {item['arquivo']} -> Foto ({idx}){ext}  {dt_txt}  {item['status']}")

    print(f"\nConcluido. Fotos ordenadas em: {PASTA_DESTINO}")

def main():
    import sys
    # permite: python ordenar_fotos.py 1  ou  2  ou  --recente/--antiga
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("1", "antiga", "--antiga", "antigo"):
            copiar_ordenado("1")
            return
        if arg in ("2", "recente", "--recente", "recentes"):
            copiar_ordenado("2")
            return
    # interativo
    ordem = escolher_ordem()
    copiar_ordenado(ordem)

if __name__ == "__main__":
    main()
