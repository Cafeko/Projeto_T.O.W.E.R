# Projeto T.O.W.E.R

Projeto multi-funcionalidades operado por **agente externo** (OpenCode, Claude Code, Cursor…).
Cada funcionalidade mora na sua própria pasta em `features/` e o agente segue o `AGENTS.md` dela.

## Funcionalidades

| Funcionalidade | Pasta | Docs do agente |
|----------------|-------|----------------|
| Ordenar fotos | `features/ordenar_fotos/` | [`features/ordenar_fotos/AGENTS.md`](features/ordenar_fotos/AGENTS.md) |

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
│   └── resultado.csv           # intermediário: Arquivo,Data,Hora,Data/Hora,Status,Texto IA
└── features/
    └── ordenar_fotos/          # funcionalidade 1
        ├── AGENTS.md           # fluxo exato do agente
        └── organizar_fotos.py  # único meio permitido de copiar/renomear
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

## Requisitos

- Python 3.10+
- `pip install -r requisitos.txt` (hoje: só biblioteca padrão — nada a instalar)

## Notas

- Rode os scripts a partir da **raiz do projeto**; caminhos relativos se resolvem contra a raiz.
- `Arquivos/Fotos/` e `Arquivos/Fotos_Ordenadas/` são ignorados pelo git — nunca commite fotos.
