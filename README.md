# Telecom - Ordenador de Fotos por Data

Organiza fotos pela **data/hora do carimbo visível na imagem** (ex: `quarta-feira, 9 de setembro de 2026 17:58:53`). Útil para gerar relatórios de atividades de Telecom com as fotos em ordem cronológica.

Pipeline: **IA local de visão lê a data → `Arquivos/resultado.csv` → cópia ou renomeação ordenada (`Foto (1)`, `Foto (2)`, …)**.

## Como funciona (visão geral)

1. **Você aponta a pasta com as fotos.** Pode ser `Arquivos/Fotos` ou qualquer outra pasta (caminho absoluto ou relativo à raiz do projeto).
2. **A IA extrai a data de cada foto.** O modelo de visão `qwen2.5vl:3b` (via Ollama, tudo local) lê o carimbo de data/hora na imagem, em até 3 tentativas por foto (imagem completa → recorte do rodapé → imagem maior). Cada data é normalizada para o formato `DD/MM/AAAA HH:MM:SS.mmm` e salva em `Arquivos/resultado.csv`. Fotos sem data legível **não são descartadas**: vão para o final da ordenação.
3. **Você escolhe cópia ou renomear.**
   - **Cópia:** os originais ficam intactos e as cópias ordenadas vão para `Arquivos\Fotos_Ordenadas`.
   - **Renomear:** os arquivos da própria pasta de origem são renomeados (em 2 fases, via nomes temporários, para não haver colisão).
4. **Você escolhe a ordem:** mais antiga primeiro (`Foto (1)` = mais antiga) ou mais nova primeiro (`Foto (1)` = mais recente).
5. **Pronto:** arquivos `Foto (1).ext`, `Foto (2).ext`, … (a extensão original de cada foto é mantida).

## Estrutura

```
Projeto_T.O.W.E.R/
├── agente_fotos.py       # fluxo conversacional completo com LLM ← use este
├── extrair_datas_ia.py   # etapa 1: extrai datas das fotos -> Arquivos/resultado.csv
├── organizar_fotos.py    # etapa 2: aplica a ordenação (copia ou renomeia)
├── AGENTS.md             # instruções para agentes externos (OpenCode, Claude Code, etc.)
├── requisitos.txt        # pillow, requests (+ resto do ambiente)
├── Arquivos/
│   ├── Fotos/            # ENTRADA - coloque as fotos aqui (ignorado pelo git)
│   ├── Fotos_Ordenadas/  # SAÍDA da cópia (ignorado pelo git)
│   └── resultado.csv     # intermediário: Arquivo,Data,Hora,Data/Hora,Status,Texto IA
```

## Requisitos

- Python 3.10+
- Ollama rodando + modelo de visão `qwen2.5vl:3b` (~3,2 GB). Para a conversa do agente, `qwen2.5:3b` (ou o próprio `qwen2.5vl:3b` como fallback).

```bash
# 1. Ollama - https://ollama.com/download
ollama pull qwen2.5vl:3b
ollama pull qwen2.5:3b    # opcional, para a conversa do agente
ollama serve              # deixar rodando

# 2. Dependências Python
pip install -r requisitos.txt
```

## Uso recomendado: agente LLM

```bash
python agente_fotos.py
python agente_fotos.py --pasta Arquivos/fotos
python agente_fotos.py --sem-llm         # mesmo fluxo, sem LLM (regras locais)
python agente_fotos.py --modelo qwen2.5:3b
```

Passo a passo do que o agente faz:

| Passo | O que acontece |
|-------|----------------|
| 0 | Inspeciona a pasta do projeto (estrutura, `Arquivos/`, fotos na pasta padrão, se já existe `resultado.csv`) e mostra o resumo |
| 1 | Pergunta o caminho das fotos (Enter = `Arquivos/fotos`). Se o caminho for inválido ou vazio, sugere pastas a partir do que viu no projeto |
| 2 | Extrai as datas com a IA de visão (mesmo pipeline de `extrair_datas_ia.py`) |
| 3 | Pergunta: **criar cópia** em `Arquivos\Fotos_Ordenadas` **ou renomear** os originais? Aceita linguagem natural ("cria copia", "renomeia ai") |
| 4 | Pergunta a ordem: **mais antiga primeiro** ou **mais nova primeiro**? |
| 5 | Executa e resume (quantidade, destino e ordem usada) |

O LLM (Ollama local, configurável por `MODELO_TEXTO` ou `--modelo`) gera as falas e interpreta as respostas livres — ele **só decide e conversa**; quem copia/renomeia de fato são os scripts. Se o Ollama estiver fora do ar, o agente segue o mesmo fluxo com regras locais.

## Os scripts em detalhe

### `extrair_datas_ia.py` — etapa 1 (extração)

```bash
python extrair_datas_ia.py
# ou como função: extrair_datas_ia.processar_pasta(pasta, csv_saida)
```

- Lê `Arquivos/Fotos` (`jpg`/`jpeg`/`png`/`webp`/`bmp`/`tif`) — aceita qualquer ano e formato de carimbo (`DD/MM/AAAA`, `AAAA-MM-DD`, `9 de setembro de 2024`, `September 9, 2024`, com ou sem hora/milissegundos, em PT ou EN).
- Para cada foto, consulta o Ollama em `http://localhost:11434/api/generate`, em até 3 tentativas (896 px completa → recorte dos 30% inferiores a 1000 px → 1100 px completa), com retry e pausas para não sobrecarregar em lotes grandes.
- `parse_data()` normaliza tudo para `DD/MM/AAAA HH:MM:SS.mmm` e limpa sujeira que a IA às vezes inclui (coordenadas GPS, endereços).
- Mostra progresso (`1/150 - foto.jpg -> 09/09/2026 17:58:59.801 OK`), salva `Arquivos/resultado.csv` já ordenado (antiga → recente) e descarrega o modelo da memória ao final (`keep_alive: 0`).

Exemplo de `resultado.csv`:

```
Arquivo,Data,Hora,Data/Hora,Status,Texto IA
image.jpeg,09/09/2026,15:15:52.775,09/09/2026 15:15:52.775,OK,09/09/2026 15:15:52.775
semdata.jpeg,,,,DATA NÃO ENCONTRADA,texto lido na imagem
```

### `organizar_fotos.py` — etapa 2 (ordenação)

```bash
python organizar_fotos.py          # interativo
python organizar_fotos.py 1        # mais antiga primeiro -> Foto (1) = mais antiga
python organizar_fotos.py 2        # mais recente primeiro -> Foto (1) = mais recente
python organizar_fotos.py --antiga
python organizar_fotos.py --recente
# ou como função:
# organizar_fotos.aplicar_ordenacao(ordem, pasta_origem, pasta_destino, csv_path, modo)
#   ordem: "1" (antiga) | "2" (nova) — modo: "copia" | "renomear"
```

- Lê o `resultado.csv` e ordena por data/hora. **Fotos sem data vão por último**, mantendo a ordem original entre elas.
- **Modo cópia** (padrão): limpa `Arquivos/Fotos_Ordenadas` e copia com `shutil.copy2` como `Foto (1).ext` … `Foto (n).ext`, mantendo a extensão original de cada foto.
- **Modo renomear**: renomeia dentro da própria pasta de origem, em 2 fases (nome temporário → nome final) para evitar colisões quando o destino já existe.

### `agente_fotos.py` — o orquestrador

Junta as duas etapas num fluxo conversacional. Ferramentas que ele usa (todas reaproveitam os scripts acima, o LLM nunca toca em arquivos diretamente):

- `tool_resumo_projeto` / `tool_listar_diretorio` — enxerga a pasta do projeto
- `tool_extrair_datas` → `extrair_datas_ia.processar_pasta`
- `tool_aplicar_ordenacao` → `organizar_fotos.aplicar_ordenacao`

## Fluxo manual (sem agente)

```bash
python extrair_datas_ia.py
python organizar_fotos.py 1
```

## Notas

- Rode os scripts a partir da **raiz do projeto**; caminhos relativos se resolvem contra a raiz.
- O modelo é descarregado da RAM automaticamente ao final (`ollama ps` fica vazio). Se interromper com Ctrl+C, libere manual: `ollama stop qwen2.5vl:3b`.
- Para trocar o modelo de visão: `ollama pull llava:7b` e altere `MODELO_IA` em `extrair_datas_ia.py`. O modelo de conversa se troca via `--modelo` ou variável `MODELO_TEXTO`.
- `Arquivos/Fotos/` e `Arquivos/Fotos_Ordenadas/` são ignorados pelo git — nunca commite fotos.
- Código próprio é MIT/domínio público. Bibliotecas (Pillow/MIT, requests/Apache 2.0, Ollama/MIT, Qwen/Apache 2.0) são livres para uso comercial com aviso de licença.
