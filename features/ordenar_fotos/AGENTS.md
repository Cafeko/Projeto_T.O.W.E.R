# AGENTS.md — Ordenar Fotos

> Instruções para qualquer agente externo executando esta funcionalidade.
> Idioma do usuário: português. Responda em português, de forma curta e direta.
>
> **Modelo de atuação: VOCÊ é o agente.**
> **VOCÊ mesmo abre e lê cada imagem** (sua visão) e grava a tabela;
> o script `organizar_fotos.py` desta pasta só entra no final, para executar a
> cópia/renomeação. **Nunca renomeie/copie foto por conta própria**
> (nada de `os.rename`, `shutil`, `move`, `copy` ou script ad-hoc).

## O que faz

Organiza fotos pela **data/hora do carimbo visível na imagem** (ex: `9 de setembro de 2026 17:58:53`).

```
Arquivos/                        # dados compartilhados na RAIZ do projeto
  Fotos/                         # ENTRADA típica (gitignored - nunca commitar fotos)
  Fotos_Ordenadas/               # SAÍDA da cópia: Foto (1).ext ... Foto (n).ext (gitignored)
  resultado.csv                  # TABELA que VOCÊ preenche: Arquivo,Data,Hora,Data/Hora,Status,Texto IA

features/ordenar_fotos/
  organizar_fotos.py             # script desta funcionalidade (único meio de copiar/renomear)
  AGENTS.md                      # este arquivo
```

## Fluxo obrigatório com o usuário

Sempre nesta ordem, perguntando antes de agir:

1. **Caminho das fotos** — aceite absoluto ou relativo à raiz do projeto. Enter = `Arquivos/fotos`. Se inválido/vazio, liste a pasta do projeto e `Arquivos/` para sugerir.
2. **Extrair datas (VOCÊ faz)** — abra e leia **cada imagem** (o carimbo fica em geral no rodapé), transcreva a data/hora e **grave `Arquivos/resultado.csv`** no formato exato abaixo. Não prossiga se não houver fotos.
3. **Cópia ou renomear?** — `1` = criar cópia ordenada em `Arquivos\Fotos_Ordenadas`; `2` = renomear os originais na própria pasta. Aceite linguagem natural ("cria copia", "renomeia ai").
4. **Ordem** — `1` = mais antiga primeiro (`Foto (1)` = mais antiga); `2` = mais nova primeiro.
5. **Executar via script e resumir** — rode `organizar_fotos.py` com os flags correspondentes (ver Comandos) e informe quantidade, destino e ordem usada. O script **limpa o CSV sozinho** ao concluir (só cabeçalho) — você não precisa mexer na tabela depois.

## Como ler as datas das imagens

- Formatos possíveis: `DD/MM/AAAA HH:MM:SS`, `AAAA-MM-DD HH:MM`, `9 de setembro de 2026 17:58:53`, `September 9, 2026 15:15:55`, com ou sem milissegundos. Vale qualquer ano, mes e dia.
- Ignore coordenadas GPS, endereços e outros textos — só a data/hora interessa.
- **Cor do texto varia** (branco, amarelo ou outra): nunca descarte por cor. Em fundo claro (céu, chapa metálica, etiqueta) o contraste cai — amplie e confira com atenção.
- Se a foto **não tiver data legível**: deixe Data/Hora vazios, Status = `DATA NÃO ENCONTRADA`. Ela vai por último na ordenação — **nunca descarte fotos**.

## Segunda tentativa obrigatória (só agentes externos)

- Se não achar a data de primeira (recorte do rodapé ou primeira leitura), **reabra a imagem inteira** e procure de novo: o carimbo pode estar mais alto ou em outra cor/posição (ex: overlay de drone em amarelo no meio da foto).
- Vale recorte maior, ampliação ou segunda passada de OCR com outra região — o que importa é cobrir a **foto toda**.
- Só marque `DATA NÃO ENCONTRADA` depois dessa segunda tentativa na imagem inteira.

## Formato exato de `Arquivos/resultado.csv`

- Encoding **`utf-8-sig`**, cabeçalho obrigatório, uma linha por foto:

```
Arquivo,Data,Hora,Data/Hora,Status,Texto IA
image.jpeg,09/09/2026,15:15:52.775,09/09/2026 15:15:52.775,OK,09/09/2026 15:15:52.775
semdata.jpeg,,,,DATA NÃO ENCONTRADA,texto lido na imagem
```

- `Arquivo` = nome do arquivo **exato** (como está na pasta de origem).
- `Data` = `DD/MM/AAAA`; `Hora` = `HH:MM:SS.mmm`; `Data/Hora` = os dois juntos.
- `Status` = `OK` (achou data) ou `DATA NÃO ENCONTRADA`.
- `Texto IA` = a data normalizada (se OK) ou o texto lido (se sem data).

## Regras

- **Nunca renomear/copiar fotos manualmente** (nada de `os.rename`, `shutil` ou scripts ad-hoc): a ordenação física é **sempre** via `organizar_fotos.py` desta pasta.
- **A extração das datas é SUA tarefa** (ler imagens + gravar CSV).
- **Execução**: rode o script a partir da **raiz do projeto**; caminhos relativos se resolvem contra a raiz.
- **Git**: `Arquivos/Fotos/` e `Arquivos/Fotos_Ordenadas/` são gitignored — não force commit de fotos. Commits só sob pedido explícito.

## Comandos (etapa 5 — o script executa, você só chama)

```bash
# COPIA ordenada p/ Arquivos/Fotos_Ordenadas (originais intactos)
python features/ordenar_fotos/organizar_fotos.py 1 --origem <PASTA_DAS_FOTOS> --modo copia
python features/ordenar_fotos/organizar_fotos.py 2 --origem <PASTA_DAS_FOTOS> --modo copia

# RENOMEAR os originais na propria pasta
python features/ordenar_fotos/organizar_fotos.py 1 --origem <PASTA_DAS_FOTOS> --modo renomear
python features/ordenar_fotos/organizar_fotos.py 2 --origem <PASTA_DAS_FOTOS> --modo renomear
```

- `1` = mais antiga primeiro, `2` = mais nova primeiro. `--csv` e `--destino` só se precisar sair do padrão.
- Exemplo completo: `python features/ordenar_fotos/organizar_fotos.py 1 --origem Arquivos/Fotos --modo copia`
