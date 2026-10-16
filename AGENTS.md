# AGENTS.md — Projeto T.O.W.E.R

> Instruções para qualquer agente externo operando neste projeto.
> Idioma do usuário: português. Responda em português, de forma curta e direta.
>
> **Modelo de atuação: VOCÊ é o agente.**
> **VOCÊ mesmo abre e lê cada imagem** (sua visão) quando a funcionalidade pedir;
> a ordenação/cópia física é **sempre** via script da funcionalidade.
> **Nunca renomeie/copie arquivos por conta própria**
> (nada de `os.rename`, `shutil`, `move`, `copy` ou script ad-hoc).

## Estrutura (multi-funcionalidades)

```
Projeto_T.O.W.E.R/
  AGENTS.md                    # este roteador (você está aqui)
  README.md                    # visão geral do projeto
  requisitos.txt               # dependências Python
  Arquivos/                    # dados compartilhados na raiz
    Fotos/                     # ENTRADA típica (gitignored)
    Fotos_Ordenadas/           # SAÍDA da cópia (gitignored)
    Classificadas/             # SAÍDA por relatório: <relatorio>/<classe>/ + classificacao.csv + viewer.json (gitignored)
    resultado.csv              # tabela intermediária (cada feature documenta o formato)
  features/
    ordenar_fotos/             # funcionalidade 1
      AGENTS.md                # instruções ESPECÍFICAS — siga esse arquivo ao executar
      organizar_fotos.py       # script da funcionalidade
    fit_fotos/                 # funcionalidade 2
      AGENTS.md                # instruções ESPECÍFICAS — siga esse arquivo ao executar
      fit_fotos.py             # janela gráfica (o agente só ABRE o programa)
    classificar_fotos/         # funcionalidade 3
      AGENTS.md                # instruções ESPECÍFICAS — siga esse arquivo ao executar
      classificar_fotos.py     # distribui fotos ordenadas por relatório/classe (multi-rótulo)
    montar_relatorio/          # funcionalidade 4 (foco atual)
      AGENTS.md                # instruções ESPECÍFICAS — siga esse arquivo ao executar
      montar_relatorio.py      # agrupa por atividade do escopo + etapa (antes/durante/depois)
```

## Funcionalidades disponíveis

| Funcionalidade | Pasta | Instruções | O que faz |
|----------------|-------|------------|-----------|
| Ordenar fotos | `features/ordenar_fotos/` | [`features/ordenar_fotos/AGENTS.md`](features/ordenar_fotos/AGENTS.md) | Organiza fotos pela data/hora do carimbo visível na imagem |
| Fotos no tamanho do Excel | `features/fit_fotos/` | [`features/fit_fotos/AGENTS.md`](features/fit_fotos/AGENTS.md) | Janela gráfica: vê fotos, escolhe tamanho (px/cm), copia ou salva |
| Classificar fotos | `features/classificar_fotos/` | [`features/classificar_fotos/AGENTS.md`](features/classificar_fotos/AGENTS.md) | Classifica fotos ordenadas por relatório/classe (multi-rótulo), pronto p/ UI estilo fit_fotos |
| Montar relatório | `features/montar_relatorio/` | [`features/montar_relatorio/AGENTS.md`](features/montar_relatorio/AGENTS.md) | Agrupa por atividade do escopo + etapa (antes/durante/depois) p/ provar serviço feito |

## Como atuar

1. Descubra o que o usuário quer (se ambíguo, pergunte):
   - **só ordenar**, **só classificar** (relatório já preparado ou fotos já
     ordenadas), **só fit** (ver/copiar) — cada funcionalidade funciona
     **separada**; siga o `AGENTS.md` dela;
   - **relatório novo** (fluxo completo) — ver seção abaixo.
2. Abra e siga o `AGENTS.md` **daquela funcionalidade** — ele tem o fluxo, o formato de dados e os comandos exatos.
3. Rode os scripts sempre a partir da **raiz do projeto**; caminhos relativos se resolvem contra a raiz.
4. Para adicionar uma nova funcionalidade: crie `features/<nome>/` com seu script + seu `AGENTS.md` próprio, e registre a linha na tabela acima.

## Fluxo relatório novo (ordenar → classificar)

Quando o usuário disser "novo relatório" (ou pedir ordenar + classificar juntos):

1. **Pergunte antes de agir** (as duas coisas juntas):
   - nome do **relatório** (pasta de trabalho, ex: `gna_fonte_out2026`);
   - **de onde pegar as fotos** p/ ordenar (absoluto ou relativo à raiz;
     Enter = `Arquivos/Fotos`; se inválido, liste projeto e `Arquivos/`).
2. **Ordene** seguindo `features/ordenar_fotos/AGENTS.md`
   (modo copia, antiga primeiro, salvo pedido diferente).
3. **Prepare** o ambiente seguindo `features/classificar_fotos/AGENTS.md`
   passo 0 (`--preparar --relatorio <nome>`
   `--origem Arquivos/Fotos_Ordenadas`).
4. **Treino**: abra `modo_treino.py --relatorio <nome>` para a pessoa
   classificar (seção Modo treino da feature).
5. **Distribua** (`classificar_fotos.py --relatorio <nome>`) e resuma.

## Regras globais

- **Git**: `Arquivos/Fotos/`, `Arquivos/Fotos_Ordenadas/` e `Arquivos/Classificadas/` são gitignored — não force commit de fotos. Commits só sob pedido explícito.
- Não crie scripts ad-hoc de cópia/renomeação: cada funcionalidade tem seu script oficial.
