# AGENTS.md — Ordenador de Fotos (Projeto T.O.W.E.R)

> Instruções para qualquer agente externo operando nesta pasta.
> Idioma do usuário: português. Responda em português, de forma curta e direta.

## O que é este projeto

Organiza fotos pela **data/hora do carimbo visível na imagem** (ex: `9 de setembro de 2026 17:58:53`).
Pipeline: **IA local de visão (Ollama `qwen2.5vl:3b`) lê a data → `Arquivos/resultado.csv` → cópia/renomeação ordenada**.

## Estrutura

```
agente_fotos.py       # fluxo conversacional completo (caminho p/ usuário final)
extrair_datas_ia.py   # etapa 1: extrai datas das fotos -> Arquivos/resultado.csv
organizar_fotos.py    # etapa 2: aplica a ordenação (copia ou renomeia)
Arquivos/
  Fotos/              # ENTRADA (gitignored - nunca commitar fotos)
  Fotos_Ordenadas/    # SAÍDA da cópia: Foto (1).ext ... Foto (n).ext (gitignored)
  resultado.csv       # intermediário: Arquivo,Data,Hora,Data/Hora,Status,Texto IA
```

Funções reutilizáveis (importe, não reinvente):

- `extrair_datas_ia.processar_pasta(pasta, csv_saida)` -> lista de resultados
- `organizar_fotos.aplicar_ordenacao(ordem, pasta_origem, pasta_destino, csv_path, modo)`
  - `ordem`: `"1"` = mais antiga primeiro, `"2"` = mais nova primeiro
  - `modo`: `"copia"` (padrão) ou `"renomear"`

## Fluxo obrigatório com o usuário

Sempre nesta ordem, perguntando antes de agir:

1. **Caminho das fotos** — aceite absoluto ou relativo à raiz do projeto. Enter = `Arquivos/fotos`. Se inválido/vazio, liste a pasta do projeto e `Arquivos/` para sugerir.
2. **Extrair datas** — via `processar_pasta`. Não prossiga se não houver resultados.
3. **Cópia ou renomear?** — `1` = criar cópia ordenada em `Arquivos\Fotos_Ordenadas`; `2` = renomear os originais na própria pasta. Aceite linguagem natural ("cria copia", "renomeia ai").
4. **Ordem** — `1` = mais antiga primeiro (`Foto (1)` = mais antiga); `2` = mais nova primeiro.
5. **Executar e resumir** — via `aplicar_ordenacao`, informe quantidade, destino e ordem usada.

## Regras

- **Nunca renomear/copiar fotos manualmente** (nada de `os.rename`/scripts ad-hoc): use sempre `aplicar_ordenacao`. O modo `renomear` usa 2 fases (temp → final) para evitar colisão — não reimplemente isso.
- **CSV**: sempre `utf-8-sig`; data normalizada `DD/MM/AAAA HH:MM:SS.mmm`; fotos sem data vão **por último**, nunca descartadas.
- **Dependências**: Ollama rodando (`ollama serve`) + `qwen2.5vl:3b` (extração) e `qwen2.5:3b` ou fallback (conversa). Se o Ollama estiver fora do ar, avise e siga o mesmo fluxo com regras locais — nunca trave.
- **Execução**: rode os scripts a partir da **raiz do projeto**; caminhos relativos se resolvem contra a raiz, não contra o CWD do terminal.
- **Compatibilidade**: preserve o CLI existente (`organizar_fotos.py [1|2|--antiga|--recente]`, `extrair_datas_ia.py` sem args).
- **Git**: `Arquivos/Fotos/` e `Arquivos/Fotos_Ordenadas/` são gitignored — não force commit de fotos. Commits só sob pedido explícito.

## Comandos

```bash
python agente_fotos.py --pasta Arquivos/fotos   # fluxo completo (recomendado)
python agente_fotos.py --sem-llm                # mesmo fluxo, sem LLM
python extrair_datas_ia.py                      # só extração
python organizar_fotos.py 1                     # só ordenação (1=antiga, 2=nova)
```
