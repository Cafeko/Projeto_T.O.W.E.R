# AGENTS.md — Montar Relatório (atividade + etapa)

> Instruções para qualquer agente externo executando esta funcionalidade.
> Idioma do usuário: português. Responda em português, de forma curta e direta.
>
> **Modelo de atuação: VOCÊ é o agente.**
> **VOCÊ mesmo abre e lê cada imagem** (sua visão) e preenche a tabela;
> o script `montar_relatorio.py` desta pasta só entra para copiar.
> **Nunca copie/renomeie foto por conta própria**
> (nada de `os.rename`, `shutil`, `move`, `copy` ou script ad-hoc).

## O que faz

Monta o relatório para **provar que o serviço foi feito**: fotos ordenadas
e agrupadas por **atividade do escopo**, cada uma na **etapa do processo**
(`antes` → `durante` → `depois`).

- **RELATÓRIO** = pasta de trabalho (`Arquivos/Relatorios/<relatorio>/`).
- **ATIVIDADE** = item do escopo com `id` estável (`01`, `02`...) + título.
  Uma foto pode ter **N vínculos**: separe por `;` alinhados
  (ex: `Atividade=02;03`, `Etapa=durante;depois` — a foto vai para as duas
  pastas). SITE ignora a etapa.
- **ETAPA** = só `antes`, `durante` ou `depois`. Sem etapa segura =
  `_NAO_IDENTIFICADAS/` (nunca descarta foto).
- **SITE** = atividade especial fixa, sem etapa, para as fotos padrão que
  todo relatório tem: rua/acesso, frente do site, portão, cadeado, torre,
  área interna, placa ID. Se a foto existir, marque `Atividade=SITE`
  (etapa vazia) e ela vai para `fotos_do_site/`; se não existir, deixe sem
  mesmo — nunca invente.

```
Arquivos/Relatorios/<relatorio>/
  fotos/                          # cópia permanente da entrada (Foto (n))
  escopo.json                     # ATIVIDADES + o que esperar em cada etapa + exemplos
  evidencia.csv                   # TABELA que VOCÊ preenche (1 foto = 1 atividade + 1 etapa)
  atividades/<id>_<slug>/         # após distribuir
    antes|durante|depois/Foto (n).ext
  fotos_do_site/                  # SITE (sem etapa): rua, frente, portão,
                                  #   cadeado, torre, área interna, placa ID
  _NAO_IDENTIFICADAS/             # fallback
  viewer.json                     # índice p/ UI futura

features/montar_relatorio/
  montar_relatorio.py             # --preparar + distribuir (único meio de copiar)
  avaliar_relatorio.py            # janela: avalia foto a foto, corrige e distribui (a pessoa opera)
  AGENTS.md                       # este arquivo
```

## Fluxo obrigatório

1. **Relatório** — pergunte o nome (ex: `gna_fonte_out2026`). Um por vez.
2. **Origem das fotos** — Enter = `Arquivos/Fotos_Ordenadas`. Se
   inválida/vazia, liste projeto e `Arquivos/`.
3. **Preparar** — rode `--preparar` (copia p/ `fotos/`, cria `escopo.json`
   modelo + `evidencia.csv` todas PENDENTE).
4. **Escopo (VOCÊ + usuário)** — edite `escopo.json`: para cada atividade,
   `id`, `titulo`, **`tipo`** (VERBO_OBJETO, ex: `desinstalacao_fonte`,
   `instalacao_bateria` — nunca genérico), `descricao` (1 frase) e
   `evidencia.antes/durante/depois`
   (1 frase visual cada — é o que guia a classificação). Se o usuário tiver
   2-3 fotos-modelo por etapa, registre em `exemplos` e **abra essas imagens
   com sua visão antes de classificar as novas** (few-shot). Se
   `_modelos/<tipo>/` já existir de outro relatório, abra o `guia.json` e
   as fotos de lá primeiro — é assim que a LLM aprende o que mostrar.
5. **Classificar (VOCÊ faz)** — abra e leia **cada imagem** de `fotos/` e
   preencha `evidencia.csv` no formato exato abaixo, pela **regra de foco**:
   só marque atividade+etapa se o conteúdo estiver nítido e identificável
   com segurança; na dúvida, deixe vazio (= `_NAO_IDENTIFICADAS`).
6. **Avaliar (pessoa na janela)** — abra `avaliar_relatorio.py
   --relatorio <nome>`: mostra foto + sugestão da IA na MESMA ordem da
   grade; Enter = acertou, ou monte os vínculos (+ Juntar p/ N atividades,
   − Tirar, Limpar = não identificada) e salve (OK). Filtros: Todas /
   por atividade / Boas p/ relatório / Não selecionadas. Botão
   **Miniaturas**: 1 clique seleciona e edita no painel, 2 cliques abre
   grande; voltar revela onde estava. Botões **Avaliar/Copiar p/ Excel**
   trocam o painel lateral: no modo Copiar, a mesma foto é copiada (Ctrl+C),
   enviada ao Excel aberto (Ctrl+E) ou salva no tamanho LxA — mesma config
   do fit_fotos. Atalhos: ← → navega, 1/2/3 etapa,
   0 limpa. O botão **Distribuir** monta as pastas sem sair da janela
   (marque "só boas" p/ pastas finais).
7. **Distribuir via script e resumir** — se não usou o botão da janela,
   rode `montar_relatorio.py --relatorio <nome>` e informe: nº fotos,
   nº atividades, contagem por etapa, destino.
8. **Ver/copiar** — abra `fit_fotos.py --pasta` na pasta da etapa para colar
   no Excel em ordem.
9. **Enxugar (só quando o usuário mandar)** — NUNCA apague nada por conta
   própria. Quando ele disser que o relatório está pronto, rode
   `--modelos`: guarda 2 fotos por **tipo de atividade** em
   `_modelos/<tipo>/antes|durante|depois/` (+ `guia.json` com o que deve
   ser mostrado), por tipo de site em `_modelos/SITE/<tipo>/`, e arquiva
   `escopo.json` + `evidencia.csv` em `_relatorios/<relatorio>/` (só texto).
   É esse acervo por tipo — não o relatório — que ensina os próximos (ex:
   outra `instalacao` ou `bateria`). Só então a pasta do relatório pode
   ser apagada **inteira**.

## Formato exato de `escopo.json`

```json
{
  "relatorio": "gna_fonte",
  "descricao": "Substituicao de fonte e protecao do site",
  "atividades": [
    {
      "id": "01",
      "titulo": "Troca da fonte",
      "tipo": "troca_fonte",
      "descricao": "Substituir a fonte queimada do painel.",
      "evidencia": {
        "antes": "fonte antiga com marca de queimado, painel aberto",
        "durante": "tecnico com fiacao solta, fonte fora do lugar",
        "depois": "fonte nova instalada, led aceso, painel fechado"
      },
      "exemplos": {"antes": [], "durante": [], "depois": []}
    }
  ]
}
```

- `id` é estável e é o que vai em `evidencia.csv` (nunca o título).
- `tipo` é o nome canônico da atividade, sempre VERBO + OBJETO
  (ex: `desinstalacao_fonte`, `instalacao_bateria`, `protecao_fonte`) —
  nunca genérico (`desinstalacao` sozinho não diz do quê). É por ele que
  os modelos são guardados e reaproveitados entre relatórios. Se
  `_modelos/<tipo>/` já existir, abra o `guia.json` e as fotos-modelo
  ANTES de classificar.
- `exemplos`: nomes de arquivo das fotos-modelo (opcional, mas recomendado).

## Formato exato de `evidencia.csv`

- Encoding **`utf-8-sig`**, uma linha por foto:

```
Arquivo,Ordem,DataHora,Atividade,Etapa,Confianca,Status,Observacao,Qualidade
Foto (1).jpeg,1,09/09/2026 15:15:52,01,antes,alta,OK,fonte antiga com mancha,boa
Foto (2).jpeg,2,09/09/2026 15:16:10,01,durante,media,SUGERIDA,tecnico mexendo na fiacao,boa
Foto (3).jpeg,3,,,,PENDENTE,sem elemento nitido,
```

- `Atividade` = `id` do escopo, ou `SITE` (fotos padrão do site, sem etapa).
  `Etapa` = `antes|durante|depois` (vazio = não identificada ou SITE).
- `Confianca` = `alta|media|baixa`. `Status` = `OK|SUGERIDA|PENDENTE|NAO_IDENTIFICADA`.
- `Qualidade` = `boa` (entra no relatório) | `ruim` (fraca) |
  `duplicada` (similar a outra melhor — indique a referência na observação:
  `similar a Foto (X)`) | vazio (foto fora do escopo).

## Regra de duplicadas (dedupe)

Fotos do mesmo assunto com carimbo próximo: escolha **uma** (a mais nítida
e bem enquadrada → `boa`) e marque as demais `duplicada` com
`similar a Foto (X)` na observação. `--so-boas` monta as pastas só com as
boas (relatório final); sem a flag, copia tudo (para avaliar).

## Regras

- **Nunca copiar/renomeie manualmente**: só via `montar_relatorio.py`.
- **1 foto = 1 atividade + 1 etapa** (diferente do classificar, que era N classes).
- **Ordem preservada**: mantém `Foto (n)` dentro de cada etapa.
- **Execução**: rode a partir da **raiz**; caminhos relativos contra a raiz.
- **Git**: `Arquivos/Relatorios/` é gitignored — não force commit de fotos.

## Comandos

```bash
# preparar ambiente (copia fotos, cria escopo modelo + evidencia PENDENTE)
python features/montar_relatorio/montar_relatorio.py --preparar --relatorio <nome> --origem Arquivos/Fotos_Ordenadas

# distribuir após preencher evidencia.csv (lê fotos/ do relatório sozinho)
python features/montar_relatorio/montar_relatorio.py --relatorio <nome>

# distribuir só as boas (pastas finais do relatório, sem ruins/duplicadas)
python features/montar_relatorio/montar_relatorio.py --relatorio <nome> --so-boas

# avaliar na janela (a pessoa valida/corrige; fica aberta; tem botão Distribuir)
python features/montar_relatorio/avaliar_relatorio.py --relatorio <nome>

# guardar modelos p/ relatórios futuros (SÓ após o usuário aprovar; não apaga nada)
python features/montar_relatorio/montar_relatorio.py --modelos --relatorio <nome>

# ver uma etapa no tamanho do Excel
python features/fit_fotos/fit_fotos.py --pasta "Arquivos/Relatorios/<relatorio>/atividades/01_<slug>/depois"
```
