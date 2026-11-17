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
| `scripts/serve.sh` | План Б: OpenAI-совместимый сервер на llama.cpp (`llama.cpp-bin/`) |
| `scripts/claude-local.cmd` | Claude Code на локальной модели через Strata (ANTHROPIC_BASE_URL) |
| `scripts/strata_fix_down.py` | Перекодирует Q4_K down-эксперты GGUF в Q5_1, чтобы файл принял движок Strata |
| `scripts/evaluate.py` | Оценка: уровень отказов + сохранность способностей |
| `scripts/setup.sh` | venv + зависимости (нужен для evaluate.py) |
| `scripts/abliterate.py`, `scripts/quantize.sh` | Опционально: своя аблитерация через Heretic |

## Быстрый старт (пентест-направление, движок Strata) — проверено 16.11.2026

Основной стек: **heretic Qwen3.6-35B-A3B (MoE) на движке Strata** —
OpenAI/Anthropic-совместимый API на `http://127.0.0.1:8080`, 61–82 ток/с генерации.
Подробности и замеры — `docs/02-research.md` §2.2.

```bash
cd /g/Work/OAI

# 0. Один раз: движок Strata (terminal ставит только CLI)
strata update --yes --no-control

# 1. Один раз: модель (21.8 ГБ) и перекодировка down-экспертов под ядра Strata (на SSD!)
bash scripts/download.sh llmfan46/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-GGUF Q4_K_M
#    (download.sh кладёт в каталог LM Studio на NVMe C:)
python -I scripts/strata_fix_down.py \
  "/c/Users/rmari/.lmstudio/models/llmfan46/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-GGUF/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-Q4_K_M.gguf" \
  "X:/OAI-models/qwen36-heretic-strata/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf" --verify

# 2. Первый запуск (имя файла и --family/--model обязательны — иначе Strata откажет)
strata launch --family qwen36 --model ud-q4_k_xl --model-path "X:\OAI-models\qwen36-heretic-strata" \
  --vision off --context 32k --parallel 1 --access local --port 8080 \
  --save-preset heretic-q36-32k --yes --no-tui
#    дальше: strata launch --preset heretic-q36-32k        стоп: strata launch --stop --preset heretic-q36-32k

# 3. Проверка отказов и sanity (thinking-модель — нужен большой лимит токенов)
source .venv/Scripts/activate
python scripts/evaluate.py --ablated http://127.0.0.1:8080/v1 --max-tokens 3072 --log logs/eval.json
```

Не запускайте одновременно со Strata llama-server/LM Studio: эксперты модели держатся в RAM (~19.6 ГиБ из 31).

План Б — тот же Q4_K_M через llama.cpp (без перекодировки, медленнее, `docs/02-research.md` §2.3):
`CPU_MOE=22 CTX=8192 bash scripts/serve.sh <путь к Q4_K_M.gguf на NVMe>`.

### Как пользоваться (сервер Strata поднят)

| Сценарий | Как |
|---|---|
| Агент в терминале (читает/правит файлы, гоняет команды) | `scripts\claude-local.cmd` — Claude Code на локальной модели; переменные только для этого окна, обычный облачный Claude Code не затронут. Один запрос: `scripts\claude-local.cmd -p "задача"` |
| Чат в браузере | `http://127.0.0.1:8080` — встроенная страница Strata |
| Любая OpenAI-совместимая программа (Open WebUI, Continue, Bionic, скрипты) | base URL `http://127.0.0.1:8080/v1`, ключ любой, модель `qwen3.6-35b-a3b-ud-q4_k_xl` |
| Другие агенты (OpenCode, Codex CLI…) | `strata connect` — список; `strata connect opencode` — готовый конфиг |

Claude Code через Strata: проверено 17.11.2026 (`strata connect claude-code --check` — PASS prompt + tool call).
`claude-local.cmd` сам узнаёт контекст сервера: при 64K и больше включает полный набор инструментов (20 шт.,
системный промпт ~15.6K; на 128K задача с Write + Grep — 56 с), при 32K — упрощённый режим (`CLAUDE_CODE_SIMPLE=1`,
3 инструмента, та же простая задача — 10 с). Переопределить: `set CTX=...` / `set FULL_TOOLS=0|1`.

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
