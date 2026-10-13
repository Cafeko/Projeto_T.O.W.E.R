# Projeto T.O.W.E.R

Projeto multi-funcionalidades operado por **agente externo** (OpenCode, Claude Code, Cursor…).
Cada funcionalidade mora na sua própria pasta em `features/` e o agente segue o `AGENTS.md` dela.

## Funcionalidades

| Funcionalidade | Pasta | Docs do agente |
|----------------|-------|----------------|
| Ordenar fotos | `features/ordenar_fotos/` | [`features/ordenar_fotos/AGENTS.md`](features/ordenar_fotos/AGENTS.md) |
| Fotos no tamanho do Excel | `features/fit_fotos/` | [`features/fit_fotos/AGENTS.md`](features/fit_fotos/AGENTS.md) |
| Classificar fotos | `features/classificar_fotos/` | [`features/classificar_fotos/AGENTS.md`](features/classificar_fotos/AGENTS.md) |

Organiza fotos pela **data/hora do carimbo visível na imagem** (ex: `quarta-feira, 9 de setembro de 2026 17:58:53`).
Pipeline: **agente lê as imagens → `Arquivos/resultado.csv` → cópia ou renomeação ordenada** (`Foto (1)`, `Foto (2)`, …).

## Estrutura

```
Projeto_T.O.W.E.R/
├── AGENTS.md                   # roteador do agente (comece aqui)
├── README.md                   # esta visão geral
├── requisitos.txt              # dependências (só stdlib no momento)
├── Arquivos/                   # dados compartilhados na raiz
│   ├── Fotos/                  # ENTRADA - coloque as fotos aqui (ignorado pelo git)
│   ├── Fotos_Ordenadas/        # SAÍDA da cópia (ignorado pelo git)
│   ├── Classificadas/          # SAÍDA por relatório: <relatorio>/<classe>/ + classificacao.csv + viewer.json (ignorado)
│   └── resultado.csv           # intermediário: Arquivo,Data,Hora,Data/Hora,Status,Texto IA
└── features/
    ├── ordenar_fotos/          # funcionalidade 1
    │   ├── AGENTS.md           # fluxo exato do agente
    │   └── organizar_fotos.py  # único meio permitido de copiar/renomear
    ├── fit_fotos/              # funcionalidade 2
    │   ├── AGENTS.md           # fluxo exato do agente (só abre o programa)
    │   └── fit_fotos.py        # janela gráfica: tamanho px/cm, copiar ou salvar
    └── classificar_fotos/      # funcionalidade 3
        ├── AGENTS.md           # fluxo exato (preparar → treino → distribuir)
        ├── classificar_fotos.py # --preparar ambiente + distribui por classe
        └── modo_treino.py      # janela treino estilo fit_fotos (humano valida)
```

## Uso (agente externo)

1. Abra a pasta do projeto no seu agente. Ele lê o `AGENTS.md` da raiz e depois o da funcionalidade.
2. O agente **lê cada imagem com a própria visão**, grava `Arquivos/resultado.csv` e executa o script da feature.
3. O agente **nunca renomeia/copia manualmente** — só via script oficial.

Comandos da funcionalidade ordenar-fotos (a partir da **raiz**):

```bash
python features/ordenar_fotos/organizar_fotos.py 1 --origem Arquivos/Fotos --modo copia     # antiga primeiro
python features/ordenar_fotos/organizar_fotos.py 2 --origem Arquivos/Fotos --modo copia     # nova primeiro
python features/ordenar_fotos/organizar_fotos.py 1 --origem Arquivos/Fotos --modo renomear  # renomeia, antiga primeiro
python features/ordenar_fotos/organizar_fotos.py --help
```

Formato do CSV (`utf-8-sig`):

```
Arquivo,Data,Hora,Data/Hora,Status,Texto IA
image.jpeg,09/09/2026,15:15:52.775,09/09/2026 15:15:52.775,OK,09/09/2026 15:15:52.775
semdata.jpeg,,,,DATA NÃO ENCONTRADA,texto lido na imagem
```

Fotos sem data legível ficam com Data/Hora vazios e vão por último — nunca são descartadas.
Ao concluir, o script limpa o CSV (só cabeçalho); `--manter-csv` desativa isso.

## Uso (fit_fotos — fotos no tamanho do Excel)

```bash
python features/fit_fotos/fit_fotos.py --pasta Arquivos/Fotos
```

Abre a janela: escolha a pasta, clique na foto (ou navegue com ← →),
digite largura x altura em
**px ou cm** (cm usa o DPI informado, padrão 96 como no Excel), marque
**manter proporção** (sem distorcer) ou deixe desmarcado para o tamanho exato.
Depois **copie** a selecionada (Ctrl+C — pronta para Ctrl+V no Excel) ou
**salve todas** redimensionadas (padrão: `Arquivos/Fotos_Fit/`).
Ou **Envie p/ Excel**: insere a foto full-res direto na planilha aberta, já no
tamanho — nítida como reduzir no Excel, sem arrastar (exige Excel aberto).
Com **Alta resolução** marcado (padrão), a foto vai com os pixels originais e
só o tamanho de exibição é ajustado — sem perda de qualidade.
O programa lembra pasta, tamanho e opções ao reabrir (`~/.fit_fotos.json`).

## Uso (classificar_fotos — ambiente + treino + distribuição)

```bash
python features/classificar_fotos/classificar_fotos.py --preparar --relatorio gna_fonte --origem Arquivos/Fotos_Ordenadas
python features/classificar_fotos/modo_treino.py --relatorio gna_fonte
python features/classificar_fotos/classificar_fotos.py --relatorio gna_fonte
python features/fit_fotos/fit_fotos.py --pasta Arquivos/Classificadas/gna_fonte/fonte_trocada
```

`--preparar` cria o ambiente (`fotos/` + CSV todas PENDENTE + viewer) sem
classificar e sem sugerir por nome; a tentativa é por conteúdo e a pessoa
corrige/classifica o resto no treino (cada foto validada vai p/
`_dataset/<classe>/`, cópia permanente — pode apagar os originais);
mesma foto pode ir para N classes (`Classes` separadas por `;`).

## Fluxo relatório novo (ordenar → classificar)

Diga ao agente "novo relatório". Ele pergunta o **nome do relatório** e
**de onde pegar as fotos**, ordena, prepara o ambiente, abre o treino e
distribui. Cada funcionalidade também funciona **separada**.

## Requisitos

- Python 3.10+
- `pip install -r requisitos.txt` (pillow — redimensionamento do fit_fotos; ordenar e classificar usam só stdlib)

## Notas

- Rode os scripts a partir da **raiz do projeto**; caminhos relativos se resolvem contra a raiz.
- `Arquivos/Fotos/`, `Arquivos/Fotos_Ordenadas/` e `Arquivos/Classificadas/` são ignorados pelo git — nunca commite fotos.
