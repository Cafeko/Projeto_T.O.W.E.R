"""Montar relatório por atividade + etapa — único meio permitido de copiar.

Modelo novo (foco: provar que o serviço foi feito, antes/durante/depois):

- RELATÓRIO = pasta de trabalho em Arquivos/Relatorios/<relatorio>/
- ATIVIDADE = item do escopo (ex: 01-troca_da_fonte)
- ETAPA = antes | durante | depois (+ _NAO_IDENTIFICADAS como fallback)

Arquivos por relatório:
  fotos/                  # cópia permanente da entrada ordenada (Foto (n))
  escopo.json             # o que a LLM precisa saber (atividades + o que
                          #   esperar em cada etapa + fotos-exemplo)
  evidencia.csv           # a LLM preenche (1 foto = 1 atividade + 1 etapa)
  atividades/<id>_<slug>/antes|durante|depois/Foto (n).ext
  fotos_do_site/              # atividade SITE (sem etapa): rua/acesso, frente,
                              #   portão, cadeado, torre, área interna, placa ID
  _NAO_IDENTIFICADAS/     # fallback — nunca descarta foto
  viewer.json             # índice p/ UI futura

A LLM (visão) lê cada foto e preenche evidencia.csv; este script só
distribui (shutil.copy2). PROIBIDO ao agente copiar/renomear manualmente.

Rode a partir da RAIZ do projeto.
"""

import argparse
import csv
import json
import re
import shutil
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[2]

PASTA_ORIGEM_PADRAO = RAIZ_PROJETO / "Arquivos" / "Fotos_Ordenadas"
BASE_RELATORIOS = RAIZ_PROJETO / "Arquivos" / "Relatorios"

PASTA_FOTOS = "fotos"
PASTA_ATIVIDADES = "atividades"
PASTA_SITE = "fotos_do_site"
PASTA_SEM = "_NAO_IDENTIFICADAS"
PASTA_MODELOS = "_modelos"
N_MODELOS_PADRAO = 10
NOME_ESCOPO = "escopo.json"
NOME_EVIDENCIA = "evidencia.csv"
NOME_VIEWER = "viewer.json"
NOME_CATALOGO = "_catalogo.json"

ETAPAS = ("antes", "durante", "depois")
CONFIANCAS = ("alta", "media", "baixa", "")
STATUS_OK = ("OK", "SUGERIDA", "PENDENTE", "NAO_IDENTIFICADA")

# Atividade especial (vale p/ todo relatório, sem etapa): fotos padrão do
# site — rua/acesso, frente, portão, cadeado, torre, área interna, placa ID.
# Vai para <relatorio>/fotos_do_site/ em vez de atividades/.
ATIVIDADE_SITE = "SITE"

TIPOS_SITE = ("rua/acesso", "frente do site", "portão", "cadeado", "torre",
              "área interna", "placa ID")

CABECALHO_CSV = ["Arquivo", "Ordem", "DataHora", "Atividade", "Etapa",
                 "Confianca", "Status", "Observacao", "Qualidade"]

# Qualidade p/ o relatório: boa (entra), ruim (fraca tecnicamente),
# duplicada (similar a outra melhor próxima no tempo — não incluir).
# Vazias/NÃO_CLASSIFICADAS ficam sem qualidade.
QUALIDADES = ("boa", "ruim", "duplicada", "")

EXTENSOES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
_INVALIDOS = r'\/:*?"<>|'


def sanitizar_nome(nome: str) -> str:
    nome = (nome or "").strip().replace("_", " ")
    nome = re.sub(r"\s+", " ", nome).strip()
    for ch in _INVALIDOS:
        nome = nome.replace(ch, "")
    nome = re.sub(r"\s+", "_", nome.strip())
    nome = re.sub(r"_+", "_", nome).strip("_.")
    return nome or "sem_nome"


def chave_natural(nome: str) -> list:
    return [int(p) if p.isdigit() else p.lower()
            for p in re.split(r"(\d+)", nome)]


def listar_fotos(pasta: Path) -> list[Path]:
    pasta = Path(pasta)
    if not pasta.is_dir():
        return []
    return sorted((p for p in pasta.iterdir()
                   if p.is_file() and p.suffix.lower() in EXTENSOES),
                  key=lambda p: chave_natural(p.name))


def pasta_relatorio(relatorio: str, base: Path | None = None) -> Path:
    base = Path(base) if base else BASE_RELATORIOS
    return base / sanitizar_nome(relatorio)


def escopo_template(relatorio: str) -> dict:
    return {
        "relatorio": sanitizar_nome(relatorio),
        "descricao": "Descreva o serviço contratado em 1-2 frases.",
        "atividades": [
            {
                "id": "01",
                "titulo": "Exemplo - troca da fonte",
                "tipo": "troca_fonte",
                "descricao": "Substituir a fonte queimada do painel.",
                "evidencia": {
                    "antes": "fonte antiga com marca de queimado, painel aberto",
                    "durante": "tecnico com fiacao solta, fonte fora do lugar",
                    "depois": "fonte nova instalada, led aceso, painel fechado"
                },
                "exemplos": {"antes": [], "durante": [], "depois": []}
            }
        ],
        "fotos_site": list(TIPOS_SITE),
    }


def carregar_escopo(pasta_rel: Path) -> dict | None:
    caminho = pasta_rel / NOME_ESCOPO
    if not caminho.exists():
        return None
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def slug_atividade(ativ: dict) -> str:
    return f"{(ativ.get('id') or '00').strip()}_{sanitizar_nome(ativ.get('titulo') or 'atividade')}"


def mapa_slugs(escopo: dict | None) -> dict:
    """id da atividade -> pasta <id>_<slug>."""
    mapa: dict[str, str] = {}
    if not escopo:
        return mapa
    for ativ in escopo.get("atividades", []):
        aid = str(ativ.get("id") or "").strip()
        if aid:
            mapa[aid] = slug_atividade(ativ)
    return mapa


def preparar_relatorio(relatorio: str,
                       pasta_origem: Path | str | None = None,
                       base: Path | str | None = None) -> Path:
    pasta_origem = Path(pasta_origem) if pasta_origem else PASTA_ORIGEM_PADRAO
    pasta_rel = pasta_relatorio(relatorio, Path(base) if base else None)
    pasta_rel.mkdir(parents=True, exist_ok=True)
    dest_fotos = pasta_rel / PASTA_FOTOS
    dest_fotos.mkdir(parents=True, exist_ok=True)

    fotos = listar_fotos(pasta_origem)
    copiadas = 0
    for foto in fotos:
        destino = dest_fotos / foto.name
        if not destino.exists():
            shutil.copy2(foto, destino)
        copiadas += 1

    caminho_escopo = pasta_rel / NOME_ESCOPO
    if not caminho_escopo.exists():
        with open(caminho_escopo, "w", encoding="utf-8") as f:
            json.dump(escopo_template(relatorio), f, ensure_ascii=False, indent=2)
        print(f"Escopo modelo criado: {caminho_escopo} — edite as atividades antes de classificar.")
    else:
        print(f"Escopo já existe: {caminho_escopo}")

    csv_path = pasta_rel / NOME_EVIDENCIA
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CABECALHO_CSV)
        w.writeheader()
        for i, foto in enumerate(fotos, start=1):
            w.writerow({"Arquivo": foto.name, "Ordem": i, "DataHora": "",
                        "Atividade": "", "Etapa": "", "Confianca": "",
                        "Status": "PENDENTE", "Observacao": ""})

    viewer = {"relatorio": sanitizar_nome(relatorio),
              "origem": str(pasta_origem), "destino": str(pasta_rel),
              "atividades": [], "total_fotos": len(fotos),
              "total_copias": 0, "ausentes": 0,
              "status": "aguardando_evidencia"}
    with open(pasta_rel / NOME_VIEWER, "w", encoding="utf-8") as f:
        json.dump(viewer, f, ensure_ascii=False, indent=2)

    print(f"\nRelatorio '{relatorio}' preparado: {copiadas} fotos em {dest_fotos}")
    print(f"Evidencia: {csv_path} ({len(fotos)} pendentes)")
    print("Proximo passo: edite o escopo.json e preencha evidencia.csv (visao foto a foto).")
    return pasta_rel


def carregar_evidencia(csv_path: Path) -> list[dict] | None:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"ERRO: {csv_path} nao encontrado. Preencha evidencia.csv antes de distribuir.")
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
            etapa = ";".join(e.strip().lower()
                              for e in (row.get("Etapa") or "").split(";"))
            qualidade = (row.get("Qualidade") or "").strip().lower()
            if qualidade not in QUALIDADES:
                qualidade = ""
            linhas.append({
                "arquivo": arquivo,
                "ordem": ordem,
                "datahora": (row.get("DataHora") or "").strip(),
                "atividade": (row.get("Atividade") or "").strip(),
                "etapa": etapa,
                "confianca": (row.get("Confianca") or "").strip().lower(),
                "status": (row.get("Status") or "").strip(),
                "observacao": (row.get("Observacao") or "").strip(),
                "qualidade": qualidade,
            })
    linhas.sort(key=lambda r: (r["ordem"] or 10 ** 9, chave_natural(r["arquivo"])))
    return linhas


def resolver_origem(pasta_rel: Path) -> Path:
    fotos_rel = pasta_rel / PASTA_FOTOS
    if fotos_rel.is_dir() and listar_fotos(fotos_rel):
        return fotos_rel
    return PASTA_ORIGEM_PADRAO


_MAPA_CAMPOS = {"arquivo": "Arquivo", "ordem": "Ordem", "datahora": "DataHora",
                 "atividade": "Atividade", "etapa": "Etapa", "confianca": "Confianca",
                 "status": "Status", "observacao": "Observacao", "qualidade": "Qualidade"}


def _campo(item: dict, nome: str) -> str:
    """Lê campo em dict interno (minúsculo) ou de CSV/janela (maiúsculo)."""
    v = item.get(nome, "")
    if (v is None or v == "") and nome in _MAPA_CAMPOS:
        v = item.get(_MAPA_CAMPOS[nome], "")
    return v if isinstance(v, str) else (str(v) if v is not None else "")


def pares_evidencia(item: dict) -> list[tuple[str, str]]:
    """Vínculos (atividade, etapa) de uma linha de evidencia.csv.

    Uma foto pode servir a N atividades: Atividade e Etapa aceitam listas
    separadas por `;`, alinhadas por posição
    (ex: Atividade=`02;03`, Etapa=`durante;depois`). SITE ignora a etapa.
    Formato antigo (valor único, ou 1 etapa p/ N atividades) continua valendo.
    """
    ativs = [a.strip() for a in _campo(item, "atividade").split(";") if a.strip()]
    etapas = [(e or "").strip().lower() for e in _campo(item, "etapa").split(";")]
    if len(etapas) == 1 and len(ativs) > 1:
        etapas = etapas * len(ativs)
    pares = []
    for i, aid in enumerate(ativs):
        if aid.upper() == ATIVIDADE_SITE:
            pares.append((ATIVIDADE_SITE, ""))
            continue
        etapa = etapas[i] if i < len(etapas) else ""
        if etapa in ETAPAS:
            pares.append((aid, etapa))
    return pares


def tem_vinculo(item: dict, aid: str, etapa: str = "") -> bool:
    """True se a linha contém o vínculo (aid, etapa). Etapa vazia = qualquer."""
    for a, e in pares_evidencia(item):
        if a == aid and (not etapa or e == etapa):
            return True
    return False


def distribuir(relatorio: str,
               pasta_origem: Path | str | None = None,
               base: Path | str | None = None,
               limpar_destino: bool = True,
               so_boas: bool = False) -> list[tuple[Path, Path]]:
    base = Path(base) if base else BASE_RELATORIOS
    pasta_rel = base / sanitizar_nome(relatorio)
    csv_path = pasta_rel / NOME_EVIDENCIA
    linhas = carregar_evidencia(csv_path)
    if linhas is None:
        return []

    if pasta_origem:
        origem = Path(pasta_origem)
    else:
        origem = resolver_origem(pasta_rel)

    escopo = carregar_escopo(pasta_rel)
    slugs = mapa_slugs(escopo)

    dest_base = pasta_rel / PASTA_ATIVIDADES
    dest_base.mkdir(parents=True, exist_ok=True)
    dest_site = pasta_rel / PASTA_SITE
    dest_site.mkdir(parents=True, exist_ok=True)
    if limpar_destino:
        for p in list(dest_base.iterdir()):
            if p.is_dir():
                shutil.rmtree(p)
        if dest_site.is_dir():
            for p in list(dest_site.iterdir()):
                if p.is_file():
                    p.unlink()
        sem = pasta_rel / PASTA_SEM
        if sem.is_dir():
            shutil.rmtree(sem)

    realizados: list[tuple[Path, Path]] = []
    ausentes = 0
    puladas = 0
    contagem: dict[str, dict[str, int]] = {}
    fotos_site: list[str] = []

    for item in linhas:
        if so_boas and item["qualidade"] != "boa":
            puladas += 1
            continue
        src = origem / item["arquivo"]
        if not src.exists():
            print(f"- {item['arquivo']} NAO ENCONTRADA em {origem}")
            ausentes += 1
            continue
        aid = item["atividade"]
        etapa = item["etapa"]
        pares = pares_evidencia(item)
        if not pares:
            pares = [("", "")]
        for aid, etapa in pares:
            if aid == ATIVIDADE_SITE:
                destino_dir = dest_site
                chave = PASTA_SITE
            elif aid and etapa in ETAPAS:
                pasta_ativ = slugs.get(aid, f"{aid}_{aid}")
                destino_dir = dest_base / pasta_ativ / etapa
                chave = f"{pasta_ativ}/{etapa}"
            else:
                destino_dir = pasta_rel / PASTA_SEM
                chave = PASTA_SEM
                aid, etapa = "", ""
            destino_dir.mkdir(parents=True, exist_ok=True)
            destino = destino_dir / src.name
            shutil.copy2(src, destino)
            realizados.append((src, destino))
            if chave == PASTA_SITE:
                fotos_site.append(src.name)
                continue
            contagem[chave] = contagem.get(chave, {})
            contagem[chave][etapa if aid and etapa else "total"] = \
                contagem[chave].get(etapa if aid and etapa else "total", 0) + 1

    viewer = {"relatorio": sanitizar_nome(relatorio),
              "origem": str(origem), "destino": str(pasta_rel),
              "atividades": [{"id": aid, "pasta": pasta,
                               "etapas": {e: sum(1 for _, d in realizados
                                                 if d.parent.name == e
                                                 and d.parent.parent.name == pasta)
                                          for e in ETAPAS}}
                              for aid, pasta in sorted(slugs.items())],
              "contagem": {k: dict(v) for k, v in sorted(contagem.items())},
              "fotos_site": sorted(fotos_site, key=chave_natural),
              "fotos": [
                  {"arquivo": it["arquivo"], "ordem": it["ordem"],
                   "atividade": it["atividade"], "etapa": it["etapa"],
                   "qualidade": it["qualidade"], "status": it["status"],
                   "observacao": it["observacao"]}
                  for it in linhas
              ],
              "so_boas": so_boas,
              "total_fotos": len(linhas), "total_copias": len(realizados),
              "ausentes": ausentes, "status": "distribuido"}
    with open(pasta_rel / NOME_VIEWER, "w", encoding="utf-8") as f:
        json.dump(viewer, f, ensure_ascii=False, indent=2)

    print(f"\nRelatorio '{relatorio}': {len(realizados)} copias "
          f"({len(linhas)} fotos) -> {dest_base}")
    for chave in sorted(contagem):
        total = sum(contagem[chave].values())
        print(f"  - {chave}: {total} fotos")
    if fotos_site:
        print(f"  - {PASTA_SITE}: {len(fotos_site)} fotos")
    if so_boas:
        print(f"  (só qualidade boa: {puladas} ruins/duplicadas/pendentes puladas)")
    if ausentes:
        print(f"  ! {ausentes} ausentes")
    return realizados


def tipo_site(observacao: str) -> str:
    """Extrai o tipo de 'site - <tipo>: ...'. Sem tipo = 'geral'."""
    obs = (observacao or "").strip()
    if obs.lower().startswith("site -"):
        resto = obs[6:].strip()
        if ":" in resto:
            return sanitizar_nome(resto.split(":", 1)[0].lower()) or "geral"
    return "geral"


def atualizar_catalogo(dest_base: Path) -> Path:
    """Reconstrói _modelos/_catalogo.json a partir das pastas de modelos.

    O catálogo é indexado por TIPO de atividade — não por relatório — e
    reúne título, descrição, o que mostrar em cada etapa e os exemplos
    guardados. Os tipos de site ficam em `site`. Remove o metadado antigo
    `exemplo_de` dos guias (o relatório de origem não é o que se aprende).
    """
    catalogo = {"atividades": {}, "site": {}}

    for pasta in sorted(dest_base.iterdir()):
        if not pasta.is_dir() or pasta.name == ATIVIDADE_SITE:
            continue
        guia_path = pasta / "guia.json"
        if not guia_path.exists():
            continue
        try:
            with open(guia_path, encoding="utf-8") as f:
                guia = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        if "exemplo_de" in guia:
            guia.pop("exemplo_de", None)
            with open(guia_path, "w", encoding="utf-8") as f:
                json.dump(guia, f, ensure_ascii=False, indent=2)

        tipo = str(guia.get("tipo") or pasta.name).strip() or pasta.name
        exemplos = {}
        for etapa in ETAPAS:
            sub = pasta / etapa
            exemplos[etapa] = (sorted(
                (p.name for p in sub.iterdir()
                 if p.is_file() and p.suffix.lower() in EXTENSOES),
                key=chave_natural) if sub.is_dir() else [])
        catalogo["atividades"][tipo] = {
            "tipo": tipo,
            "titulo": guia.get("titulo", ""),
            "descricao": guia.get("descricao", ""),
            "mostrar": guia.get("mostrar", {}),
            "exemplos": exemplos,
        }

    site_dir = dest_base / ATIVIDADE_SITE
    if site_dir.is_dir():
        for pasta in sorted(site_dir.iterdir()):
            if pasta.is_dir():
                catalogo["site"][pasta.name] = sorted(
                    (p.name for p in pasta.iterdir()
                     if p.is_file() and p.suffix.lower() in EXTENSOES),
                    key=chave_natural)

    catalogo_path = dest_base / NOME_CATALOGO
    with open(catalogo_path, "w", encoding="utf-8") as f:
        json.dump(catalogo, f, ensure_ascii=False, indent=2)
    return catalogo_path


def guardar_modelos(relatorio: str,
                    por_grupo: int = N_MODELOS_PADRAO,
                    base: Path | str | None = None,
                    somente: set[str] | None = None) -> Path:
    """Guarda fotos-modelo por TIPO de atividade p/ relatórios futuros.

    O que importa aprender é o que deve ser mostrado em cada tipo de
    atividade (ex: instalacao_bateria, protecao_bateria), não o relatório
    em si. Copia até `por_grupo` fotos por (tipo, etapa) e por tipo de
    site para Arquivos/Relatorios/_modelos/<tipo>/, preferindo Status OK
    e Confianca alta, grava _modelos/<tipo>/guia.json com o que deve ser
    mostrado em cada etapa e consolida tudo em _modelos/_catalogo.json.
    Nada é guardado por relatório. Não apaga nada.
    """
    base = Path(base) if base else BASE_RELATORIOS
    pasta_rel = base / sanitizar_nome(relatorio)
    csv_path = pasta_rel / NOME_EVIDENCIA
    linhas = carregar_evidencia(csv_path)
    if linhas is None:
        raise SystemExit(1)
    origem = resolver_origem(pasta_rel)
    escopo = carregar_escopo(pasta_rel) or escopo_template(relatorio)

    dest_base = base / PASTA_MODELOS
    dest_base.mkdir(parents=True, exist_ok=True)

    def melhores(candidatas: list[dict]) -> list[dict]:
        """Escolhe até `por_grupo` fotos BOAS e VARIADAS.

        Variedade: descarta 'similar a Foto (X)' / observação repetida e
        fotos a menos de 30 s de uma já escolhida (mesma cena/rajada).
        """
        from datetime import datetime

        def tempo(c):
            for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S.%f"):
                try:
                    return datetime.strptime(_campo(c, "datahora").strip(), fmt)
                except ValueError:
                    continue
            return None

        def chave(c):
            conf = {"alta": 0, "media": 1, "baixa": 2}.get(_campo(c, "confianca"), 3)
            ok = 0 if _campo(c, "status") == "OK" else 1
            try:
                ordem = int(str(_campo(c, "ordem") or "0"))
            except ValueError:
                ordem = 10 ** 9
            return (ok, conf, ordem)

        escolhidas: list[dict] = []
        obs_vistas: set[str] = set()
        tempos: list[datetime] = []
        for c in sorted(candidatas, key=chave):
            if len(escolhidas) >= por_grupo:
                break
            if _campo(c, "qualidade") != "boa":
                continue
            obs = _campo(c, "observacao").strip().lower()
            if "similar a" in obs or obs in obs_vistas:
                continue
            t = tempo(c)
            if t and any(abs((t - tc).total_seconds()) < 30 for tc in tempos):
                continue
            escolhidas.append(c)
            obs_vistas.add(obs)
            if t:
                tempos.append(t)
        return escolhidas

    def copiar_modelos(subpasta: Path, escolhidas: list[dict]) -> list[str]:
        subpasta.mkdir(parents=True, exist_ok=True)
        nomes = []
        for c in escolhidas:
            src = origem / _campo(c, "arquivo")
            if src.name and src.exists():
                if not (subpasta / src.name).exists():
                    shutil.copy2(src, subpasta / src.name)
                nomes.append(src.name)
        return nomes

    total = 0
    for ativ in escopo.get("atividades", []):
        aid = str(ativ.get("id") or "").strip()
        if not aid or (somente and aid not in somente):
            continue
        tipo = sanitizar_nome(str(ativ.get("tipo") or ativ.get("titulo") or aid).lower())
        for etapa in ETAPAS:
            grupo = [c for c in linhas if tem_vinculo(c, aid, etapa)]
            escolhidas = melhores(grupo)
            if not escolhidas:
                continue
            nomes = copiar_modelos(dest_base / tipo / etapa, escolhidas)
            total += len(nomes)
            ex = ativ.setdefault("exemplos", {"antes": [], "durante": [], "depois": []})
            ex[etapa] = nomes
        # guia do tipo: o que deve ser mostrado em cada etapa. Se o tipo
        # já existe de outro relatório, preserva o guia e só completa o
        # que faltar (o aprendizado é por atividade, não por relatório).
        guia_path = dest_base / tipo / "guia.json"
        guia = {}
        if guia_path.exists():
            try:
                with open(guia_path, encoding="utf-8") as f:
                    guia = json.load(f)
            except (OSError, json.JSONDecodeError):
                guia = {}
        guia["tipo"] = tipo
        guia.setdefault("titulo", ativ.get("titulo", ""))
        guia.setdefault("descricao", ativ.get("descricao", ""))
        if not guia.get("mostrar"):
            guia["mostrar"] = dict(ativ.get("evidencia", {}))
        guia.pop("exemplo_de", None)
        with open(guia_path, "w", encoding="utf-8") as f:
            json.dump(guia, f, ensure_ascii=False, indent=2)

    ex_site: dict[str, list[str]] = {}
    por_tipo: dict[str, list[dict]] = {}
    for c in linhas if not somente else []:
        if tem_vinculo(c, ATIVIDADE_SITE):
            por_tipo.setdefault(tipo_site(_campo(c, "observacao")), []).append(c)
    for tipo, grupo in sorted(por_tipo.items()):
        escolhidas = melhores(grupo)
        if not escolhidas:
            continue
        nomes = copiar_modelos(dest_base / ATIVIDADE_SITE / tipo, escolhidas)
        total += len(nomes)
        ex_site[tipo] = nomes
    if ex_site:
        escopo["exemplos_site"] = ex_site

    with open(pasta_rel / NOME_ESCOPO, "w", encoding="utf-8") as f:
        json.dump(escopo, f, ensure_ascii=False, indent=2)

    catalogo_path = atualizar_catalogo(dest_base)

    print(f"\nModelos (por tipo de atividade): {total} fotos -> {dest_base}/")
    print(f"Guia por tipo: {dest_base}/<tipo>/guia.json")
    print(f"Catálogo de atividades/exemplos: {catalogo_path}")
    print("Base permanente por TIPO de atividade — nada é guardado por relatório.")
    print("Nada foi apagado — a pasta do relatório pode ser apagada INTEIRA "
          "só quando o usuário mandar.")
    return dest_base


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Monta relatorio por atividade/etapa (antes/durante/depois). "
                    "Unico meio permitido de copiar — nao copie manualmente.")
    ap.add_argument("--relatorio", default=None,
                    help="nome do relatório (pasta em Arquivos/Relatorios/)")
    ap.add_argument("--origem", default=None,
                    help="pasta das fotos (padrao: fotos/ do relatorio, senao Fotos_Ordenadas)")
    ap.add_argument("--base", default=None,
                    help="base dos relatorios (padrao: Arquivos/Relatorios)")
    ap.add_argument("--preparar", action="store_true",
                    help="prepara o ambiente: copia fotos p/ fotos/, cria escopo.json "
                         "modelo + evidencia.csv todas PENDENTE")
    ap.add_argument("--modelos", action="store_true",
                    help="guarda fotos-modelo por tipo de atividade/site em _modelos/ "
                         "(+ _catalogo.json), sem histórico por relatório")
    ap.add_argument("--por-grupo", type=int, default=N_MODELOS_PADRAO,
                    help="fotos-modelo por (atividade, etapa) e por tipo de site "
                         f"(padrao: {N_MODELOS_PADRAO})")
    ap.add_argument("--so-atividade", default=None,
                    help="com --modelos: guarda só estas atividades (ids separados por vírgula, ex: 03)")
    ap.add_argument("--manter-destino", action="store_true",
                    help="nao limpa atividades/ antes de distribuir")
    ap.add_argument("--so-boas", action="store_true",
                    help="copia só qualidade boa (relatório final, sem "
                         "ruins/duplicadas)")
    args = ap.parse_args(argv)

    if not args.relatorio:
        ap.error("--relatorio é obrigatório (ex: --relatorio gna_fonte)")

    if args.preparar:
        preparar_relatorio(args.relatorio, pasta_origem=args.origem,
                           base=args.base)
        return

    if args.modelos:
        somente = ({a.strip() for a in args.so_atividade.split(",") if a.strip()}
                   if args.so_atividade else None)
        guardar_modelos(args.relatorio, por_grupo=args.por_grupo,
                        base=args.base, somente=somente)
        return

    distribuir(args.relatorio, pasta_origem=args.origem, base=args.base,
               limpar_destino=not args.manter_destino, so_boas=args.so_boas)


if __name__ == "__main__":
    main()
