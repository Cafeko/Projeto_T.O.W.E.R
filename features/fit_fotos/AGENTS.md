# AGENTS.md — fit_fotos

> Instruções para qualquer agente externo executando esta funcionalidade.
> Idioma do usuário: português. Responda em português, de forma curta e direta.
>
> **Modelo de atuação: VOCÊ só abre o programa para o usuário.**
> Quem escolhe tamanho, copia e salva é a **pessoa na janela gráfica**.
> Você **não redimensiona, não copia e não edita fotos**
> (nada de PIL, `shutil`, `os.rename`, clipboard ou script ad-hoc).

## O que faz

Janela gráfica para olhar as fotos de uma pasta e deixá-las no tamanho certo
para colar no relatório do Excel. A pessoa escolhe o tamanho em **px ou cm**
(como no Excel), marca se quer **manter a proporção** (sem distorcer) ou o
tamanho exato, e então **copia para a área de transferência** (colar com
Ctrl+V no Excel) ou **salva as redimensionadas** numa pasta.

```
features/fit_fotos/
  fit_fotos.py               # programa (janela gráfica + --pasta)
  AGENTS.md                  # este arquivo
```

## Fluxo obrigatório com o usuário

1. **Caminho das fotos** — pergunte a pasta (absoluto ou relativo à raiz).
   Se inválido/vazio, sugira olhando a pasta do projeto e `Arquivos/`.
2. **Abra o programa já na pasta** — rode o comando abaixo com a pasta
   informada e avise que a janela abriu.
3. **Explique em 2 frases**: na janela a pessoa navega com ← →, escolhe o
   tamanho (px ou cm), marca manter-proporção ou não, e copia (Ctrl+C), salva
   todas ou envia direto p/ o Excel aberto (Ctrl+E — nítido, já no tamanho).
4. **Encerre** — não há CSV nem etapa posterior; seu trabalho acaba ao abrir.

## Comando (você só chama — a pessoa opera a janela)

```bash
python features/fit_fotos/fit_fotos.py --pasta <PASTA_DAS_FOTOS>
```

- Exemplo: `python features/fit_fotos/fit_fotos.py --pasta Arquivos/Fotos`
- Sem `--pasta`, o programa abre na pasta padrão (`Arquivos/Fotos`).
- Rode a partir da **raiz do projeto**.
- Caminho com espaços: use aspas (`--pasta "C:\minha pasta\Fotos"`). Para abrir
  sem console e sem travar o terminal (Windows): `Start-Process pythonw`
  com o caminho entre aspas embutidas.

## Regras

- **Nunca manipule imagens por conta própria**: sem redimensionar, copiar,
  salvar ou converter fora do programa.
- **Git**: pastas de fotos e de saída são gitignored — não force commit de fotos. Commits só sob pedido explícito.
