# OAI — Open Abliterated Inference

Проект для запуска готовых abliterated/heretic-моделей на локальном железе
(RTX 5070 Ti 16 ГБ / Ryzen 7 9800X3D / 32 ГБ DDR5).

Основной путь: **скачать готовую abliterated GGUF с Hugging Face →
запустить через llama.cpp / LM Studio / Bionic → проверить качество**.
Собственная аблитерация — опционально (см. «Продвинутый путь» ниже).

## Что здесь есть

| Путь | Назначение |
|---|---|
| `docs/01-hardware-audit.md` | Аудит железа и уже установленного ПО/моделей |
| `docs/02-research.md` | Исследование подходов и технологий + рекомендации |
| `configs/models.yaml` | Каталог готовых abliterated GGUF под 16 ГБ VRAM |
| `configs/probes_*.json` | Промпты для оценки (отказы + способности) |
| `scripts/check_env.py` | Проверка окружения (GPU, CUDA, RAM, диск) |
| `scripts/download.sh` | Скачивание GGUF с Hugging Face (в каталог LM Studio или локально) |
| `scripts/serve.sh` | Локальный OpenAI-совместимый сервер (llama.cpp из комплекта LM Studio) |
| `scripts/evaluate.py` | Оценка: уровень отказов + сохранность способностей |
| `scripts/setup.sh` | venv + зависимости (нужен для evaluate.py) |
| `scripts/abliterate.py`, `scripts/quantize.sh` | Опционально: своя аблитерация через Heretic |

## Быстрый старт

```bash
cd /g/Work/OAI

# 1. Скачать готовую модель (кладётся в каталог LM Studio —
#    сразу видна в LM Studio и Bionic):
bash scripts/download.sh mradermacher/gemma-4-12B-it-uncensored-heretic-GGUF Q5_K_M

# 2а. GUI-путь: открыть LM Studio или Bionic и выбрать модель — готово.
# 2б. API-путь: поднять OpenAI-совместимый сервер на :8080
bash scripts/serve.sh "C:\Users\rmari\.lmstudio\models\mradermacher\gemma-4-12B-it-uncensored-heretic-GGUF\<файл>.gguf"

# 3. Проверить отказы и качество (нужен setup.sh один раз):
bash scripts/setup.sh && source .venv/Scripts/activate
python scripts/evaluate.py --base http://localhost:1234/v1 --ablated http://localhost:8080/v1
```

Что качать в первую очередь — см. `configs/models.yaml`
(приоритет 1: `gemma-4-12B-it-uncensored-heretic` — полностью влезает в VRAM).

## Продвинутый путь (опционально): своя аблитерация

Если когда-нибудь захочется сделать собственную версию, а не готовую:

```bash
source .venv/Scripts/activate
python scripts/abliterate.py --model Qwen/Qwen3-8B --output models/qwen3-8b-abliterated
bash scripts/quantize.sh models/qwen3-8b-abliterated q5_k_m
```

Обоснование выбора движков и моделей — в `docs/02-research.md`.
