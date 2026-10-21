# AGENTS.md — Classificar Fotos

> Instruções para qualquer agente externo executando esta funcionalidade.
> Idioma do usuário: português. Responda em português, de forma curta e direta.
>
> **Modelo de atuação: o script prepara o ambiente e a PESSOA classifica
> no modo treino.** Você executa os comandos e orienta; só classifique com
> sua visão se o usuário pedir explicitamente.
> A cópia física é **sempre** via script desta pasta.
> **Nunca copie/renomeie foto por conta própria**
> (nada de `os.rename`, `shutil`, `move`, `copy` ou script ad-hoc).

> **Atenção — não confundir:** aqui **RELATÓRIO = lote de trabalho** para
> classificar por **classe**. Isto **não** é o relatório final de serviço
> (agrupado por **atividade + etapa**), que é a funcionalidade
> `features/montar_relatorio/`.

## O que faz

Prepara o ambiente de cada **relatório** e classifica as fotos por **classe**.
Uma mesma foto pode ter **N classes** — ela é copiada para N pastas,
mantendo o nome ordenado (`Foto (1).ext`) para exibir depois em UI
estilo `fit_fotos` (ver + copiar para o Excel).

- **RELATÓRIO** = pasta de trabalho (ex: `gna_fonte_out2026`, selecionado
  na lista do treino ou passado por `--relatorio`).
  O script cria `Arquivos/Classificadas/<relatorio>/` com as fotos
  (`fotos/` — cópia permanente, pode apagar os originais), `classificacao.csv`
  e `viewer.json` — SEM classificar. O usuário classifica no modo treino.
- **CLASSE** é o que importa (ex: `fonte_trocada`). Multi-rótulo: mesma foto
  em N classes. No treino, classes por **marcação em lista** (digite só ao
  criar em "Nova classe"). Cada foto validada é salva em
  `Arquivos/Classificadas/_dataset/<classe>/` (`<relatorio>__<arquivo>`) e
  ao distribuir também — base permanente p/ treinar classificador futuro.

```
Arquivos/                            # dados compartilhados na RAIZ
  Fotos_Ordenadas/                   # ENTRADA padrão (saída do ordenar_fotos)
  Classificadas/                     # um relatório = uma pasta (gitignored)
    _catalogo.json                   # classes (lista global p/ seleção)
    _treino.csv                      # exemplos validados (base p/ classificador futuro)
    _dataset/<classe>/               # imagens validadas, cópia permanente (<relatorio>__<arquivo>)
    <relatorio>/                     # ambiente do relatório (criado por --preparar)
      fotos/                         # cópias aguardando classificação (ordem mantida)
      classificacao.csv              # TABELA (PENDENTE; SUGERIDA após tentativa por conteúdo)
      viewer.json                    # índice p/ UI
      <classe>/                      # após distribuir: uma pasta por classe
        Foto (1).ext ...             # cópias em ordem cronológica
      _NÃO_CLASSIFICADAS/            # fallback: foto sem classe válida

features/classificar_fotos/
  classificar_fotos.py               # --preparar (ambiente) + distribuir por classe (linha de comando: roda e sai)
  modo_treino.py                     # janela treino: sugere, você confirma/corrige (humano valida)
  ver_relatorio.py                   # janela: navega no relatório por classe (fica aberta; copia via fit_fotos)
  AGENTS.md                          # este arquivo
```

## Fluxo obrigatório com o usuário

Sempre nesta ordem, perguntando antes de agir:

0. **Preparar ambiente (script faz)** — `classificar_fotos.py --preparar`
   cria `Arquivos/Classificadas/<relatorio>/` com as fotos em `fotos/`
   (cópia permanente — pode apagar os originais depois),
   `classificacao.csv` (todas PENDENTE) e `viewer.json` inicial.
   NÃO classifica e NUNCA sugere por nome de arquivo.
1. **Relatório** — pergunte o nome (pasta de trabalho,
   ex: `gna_fonte_out2026`). Um relatório por vez.
   Para outro relatório, repita do passo 0.
2. **Pasta de entrada** — só se precisar sair do padrão. Padrão do
   `--preparar`: `Arquivos/Fotos_Ordenadas`. Pode ser outra pasta indicada.
   Se inválida/vazia, liste a pasta do projeto e `Arquivos/` para sugerir.
3. **Verificar ordem** — o `--preparar` avisa se a entrada está fora do
   padrão `Foto (n)`. Se `NAO ORDENADA`, pergunte: "posso ordenar primeiro?".
   Se sim, execute o fluxo de `features/ordenar_fotos/AGENTS.md` e volte aqui.
4. **Classes** — pergunte a lista de classes antes do treino só se ainda
   estiver vazio (ex: `fonte_trocada; protecao`). No treino elas viram
   marcações em lista — só confirme o nome ao criar (evita variação errada).
   **Tentativa por conteúdo (VOCÊ faz, se o usuário pedir)** — abra e leia
   **cada imagem** com sua visão e grave as classes no CSV como `SUGERIDA`
   (sempre pelo CONTEÚDO, nunca pelo nome do arquivo), seguindo a
   **regra de foco** abaixo. A pessoa corrige e classifica o resto no treino.

## Regra de foco (vale p/ agente e p/ treino)

Atribua uma classe à foto **somente se a foto estiver focando naquela coisa**:
objeto nítido e identificável com segurança (assunto principal ou claramente
visível). Se estiver **borrada, desfocada, longe/cortada a ponto de não dar
para identificar**, ou o objeto aparece **só de fundo/de passagem**, NÃO
atribua essa classe. Na dúvida entre marcar ou não, não marque — o humano
decide no treino. Foto sem nenhuma classe segura = `Não identificado`.
5. **Treino (humano valida e completa)** — abra `modo_treino.py --relatorio <nome>`.
   A pessoa corrige as `SUGERIDA` (Enter = acertou) e classifica as `PENDENTE`.
   (ver seção Modo treino).
6. **Distribuir via script e resumir** — rode `classificar_fotos.py`
   com `--relatorio` (usa `fotos/` do relatório sozinho) e informe: relatório,
   nº de fotos, nº de classes, destino e como ver/copiar (fit_fotos por pasta).
7. **Ver/copiar (opcional)** — para colar no Excel, abra
   `python features/fit_fotos/fit_fotos.py --pasta Arquivos/Classificadas/<relatorio>/<classe>`.

## Modo treino (humano valida, mesmo visual do fit_fotos)

Quando o usuário pedir "modo treino" ou quiser classificar manualmente:
quem valida é a **pessoa na janela** (você só ABRE o programa).

- O **relatório** é selecionado na lista; as **classes** por marcação
  (digite só em "Nova classe"). Cada foto validada é salva em
  `_dataset/<classe>/` — junto com `fotos/` do relatório, pode apagar
  os originais sem perder nada.

1. Pergunte o relatório — o `--preparar` já deixa as fotos em
   `<relatorio>/fotos/`.
2. Abra: `python features/classificar_fotos/modo_treino.py --relatorio <nome>`
   (abre direto nas fotos do relatório; `--pasta` só se precisar trocar).
3. Explique em 3 frases: a janela mostra a foto + sugestão automática;
   Enter = acertou, ou marque as classes e Salvar correção;
   "Não identificado" quando não der p/ classificar. Nova classe pelo campo.
   Detalhes da janela: ao trocar de foto as marcações recomeçam da foto
   atual (salvas > sugestão) — nada da foto anterior é mantido; a lista
   mostra ✓ com a classe salva e o filtro "Mostrar" agrupa por classe
   (Todas / Não classificadas / cada classe, com contadores). Zoom na foto:
   rodinha do mouse, botões −/+ (Ajustar, 1:1) ou arrastar p/ navegar.
4. Ao fechar, rode `classificar_fotos.py --relatorio <nome>` para distribuir
   (também reforça o `_dataset`).
5. Catálogo (`_catalogo.json`: classes globais) e exemplos (`_treino.csv`)
   ficam guardados como base de treino. Nada aqui sugere por nome de
   arquivo (`Foto (n)` repete entre relatórios).

## Formato exato de `classificacao.csv`

- Encoding **`utf-8-sig`**, cabeçalho obrigatório, uma linha por foto:

```
Arquivo,Ordem,Classes,Status,Observacao IA
Foto (1).jpg,1,vazamento; corrosão,OK,mancha escura na base
Foto (2).jpg,2,estrutura,OK,vista geral da torre
Foto (3).jpg,3,,PENDENTE,sem elemento nítido
```

- `Arquivo` = nome exato na pasta de origem (em geral `Foto (n).ext`).
- `Ordem` = número da ordem cronológica (1 = mais antiga).
- `Classes` = 1..N classes separadas por `;` (ou `|`). Sem classe = vazio.
- `Status` = `OK` (validada), `SUGERIDA` (sugestão automática — confirmar no treino),
  `PENDENTE` (aguardando) ou `NÃO_CLASSIFICADA`.
- `Observacao IA` = motivo curto da classificação (p/ auditoria e UI).

## Regras

- **Nunca copiar/renomear manualmente**: ambiente e distribuição física são
  **sempre** via `classificar_fotos.py` desta pasta.
- **Quem classifica é a pessoa no modo treino** (ou VOCÊ com sua visão, só se
  o usuário pedir classificação por agente e gravar o CSV no formato exato).
- **Multi-rótulo**: mesma foto em N classes = N cópias (o script faz).
- **Ordem preservada**: nunca renomeie dentro das classes; o nome
  `Foto (n)` garante ordem natural na UI.
- **Execução**: rode o script a partir da **raiz do projeto**.
- **Git**: `Arquivos/Fotos*/` e `Arquivos/Classificadas/` são gitignored —
  não force commit de fotos. Commits só sob pedido explícito.

## Comandos (você só chama — o script executa)

```bash
# 0 - preparar ambiente do relatório (copia fotos p/ fotos/, CSV + viewer inicial, sem classificar)
python features/classificar_fotos/classificar_fotos.py --preparar --relatorio <nome> --origem Arquivos/Fotos_Ordenadas

# 1 - modo treino (janela: sugere, humano confirma/corrige — a pessoa opera; salva em _dataset/)
python features/classificar_fotos/modo_treino.py --relatorio <nome>

# 2 - distribuir por classe após o treino (usa fotos/ do relatório sozinho;
#     --origem só se precisar outra pasta)
python features/classificar_fotos/classificar_fotos.py --relatorio <nome>

# 3 - ver o relatório classificado (janela: fica aberta; copia no tamanho
#     do Excel igual ao fit_fotos: tamanho LxA, Copiar, Enviar, Salvar)
python features/classificar_fotos/ver_relatorio.py --relatorio <nome>

# 4 - ver uma classe no tamanho do Excel (janela fit_fotos)
python features/fit_fotos/fit_fotos.py --pasta Arquivos/Classificadas/<relatorio>/<classe>
```

**Nota:** `classificar_fotos.py` é linha de comando (roda e sai — normal).
Para *ver* as fotos, use as janelas (`modo_treino.py` p/ validar,
`ver_relatorio.py` p/ navegar, `fit_fotos.py` p/ copiar).

- `--csv` e `--base` só se precisar sair do padrão.
- Exemplo completo:
  `python features/classificar_fotos/classificar_fotos.py --preparar --relatorio gna_fonte --origem Arquivos/Fotos_Ordenadas`
