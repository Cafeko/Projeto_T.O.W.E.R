"""Distribuição física de fotos classificadas — único meio permitido de copiar.

- `--preparar`: cria o ambiente do relatório
  (`<relatorio>/fotos/` + classificacao.csv todas PENDENTE + viewer inicial)
  SEM classificar e sem sugerir por nome; a tentativa de classificação é
  por conteúdo, e o usuário corrige/classifica o resto no modo treino.
- Agente externo ou treino: classifica e grava <relatorio>/classificacao.csv,
  depois este script distribui por classe.
  PROIBIDO ao agente copiar/renomear manualmente (os.rename, shutil,
  move, copy, script ad-hoc).
- Uma mesma foto pode ter N classes -> é copiada para N pastas.
- A ordem cronológica é preservada: o nome original (Foto (n).ext) é
  mantido dentro de cada pasta de classe, em ordem natural — pronto para
  visualização/cópia estilo fit_fotos.
- Rode a partir da RAIZ do projeto; caminhos relativos se resolvem
  contra a raiz (ex: python features/classificar_fotos/classificar_fotos.py ...).
"""

import argparse
import csv
import json
import re
import shutil
from pathlib import Path

# Raiz do projeto = 2 níveis acima deste arquivo (features/classificar_fotos/ -> raiz).
# Caminhos internos absolutos: funciona com duplo-clique ou qualquer CWD.
RAIZ_PROJETO = Path(__file__).resolve().parents[2]

PASTA_ORIGEM_PADRAO = RAIZ_PROJETO / "Arquivos" / "Fotos_Ordenadas"
BASE_CLASSIFICADAS = RAIZ_PROJETO / "Arquivos" / "Classificadas"
NOME_CSV = "classificacao.csv"
NOME_VIEWER = "viewer.json"
# Dentro da pasta de cada relatório, as fotos aguardando classificação.
PASTA_FOTOS_REL = "fotos"
PASTA_SEM_CLASSE = "_NÃO_CLASSIFICADAS"
CABECALHO_CSV = ["Arquivo", "Ordem", "Classes", "Status", "Observacao IA"]

EXTENSOES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

# Caracteres inválidos no Windows para nome de pasta.
_INVALIDOS = r'\/:*?"<>|'


def sanitizar_nome(nome: str) -> str:
    """Normaliza nome de relatório/classe para pasta segura."""
    nome = (nome or "").strip().replace("_", " ")
    nome = re.sub(r"\s+", " ", nome).strip()
    for ch in _INVALIDOS:
        nome = nome.replace(ch, "")
    nome = re.sub(r"\s+", "_", nome.strip())
    nome = re.sub(r"_+", "_", nome).strip("_.")
    return nome or "sem_nome"


def chave_natural(nome: str) -> list:
    """Ordenação natural: Foto (2) < Foto (10)."""
    return [int(p) if p.isdigit() else p.lower()
            for p in re.split(r"(\d+)", nome)]


def listar_fotos(pasta: Path) -> list[Path]:
    pasta = Path(pasta)
    if not pasta.is_dir():
        return []
    return sorted((p for p in pasta.iterdir()
                   if p.is_file() and p.suffix.lower() in EXTENSOES),
                  key=lambda p: chave_natural(p.name))


def verificar_ordenadas(pasta: Path | str | None = None) -> tuple[bool, str]:
    """Checa se a pasta parece conter fotos já ordenadas.

    Critério: todos os arquivos seguem `Foto (n).ext` com n sequencial
    de 1..N sem buracos. Retorna (ordenada, motivo).
    """
    pasta = Path(pasta) if pasta else PASTA_ORIGEM_PADRAO
    fotos = listar_fotos(pasta)
    if not fotos:
        return False, f"pasta vazia ou sem imagens: {pasta}"
    padrao = re.compile(r"^foto \((\d+)\)\.\w+$", re.IGNORECASE)
    numeros = []
    for f in fotos:
        m = padrao.match(f.name)
        if not m:
            return False, f"arquivo fora do padrão ordenado: {f.name}"
        numeros.append(int(m.group(1)))
    if sorted(numeros) != list(range(1, len(fotos) + 1)):
        return False, "numeração fora de sequência (buraco ou duplicada)"
    return True, f"{len(fotos)} fotos em sequência Foto (1)..Foto ({len(fotos)})"


def pasta_csv(relatorio: str, base: Path | str | None = None,
              csv_opt: Path | str | None = None) -> tuple[Path, Path]:
    """Resolve (pasta_do_relatorio, caminho_csv)."""
    base = Path(base) if base else BASE_CLASSIFICADAS
    if csv_opt:
        csv_path = Path(csv_opt)
        pasta_rel = csv_path.parent
    else:
        pasta_rel = base / sanitizar_nome(relatorio)
        csv_path = pasta_rel / NOME_CSV
    return pasta_rel, csv_path


def iniciar_csv(relatorio: str, base: Path | str | None = None,
                csv_opt: Path | str | None = None,
                origem: Path | str | None = None) -> Path:
    """Cria a pasta do relatório + CSV com cabeçalho (se ainda não existe).

    O agente preenche o CSV lendo cada imagem. Retorna o caminho do CSV.
    """
    pasta_rel, csv_path = pasta_csv(relatorio, base, csv_opt)
    pasta_rel.mkdir(parents=True, exist_ok=True)
    if not csv_path.exists():
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(CABECALHO_CSV)
        # Pré-preenche uma linha por foto da origem, para o agente completar.
        fotos = listar_fotos(Path(origem) if origem else PASTA_ORIGEM_PADRAO)
        if fotos:
            with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                for i, foto in enumerate(fotos, start=1):
                    w.writerow([foto.name, i, "", "PENDENTE", ""])
        print(f"CSV iniciado: {csv_path} ({len(fotos) if fotos else 0} fotos)")
    else:
        print(f"CSV já existe: {csv_path}")
    return csv_path


def resolver_origem(relatorio: str, origem: Path | str | None = None,
                    base: Path | str | None = None) -> Path:
    """Origem das fotos: --origem vence; senão a pasta fotos/ do relatório
    (se existir com imagens); senão Arquivos/Fotos_Ordenadas."""
    if origem:
        return Path(origem)
    base = Path(base) if base else BASE_CLASSIFICADAS
    fotos_rel = base / sanitizar_nome(relatorio) / PASTA_FOTOS_REL
    if fotos_rel.is_dir() and listar_fotos(fotos_rel):
        return fotos_rel
    return PASTA_ORIGEM_PADRAO


def preparar_relatorio(relatorio: str,
                       pasta_origem: Path | str | None = None,
                       base_destino: Path | str | None = None) -> Path:
    """Prepara o ambiente do relatório automaticamente (sem classificar).

    - Cria `Arquivos/Classificadas/<relatorio>/`;
    - copia as fotos da origem para `<relatorio>/fotos/` (aguardando —
      cópia permanente: pode apagar os originais);
    - gera `classificacao.csv` com todas PENDENTE — a tentativa de
      classificação por conteúdo vem depois (e o usuário corrige/classifica
      o resto no treino; cada validação também salva a imagem em
      `_dataset/<classe>/`, cópia permanente);
    - gera `viewer.json` inicial (status aguardando).
    Retorna a pasta do relatório.
    """
    pasta_origem = Path(pasta_origem) if pasta_origem else PASTA_ORIGEM_PADRAO
    base_destino = Path(base_destino) if base_destino else BASE_CLASSIFICADAS
    pasta_rel = base_destino / sanitizar_nome(relatorio)
    pasta_rel.mkdir(parents=True, exist_ok=True)
    dest_fotos = pasta_rel / PASTA_FOTOS_REL
    dest_fotos.mkdir(parents=True, exist_ok=True)

    ok, motivo = verificar_ordenadas(pasta_origem)
    if not ok:
        print(f"AVISO: origem fora do padrão ordenado ({motivo}). "
              "Preparando mesmo assim — confira a ordem no treino.")

    fotos = listar_fotos(pasta_origem)
    copiadas = 0
    for foto in fotos:
        destino = dest_fotos / foto.name
        if not destino.exists():
            shutil.copy2(foto, destino)
        copiadas += 1

    csv_path = pasta_rel / NOME_CSV
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CABECALHO_CSV)
        w.writeheader()
        for i, foto in enumerate(fotos, start=1):
            w.writerow({"Arquivo": foto.name, "Ordem": i, "Classes": "",
                        "Status": "PENDENTE", "Observacao IA": ""})

    viewer = {
        "relatorio": sanitizar_nome(relatorio),
        "origem": str(pasta_origem),
        "destino": str(pasta_rel),
        "fotos_dir": str(dest_fotos),
        "classes": [],
        "total_fotos": len(fotos),
        "total_copias": 0,
        "ausentes": 0,
        "status": "aguardando_classificacao",
        "fotos": [
            {"arquivo": foto.name, "ordem": i, "classes": [], "observacao": ""}
            for i, foto in enumerate(fotos, start=1)
        ],
    }
    with open(pasta_rel / NOME_VIEWER, "w", encoding="utf-8") as f:
        json.dump(viewer, f, ensure_ascii=False, indent=2)

    print(f"\nRelatorio '{relatorio}' preparado: {copiadas} fotos em {dest_fotos}")
    print(f"CSV: {csv_path} ({len(fotos)} pendentes)")
    print("Proximo passo: tentativa de classificação por conteúdo; depois o "
          "treino p/ corrigir e classificar o resto; por fim --relatorio p/ distribuir.")
    return pasta_rel


def carregar_classificacao(csv_path: Path | str) -> list[dict] | None:
    """Lê classificacao.csv. Classes separadas por ; ou | (multi-rótulo)."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"ERRO: {csv_path} nao encontrado. O agente deve classificar "
              "cada imagem e gravar o CSV antes de chamar este script.")
        return None
    linhas = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            arquivo = (row.get("Arquivo") or "").strip()
            if not arquivo:
                continue
            try:
                ordem = int(str(row.get("Ordem") or "0").strip())
            except ValueError:
                ordem = 0
            bruto = (row.get("Classes") or "").strip()
            # Aceita ; ou | como separador multi-classe.
            classes = [sanitizar_nome(c) for c in re.split(r"[;|]", bruto)
                       if c.strip()]
            # Remove duplicadas preservando ordem.
            vistas = set()
            unicas = []
            for c in classes:
                if c not in vistas:
                    vistas.add(c)
                    unicas.append(c)
            linhas.append({
                "arquivo": arquivo,
                "ordem": ordem,
                "classes": unicas,
                "status": (row.get("Status") or "").strip(),
                "observacao": (row.get("Observacao IA") or "").strip(),
            })
    linhas.sort(key=lambda r: (r["ordem"] or 10 ** 9, chave_natural(r["arquivo"])))
    return linhas


def aplicar_classificacao(relatorio: str,
                          pasta_origem: Path | str | None = None,
                          base_destino: Path | str | None = None,
                          csv_path: Path | str | None = None,
                          limpar_destino: bool = True) -> list[tuple[Path, Path]]:
    """Copia cada foto para N pastas de classe, mantendo nome/ordem.

    Gera viewer.json na pasta do relatório para a UI futura (estilo
    fit_fotos: ver + copiar por classe). Retorna lista de (origem, destino).

    Se pasta_origem for None, usa a pasta fotos/ do relatório (quando o
    relatório foi preparado) ou Arquivos/Fotos_Ordenadas.
    """
    base_destino = Path(base_destino) if base_destino else BASE_CLASSIFICADAS
    pasta_origem = Path(pasta_origem) if pasta_origem else resolver_origem(relatorio, None, base_destino)
    pasta_rel, csv_resolvido = pasta_csv(relatorio, base_destino, csv_path)
    csv_resolvido = Path(csv_path) if csv_path else csv_resolvido

    linhas = carregar_classificacao(csv_resolvido)
    if linhas is None:
        return []

    pasta_rel.mkdir(parents=True, exist_ok=True)
    if limpar_destino:
        for p in pasta_rel.iterdir():
            if p.is_dir() and p.name != PASTA_FOTOS_REL:
                shutil.rmtree(p)

    realizados: list[tuple[Path, Path]] = []
    todas_classes: list[str] = []
    vistas_cls: set[str] = set()
    ausentes = 0

    for item in linhas:
        origem = pasta_origem / item["arquivo"]
        if not origem.exists():
            print(f"- {item['arquivo']} NAO ENCONTRADA em {pasta_origem}")
            ausentes += 1
            continue
        classes = item["classes"] or [PASTA_SEM_CLASSE]
        for cls in classes:
            if cls not in vistas_cls:
                vistas_cls.add(cls)
                todas_classes.append(cls)
            destino_dir = pasta_rel / cls
            destino_dir.mkdir(parents=True, exist_ok=True)
            destino = destino_dir / origem.name
            shutil.copy2(origem, destino)
            realizados.append((origem, destino))
            # Cópia permanente p/ treino futuro (pode apagar os originais).
            ds_dir = base_destino / "_dataset" / cls
            ds_dir.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(origem, ds_dir / f"{sanitizar_nome(relatorio)}__{origem.name}")
            except OSError:
                pass

    # Índice para a UI futura (ver + copiar por classe, como o fit_fotos).
    viewer = {
        "relatorio": sanitizar_nome(relatorio),
        "origem": str(pasta_origem),
        "destino": str(pasta_rel),
        "classes": sorted(todas_classes),
        "total_fotos": len(linhas),
        "total_copias": len(realizados),
        "ausentes": ausentes,
        "fotos": [
            {"arquivo": it["arquivo"], "ordem": it["ordem"],
             "classes": it["classes"] or [PASTA_SEM_CLASSE],
             "observacao": it["observacao"]}
            for it in linhas
        ],
    }
    with open(pasta_rel / NOME_VIEWER, "w", encoding="utf-8") as f:
        json.dump(viewer, f, ensure_ascii=False, indent=2)

    print(f"\nRelatorio '{relatorio}': {len(realizados)} copias "
          f"({len(linhas)} fotos, {len(todas_classes)} classes) -> {pasta_rel}")
    for cls in sorted(todas_classes):
        qtd = sum(1 for _, d in realizados if d.parent.name == cls)
        print(f"  - {cls}: {qtd} fotos")
    print(f"Indice p/ UI: {pasta_rel / NOME_VIEWER} (compativel c/ fit_fotos: "
          "abra --pasta nessa classe)")
    return realizados


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Distribui fotos classificadas por relatório/classe "
                    "(multi-rótulo). Único meio permitido de copiar — "
                    "não copie manualmente.")
    ap.add_argument("--relatorio", default=None,
                    help="nome do relatório (pasta em Arquivos/Classificadas/)")
    ap.add_argument("--origem", default=None,
                    help="pasta das fotos (padrão: fotos/ do relatório se preparada, "
                         "senão Arquivos/Fotos_Ordenadas)")
    ap.add_argument("--csv", default=None,
                    help="CSV da classificação (padrão: "
                         "Arquivos/Classificadas/<relatorio>/classificacao.csv)")
    ap.add_argument("--base", default=None,
                    help="base das classificadas (padrão: Arquivos/Classificadas)")
    ap.add_argument("--iniciar", action="store_true",
                    help="só cria a pasta do relatório + CSV com cabeçalho e sai")
    ap.add_argument("--preparar", action="store_true",
                    help="prepara o ambiente do relatório: copia as fotos p/ "
                         "<relatorio>/fotos/, gera CSV todas PENDENTE + viewer "
                         "inicial. Sem classificar e sem sugerir por nome")
    ap.add_argument("--verificar", action="store_true",
                    help="só verifica se a origem está ordenada (Foto (n)) e sai")
    ap.add_argument("--manter-destino", action="store_true",
                    help="não limpa a pasta do relatório antes de copiar")
    args = ap.parse_args(argv)

    origem = Path(args.origem) if args.origem else PASTA_ORIGEM_PADRAO

    if args.verificar:
        ok, motivo = verificar_ordenadas(origem)
        print(f"{'ORDENADA' if ok else 'NAO ORDENADA'}: {motivo}")
        raise SystemExit(0 if ok else 1)

    if not args.relatorio:
        ap.error("--relatorio é obrigatório (ex: --relatorio torre_norte)")

    if args.iniciar:
        iniciar_csv(args.relatorio, base=args.base, csv_opt=args.csv, origem=origem)
        return

    if args.preparar:
        preparar_relatorio(args.relatorio, pasta_origem=origem,
                           base_destino=args.base)
        return

    aplicar_classificacao(args.relatorio, pasta_origem=args.origem,
                          base_destino=args.base, csv_path=args.csv,
                          limpar_destino=not args.manter_destino)


if __name__ == "__main__":
    main()
