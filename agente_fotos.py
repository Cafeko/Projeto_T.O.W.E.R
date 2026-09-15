"""Agente LLM para ordenar fotos pela data do carimbo visivel na imagem.

Fluxo (conduzido pelo agente):
  0. Inspeciona a pasta do projeto (estrutura, Arquivos/, resultado.csv)
  1. Pergunta o caminho das fotos (vale caminho absoluto ou relativo ao projeto)
  2. Lista + extrai as datas com IA visao (reaproveita extrair_datas_ia.py)
  3. Pergunta: renomear as existentes OU criar copia?
     - copia -> guardadas em "Arquivos\\Fotos_Ordenadas"
  4. Pergunta a ordem: mais antiga primeiro ou mais nova primeiro?
  5. Executa (reaproveita organizar_fotos.py) e resume.

O LLM (Ollama local) atua como cerebro do agente:
  - gera as falas / perguntas (com contexto real da pasta do projeto),
  - interpreta respostas em linguagem natural ("pode ser copia", "renomeia ai",
    "do mais antigo pro mais novo", ...),
  - decide a proxima ferramenta a chamar
    (inspecionar_projeto -> listar -> extrair -> ordenar).

Se o Ollama estiver fora do ar, o agente faz fallback para regras locais
e continua funcionando no mesmo fluxo.

Uso:
    python agente_fotos.py
    python agente_fotos.py --pasta Arquivos/fotos
    python agente_fotos.py --sem-llm        # forca modo sem LLM (regras)
    python agente_fotos.py --modelo qwen2.5:3b

Config via ambiente:
    MODELO_TEXTO  (default: qwen2.5:3b, fallback: qwen2.5vl:3b)
    OLLAMA_HOST   (default: http://localhost:11434)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests

# Reaproveita o pipeline existente como "ferramentas" do agente.
import extrair_datas_ia as extrator
import organizar_fotos as organizador

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
MODELO_TEXTO = os.getenv("MODELO_TEXTO", "qwen2.5:3b")
MODELO_VISAO = extrator.MODELO_IA  # qwen2.5vl:3b

# Pasta do projeto = pasta onde este script mora. O agente enxerga o projeto
# a partir daqui: caminhos relativos do usuario sao resolvidos contra ela.
RAIZ_PROJETO = Path(__file__).resolve().parent

PASTA_PADRAO = RAIZ_PROJETO / "Arquivos" / "fotos"
PASTA_COPIAS = RAIZ_PROJETO / "Arquivos" / "Fotos_Ordenadas"
CSV_PADRAO = RAIZ_PROJETO / "Arquivos" / "resultado.csv"

EXTENSOES = extrator.EXTENSOES_IMAGENS


# ============================================================
# Ferramentas de acesso a pasta do projeto
# ============================================================

def resolver_caminho(texto: str) -> Path:
    """Resolve o caminho digitado: absoluto vale como esta, relativo e
    relativo a RAIZ_PROJETO (nao ao diretorio atual do terminal)."""
    p = Path(texto.strip().strip('"').strip("'")).expanduser()
    if not p.is_absolute():
        p = RAIZ_PROJETO / p
    return p


def tool_listar_diretorio(caminho: Path) -> list[str]:
    """TOOL inspecionar pasta: lista entradas ('nome/' = subpasta)."""
    try:
        entradas = sorted(caminho.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except (FileNotFoundError, NotADirectoryError):
        return []
    nomes: list[str] = []
    for p in entradas:
        if p.name.startswith(".") or p.name in ("__pycache__", "env", ".git"):
            continue
        nomes.append(p.name + "/" if p.is_dir() else p.name)
    return nomes


def tool_resumo_projeto() -> dict:
    """TOOL resumo do projeto: estrutura + situacao de Arquivos/ + CSV."""
    arquivos_dir = RAIZ_PROJETO / "Arquivos"
    fotos = tool_listar_fotos(PASTA_PADRAO) if PASTA_PADRAO.exists() else []
    return {
        "raiz": str(RAIZ_PROJETO),
        "topo": tool_listar_diretorio(RAIZ_PROJETO),
        "arquivos": tool_listar_diretorio(arquivos_dir),
        "n_fotos_padrao": len(fotos),
        "csv_existe": CSV_PADRAO.exists(),
    }


def mostrar_resumo_projeto(resumo: dict) -> None:
    print(f"\n[agente: pasta do projeto -> {resumo['raiz']}]")
    print(f"[agente: conteudo -> {', '.join(resumo['topo']) or '(vazio)'}]")
    print(f"[agente: Arquivos/ -> {', '.join(resumo['arquivos']) or '(vazio)'}]")
    print(f"[agente: fotos na pasta padrao -> {resumo['n_fotos_padrao']}"
          + (f" | {CSV_PADRAO.name} existente" if resumo["csv_existe"] else "") + "]")


# ============================================================
# Camada LLM (Ollama /api/chat)
# ============================================================

def modelos_instalados() -> list[str]:
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if r.status_code == 200:
            return [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


def escolher_modelo_texto(preferido: str | None = None) -> str | None:
    """Retorna um modelo de texto disponivel, ou None se Ollama fora do ar."""
    instalados = modelos_instalados()
    if not instalados:
        return None
    candidatos = [preferido or MODELO_TEXTO, MODELO_TEXTO, MODELO_VISAO,
                  "qwen2.5:3b", "qwen2.5", "llama3.1:8b", "llama3.1", "mistral"]
    for cand in candidatos:
        if not cand:
            continue
        base = cand.split(":")[0].lower()
        for inst in instalados:
            if cand.lower() in inst.lower() or base in inst.lower():
                return inst
    # Ollama esta no ar mas sem nenhum modelo conhecido: tenta o preferido mesmo assim
    return preferido or MODELO_TEXTO


def llm_chat(modelo: str, system: str, user: str, timeout: int = 60) -> str | None:
    try:
        r = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": modelo,
                "stream": False,
                "options": {"temperature": 0},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=timeout,
        )
        if r.status_code == 200:
            return (r.json().get("message", {}).get("content", "") or "").strip() or None
    except Exception:
        pass
    return None


SYSTEM_AGENTE = (
    "Voce e o Agente Organizador de Fotos. Fale em portugues, de forma curta e direta. "
    "Voce conduz o usuario pelo fluxo: caminho das fotos -> extracao das datas -> "
    "escolha copia/renomear -> escolha da ordem -> conclusao."
)


def fala_do_agente(modelo: str | None, topico: str, detalhe: str = "") -> str:
    """Gera a fala do agente via LLM; fallback para texto fixo."""
    fallbacks = {
        "boas_vindas": "Ola! Sou o agente organizador de fotos. Vou te guiar passo a passo.",
        "pedir_caminho": f"Qual o caminho da pasta com as fotos? (Enter = {PASTA_PADRAO})",
        "pedir_modo": (
            "Datas extraidas! Agora escolha:\n"
            "  1 - Criar COPIA ordenada em 'Arquivos\\Fotos_Ordenadas'\n"
            "  2 - RENOMEAR os arquivos originais na propria pasta\n"
            "Digite 1 ou 2 (pode escrever, ex: 'cria copia'):"
        ),
        "pedir_ordem": (
            "Qual a ordem?\n"
            "  1 - Mais ANTIGA primeiro (Foto (1) = mais antiga)\n"
            "  2 - Mais NOVA primeiro (Foto (1) = mais recente)\n"
            "Digite 1 ou 2:"
        ),
    }
    if not modelo:
        if topico == "boas_vindas_extra":
            return fallbacks["boas_vindas"]
        return fallbacks.get(topico, detalhe or topico)
    if topico == "boas_vindas":
        txt = llm_chat(modelo, SYSTEM_AGENTE,
                       "Apresente-se em 1 frase curta e diga que vai pedir o caminho das fotos.")
        return txt or fallbacks["boas_vindas"]
    if topico == "pedir_caminho":
        txt = llm_chat(modelo, SYSTEM_AGENTE,
                       f"Peca o caminho da pasta de fotos em 1 frase. Diga que Enter usa '{PASTA_PADRAO}'.")
        return txt or fallbacks["pedir_caminho"]
    if topico == "pedir_modo":
        txt = llm_chat(
            modelo, SYSTEM_AGENTE,
            f"Voce extraiu datas de {detalhe} fotos. Pergunte se o usuario quer CRIAR COPIA "
            f"ordenada em 'Arquivos\\Fotos_Ordenadas' ou RENOMEAR os originais. Pecas para responder 1 ou 2.")
        return txt or fallbacks["pedir_modo"]
    if topico == "pedir_ordem":
        txt = llm_chat(modelo, SYSTEM_AGENTE,
                       "Pergunte a ordem: 1 = mais antiga primeiro, 2 = mais nova primeiro.")
        return txt or fallbacks["pedir_ordem"]
    if topico == "resumo":
        txt = llm_chat(modelo, SYSTEM_AGENTE,
                       f"Resuma em 2 frases curtas esta conclusao: {detalhe}")
        return txt or detalhe
    return detalhe or topico


def interpretar_modo(modelo: str | None, resposta: str) -> str:
    """Interpreta resposta livre -> 'copia' ou 'renomear'."""
    r = resposta.strip().lower()
    if modelo:
        out = llm_chat(
            modelo,
            "Voce classifica a resposta do usuario. Responda com UMA palavra: COPIA ou RENOMEAR.",
            f"O usuario escolhe entre criar copia ordenada ou renomear originais. Resposta: '{resposta}'. "
            "COPIA se ele quer copia/duplicar/salvar em outra pasta/1. RENOMEAR se quer renomear/originais/2.",
        )
        if out:
            u = out.strip().upper()
            if "RENOMEAR" in u:
                return "renomear"
            if "COPIA" in u or u == "1":
                return "copia"
    if r in ("1", "copia", "cópia", "copiar"):
        return "copia"
    if r in ("2", "renomear", "renomeia", "renomeação", "renomeacao"):
        return "renomear"
    if any(p in r for p in ("copia", "cópia", "copiar", "duplic", "outra pasta", "ordenadas")):
        return "copia"
    if any(p in r for p in ("renome", "origin", "mesma pasta", "existente")):
        return "renomear"
    if r == "1":
        return "copia"
    if r == "2":
        return "renomear"
    return ""


def interpretar_ordem(modelo: str | None, resposta: str) -> str:
    """Interpreta resposta livre -> '1' (antiga) ou '2' (nova)."""
    r = resposta.strip().lower()
    if modelo:
        out = llm_chat(
            modelo,
            "Voce classifica a ordem. Responda com UM digito: 1 ou 2.",
            f"1 = mais antiga primeiro, 2 = mais nova/recente primeiro. Resposta do usuario: '{resposta}'.",
        )
        if out:
            for ch in out.strip():
                if ch in ("1", "2"):
                    return ch
    if r in ("1", "2"):
        return r
    if any(p in r for p in ("antiga", "antigo", "crescente", "primeira foto mais velha")):
        return "1"
    if any(p in r for p in ("nova", "recente", "decrescente", "novo primeiro")):
        return "2"
    return ""


# ============================================================
# Ferramentas (tools) do agente
# ============================================================

def tool_listar_fotos(caminho: Path) -> list[Path]:
    """TOOL listar_fotos: retorna imagens da pasta."""
    if not caminho.exists():
        return []
    return sorted(p for p in caminho.iterdir()
                  if p.is_file() and p.suffix.lower() in EXTENSOES)


def tool_extrair_datas(caminho: Path, csv_saida: Path):
    """TOOL extrair_datas: usa o pipeline IA existente."""
    print(f"\n[agente: ferramenta extrair_datas -> {caminho}]")
    return extrator.processar_pasta(pasta=caminho, csv_saida=csv_saida)


def tool_aplicar_ordenacao(ordem: str, origem: Path, modo: str):
    """TOOL aplicar_ordenacao: copia ou renomeia."""
    destino = PASTA_COPIAS if modo == "copia" else origem
    print(f"\n[agente: ferramenta aplicar_ordenacao modo={modo} ordem={ordem}]")
    return organizador.aplicar_ordenacao(
        ordem, pasta_origem=origem, pasta_destino=destino,
        csv_path=CSV_PADRAO, modo=modo,
    )


# ============================================================
# Loop do agente
# ============================================================

def perguntar_caminho(modelo: str | None, inicial: str | None) -> Path:
    if inicial:
        p = resolver_caminho(inicial)
        if p.exists() and tool_listar_fotos(p):
            print(f"[agente: usando pasta informada -> {p}]")
            return p
        print(f"Pasta '{inicial}' vazia ou nao encontrada. Vamos tentar de novo.")
    print(fala_do_agente(modelo, "pedir_caminho"))
    while True:
        resp = input("> ").strip()
        p = PASTA_PADRAO if not resp else resolver_caminho(resp)
        if not p.exists():
            print(f"Pasta '{p}' nao existe.")
            sugerir_pastas()
            continue
        fotos = tool_listar_fotos(p)
        if not fotos:
            print(f"Nenhuma imagem em '{p}'.")
            sugerir_pastas()
            continue
        print(f"[agente: encontrei {len(fotos)} fotos em '{p}']")
        return p


def sugerir_pastas() -> None:
    """O agente olha a pasta do projeto e sugere onde podem estar as fotos."""
    raiz = tool_listar_diretorio(RAIZ_PROJETO)
    arq = tool_listar_diretorio(RAIZ_PROJETO / "Arquivos")
    print(f"[agente: na pasta do projeto ha: {', '.join(raiz) or '(vazio)'}]")
    if arq:
        print(f"[agente: em Arquivos/ ha: {', '.join(arq)}]")
    print("Digite outro caminho (absoluto ou relativo a pasta do projeto).")


def perguntar_modo(modelo: str | None, n_fotos: int) -> str:
    print("\n" + fala_do_agente(modelo, "pedir_modo", str(n_fotos)))
    while True:
        modo = interpretar_modo(modelo, input("> "))
        if modo in ("copia", "renomear"):
            label = "criar copia em 'Arquivos\\Fotos_Ordenadas'" if modo == "copia" else "renomear os originais"
            print(f"[agente: entendi -> {label}]")
            return modo
        print("Nao entendi. Digite 1 (copia) ou 2 (renomear).")


def perguntar_ordem(modelo: str | None) -> str:
    print("\n" + fala_do_agente(modelo, "pedir_ordem"))
    while True:
        ordem = interpretar_ordem(modelo, input("> "))
        if ordem in ("1", "2"):
            label = "mais antiga primeiro" if ordem == "1" else "mais nova primeiro"
            print(f"[agente: entendi -> {label}]")
            return ordem
        print("Nao entendi. Digite 1 (antiga primeiro) ou 2 (nova primeiro).")


def main() -> None:
    ap = argparse.ArgumentParser(description="Agente LLM organizador de fotos")
    ap.add_argument("--pasta", default=None, help="Caminho inicial das fotos")
    ap.add_argument("--modelo", default=None, help="Modelo de texto do Ollama")
    ap.add_argument("--sem-llm", action="store_true", help="Desativa o LLM (usa regras locais)")
    args = ap.parse_args()

    modelo = None if args.sem_llm else escolher_modelo_texto(args.modelo)
    if args.sem_llm:
        print("[agente: modo sem-LLM (regras locais)]")
    elif modelo:
        print(f"[agente: LLM conectado -> {modelo}]")
    else:
        print("[agente: Ollama indisponivel - seguindo com regras locais no mesmo fluxo]")

    print(fala_do_agente(modelo, "boas_vindas"))

    # Passo 0: o agente inspeciona a pasta do projeto (TOOL)
    resumo = tool_resumo_projeto()
    mostrar_resumo_projeto(resumo)

    # Passo 1-2: caminho + extracao (TOOLS)
    origem = perguntar_caminho(modelo, args.pasta)
    resultados = tool_extrair_datas(origem, CSV_PADRAO)
    if not resultados:
        print("Nada para ordenar. Encerrando.")
        return

    # Passo 3-4: modo + ordem (LLM interpreta linguagem natural)
    modo = perguntar_modo(modelo, len(resultados))
    ordem = perguntar_ordem(modelo)

    # Passo 5: execucao (TOOL)
    feitos = tool_aplicar_ordenacao(ordem, origem, modo)
    ordem_txt = "mais antiga primeiro" if ordem == "1" else "mais nova primeiro"
    if modo == "copia":
        destino_txt = (f"{len(feitos)} copias ordenadas ({ordem_txt}) "
                       f"salvas em '{PASTA_COPIAS}'")
    else:
        destino_txt = (f"{len(feitos)} arquivos renomeados na propria pasta "
                       f"'{origem}' ({ordem_txt})")
    print("\n" + fala_do_agente(modelo, "resumo", f"Pronto! {destino_txt}. CSV em '{CSV_PADRAO}'."))


if __name__ == "__main__":
    sys.exit(main())
