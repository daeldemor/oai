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

## Быстрый старт (пентест-направление, движок Strata)

Основной стек: **heretic Qwen3.6-35B-A3B (MoE) на движке Strata** —
OpenAI/Anthropic-совместимый API на `http://127.0.0.1:8080`.

```bash
cd /g/Work/OAI

# 1. Модель уже скачивается/скачана в models/qwen36-heretic/ (Q4_K_M, 21.8 ГБ)

# 2. Запуск через Strata (в новом терминале команда доступна как `strata`):
strata launch --model-path "G:\Work\OAI\models\qwen36-heretic" \
  --vision off --yes --no-tui

# 2б. План Б — через llama.cpp (если Strata не примет сторонний GGUF):
bash scripts/serve.sh "models/qwen36-heretic/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-Q4_K_M.gguf"

# 3. Проверка отказов и качества:
bash scripts/setup.sh && source .venv/Scripts/activate
python scripts/evaluate.py --base http://localhost:1234/v1 --ablated http://localhost:8080/v1
# (base — Gemma 26B heretic в LM Studio как эталон)
```

Запасные варианты под пентест (через `scripts/download.sh`):
`pentest_priority` в `configs/models.yaml` — кодерская DavidAU Qwen3.8-27B
и reasoning DeepSeek-V4-Pro-9B.

### GUI-вариант (без пентест-специфики)

```bash
bash scripts/download.sh mradermacher/gemma-4-12B-it-uncensored-heretic-GGUF Q5_K_M
# дальше модель видна в LM Studio и Bionic
```

## Продвинутый путь (опционально): своя аблитерация

Если когда-нибудь захочется сделать собственную версию, а не готовую:

```bash
source .venv/Scripts/activate
python scripts/abliterate.py --model Qwen/Qwen3-8B --output models/qwen3-8b-abliterated
bash scripts/quantize.sh models/qwen3-8b-abliterated q5_k_m
```

Обоснование выбора движков и моделей — в `docs/02-research.md`.
