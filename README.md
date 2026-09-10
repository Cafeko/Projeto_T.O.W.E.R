# Telecom - Ordenador de Fotos por Data

Projeto para gerar relatórios de atividades de Telecom organizando fotos pela data/hora do carimbo visível na imagem (ex: `quarta-feira, 9 de setembro de 2026 17:58:53`).

Pipeline atual: **IA local (Qwen2.5-VL) → CSV ordenado → cópia renomeada**.

## Estrutura

```
Telecom_/
├── extrair_datas_ia.py      # 1 - extrai datas com IA e gera resultado.csv
├── organizar_fotos.py       # 2 - copia para Fotos_Ordenadas renomeado
├── requirements.txt
├── Arquivos/
│   ├── Fotos/               # entrada - coloque as fotos aqui
│   ├── Fotos_Ordenadas/     # saída - Foto (1).jpeg ... Foto (n).jpeg
│   └── resultado.csv        # Data,Hora,Data/Hora,Status,Texto IA
```

## Requisitos

- Python 3.10+
- Ollama + modelo `qwen2.5vl:3b` (3.2GB)

```bash
# 1. Ollama - https://ollama.com/download
ollama pull qwen2.5vl:3b
ollama serve  # deixar rodando

# 2. Dependências Python
pip install -r requirements.txt
# requirements: pillow, requests
```

Modelos ficam em `C:\Users\<user>\.ollama\models` (global, não no projeto). Troca em `extrair_datas_ia.py:16` → `MODELO_IA`.

## Uso

### 1. Extrair datas

```bash
python extrair_datas_ia.py
```

- Lê `Arquivos/Fotos` (jpg/jpeg/png/webp/bmp/tif)
- Envia cada foto (reduzida para 896px) para `http://localhost:11434/api/generate`
- Prompt transcreve o carimbo, `parse_data()` converte para `datetime`, limpa GPS `7,6579S 40,1581W` e normaliza `Texto IA` para formato único `DD/MM/AAAA HH:MM:SS.mmm`
- Mostra progresso `1/10 - Processando: ... -> 1/10 - ... 09/09/2026 17:58:59.801 OK`
- Salva `Arquivos/resultado.csv` ordenado (antiga → recente)
- Descarrega modelo da RAM ao final (`keep_alive: 0`)

Exemplo `resultado.csv`:

```
Arquivo,Data,Hora,Data/Hora,Status,Texto IA
image.jpeg,09/09/2026,15:15:52.775,09/09/2026 15:15:52.775,OK,09/09/2026 15:15:52.775
```

### 2. Organizar fotos

```bash
python organizar_fotos.py          # interativo
python organizar_fotos.py 1        # mais antiga primeiro -> Foto (1) = mais antiga
python organizar_fotos.py 2        # mais recente primeiro -> Foto (1) = mais recente
python organizar_fotos.py --antiga
python organizar_fotos.py --recente
```

- Lê `resultado.csv`, ordena por data
- Limpa `Fotos_Ordenadas` e copia com `shutil.copy2` como `Foto (1).jpeg` … `Foto (n).jpeg` (mantém extensão)
- Fotos sem data vão por último

## Fluxo completo

```bash
python extrair_datas_ia.py
python organizar_fotos.py 1
```

## Notas

- O script já descarrega o modelo automaticamente ao final (`descarregar_modelo()` com `keep_alive: 0` — `ollama ps` fica `{"models":[]}`). Se interromper com Ctrl+C, liberar manual: `ollama stop qwen2.5vl:3b`
- Para trocar modelo: `ollama pull llava:7b` e alterar `MODELO_IA` em `extrair_datas_ia.py:16`
- Código próprio é MIT/domínio público. Bibliotecas (Pillow/MIT, requests/Apache 2.0, Ollama/MIT, Qwen/Apache 2.0) são livres para uso comercial com aviso de licença.
