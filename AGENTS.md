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
    resultado.csv              # tabela intermediária (cada feature documenta o formato)
  features/
    ordenar_fotos/             # funcionalidade 1
      AGENTS.md                # instruções ESPECÍFICAS — siga esse arquivo ao executar
      organizar_fotos.py       # script da funcionalidade
```

## Funcionalidades disponíveis

| Funcionalidade | Pasta | Instruções | O que faz |
|----------------|-------|------------|-----------|
| Ordenar fotos | `features/ordenar_fotos/` | [`features/ordenar_fotos/AGENTS.md`](features/ordenar_fotos/AGENTS.md) | Organiza fotos pela data/hora do carimbo visível na imagem |

## Como atuar

1. Descubra qual funcionalidade o usuário quer (se ambíguo, pergunte).
2. Abra e siga o `AGENTS.md` **daquela funcionalidade** — ele tem o fluxo, o formato de dados e os comandos exatos.
3. Rode os scripts sempre a partir da **raiz do projeto**; caminhos relativos se resolvem contra a raiz.
4. Para adicionar uma nova funcionalidade: crie `features/<nome>/` com seu script + seu `AGENTS.md` próprio, e registre a linha na tabela acima.

## Regras globais

- **Git**: `Arquivos/Fotos/` e `Arquivos/Fotos_Ordenadas/` são gitignored — não force commit de fotos. Commits só sob pedido explícito.
- Não crie scripts ad-hoc de cópia/renomeação: cada funcionalidade tem seu script oficial.
