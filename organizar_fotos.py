import csv
import shutil
from datetime import datetime
from pathlib import Path

PASTA_FOTOS = Path("Arquivos/fotos")
PASTA_DESTINO = Path("Arquivos/Fotos_Ordenadas")
ARQUIVO_CSV = Path("Arquivos/resultado.csv")

def carregar_ordem(csv_path: Path | None = None):
    """Le resultado.csv e retorna (com_data, sem_data) ordenada por data_hora."""
    csv_path = Path(csv_path) if csv_path else ARQUIVO_CSV
    if not csv_path.exists():
        print(f"ERRO: {csv_path} nao encontrado. Rode primeiro extrair_datas_ia.py")
        return None

    resultados = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
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

def aplicar_ordenacao(ordem: str, pasta_origem: Path | str | None = None,
                      pasta_destino: Path | str | None = None,
                      csv_path: Path | str | None = None,
                      modo: str = "copia"):
    """Ordena fotos segundo o CSV.

    ordem: "1" = mais antiga primeiro, "2" = mais recente primeiro.
    modo: "copia" -> copia para pasta_destino (padrao Arquivos/Fotos_Ordenadas).
          "renomear" -> renomeia os arquivos dentro da pasta_origem.
    Retorna lista de (origem, destino_final).
    """
    pasta_origem = Path(pasta_origem) if pasta_origem else PASTA_FOTOS
    pasta_destino = Path(pasta_destino) if pasta_destino else PASTA_DESTINO
    modo = (modo or "copia").strip().lower()
    if modo not in ("copia", "copiar", "renomear", "renomear_existentes"):
        modo = "copia"
    renomear = modo.startswith("renomear")

    dados = carregar_ordem(Path(csv_path) if csv_path else None)
    if dados is None:
        return []
    com_data, sem_data = dados

    # define ordem
    if ordem == "2":  # mais recente primeiro
        com_data = list(reversed(com_data))
        descricao = "mais recente primeiro"
    else:
        descricao = "mais antiga primeiro"

    # lista final: com data ordenada + sem data no final (mantem ordem original)
    lista_final = com_data + sem_data
    realizados = []

    if renomear:
        # Renomeia dentro da pasta_origem em 2 fases (temp -> final)
        # para evitar colisao quando o destino ja existe.
        print(f"\nRenomeando {len(lista_final)} fotos ({descricao}) em: {pasta_origem}\n")
        fase1 = []
        for idx, item in enumerate(lista_final, start=1):
            origem = pasta_origem / item["arquivo"]
            if not origem.exists():
                print(f"{idx}/{len(lista_final)} - {item['arquivo']} NAO ENCONTRADA em {pasta_origem}")
                continue
            ext = origem.suffix
            temp = pasta_origem / f"__tmp_ordenar_{idx}__{origem.name}"
            try:
                origem.rename(temp)
            except FileNotFoundError:
                # pode ja ter sido movida se CSV tinha duplicata; tenta localizar
                print(f"{idx}/{len(lista_final)} - {item['arquivo']} NAO ENCONTRADA (ja movida?)")
                continue
            fase1.append((temp, idx, ext, item))
        for temp, idx, ext, item in fase1:
            destino = pasta_origem / f"Foto ({idx}){ext}"
            if destino.exists() and destino != temp:
                destino.unlink()
            temp.rename(destino)
            realizados.append((temp, destino))
            dt_txt = item["data_hora"].strftime("%d/%m/%Y %H:%M:%S.%f")[:-3] if item["data_hora"] else "SEM DATA"
            print(f"{idx}/{len(lista_final)} - {item['arquivo']} -> Foto ({idx}){ext}  {dt_txt}  {item['status']}")
        print(f"\nConcluido. Fotos renomeadas em: {pasta_origem}")
        return realizados

    # modo copia: prepara destino
    pasta_destino.mkdir(parents=True, exist_ok=True)
    # limpa destino antes
    for p in pasta_destino.iterdir():
        if p.is_file():
            p.unlink()

    print(f"\nOrdenando {len(lista_final)} fotos ({descricao}) -> {pasta_destino}\n")
    for idx, item in enumerate(lista_final, start=1):
        origem = pasta_origem / item["arquivo"]
        if not origem.exists():
            print(f"{idx}/{len(lista_final)} - {item['arquivo']} NAO ENCONTRADA na pasta {pasta_origem}")
            continue
        # mantem extensao original (.jpeg/.jpg)
        ext = origem.suffix  # .jpeg
        destino = pasta_destino / f"Foto ({idx}){ext}"
        shutil.copy2(origem, destino)
        realizados.append((origem, destino))
        dt_txt = item["data_hora"].strftime("%d/%m/%Y %H:%M:%S.%f")[:-3] if item["data_hora"] else "SEM DATA"
        print(f"{idx}/{len(lista_final)} - {item['arquivo']} -> Foto ({idx}){ext}  {dt_txt}  {item['status']}")

    print(f"\nConcluido. Fotos ordenadas em: {pasta_destino}")
    return realizados


def copiar_ordenado(ordem: str, pasta_origem=None, pasta_destino=None, csv_path=None):
    """Compat: mantem comportamento antigo (copia)."""
    return aplicar_ordenacao(ordem, pasta_origem=pasta_origem,
                             pasta_destino=pasta_destino, csv_path=csv_path,
                             modo="copia")

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
