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

### Шпаргалка команд

Сервер Strata:

```bash
strata launch --preset heretic-q36-128k        # запуск, контекст 128K (текущий режим)
strata launch --preset heretic-q36-32k         # запуск, контекст 32K (быстрее на коротких запросах)
strata launch --stop --preset heretic-q36-128k # остановка (у каждого пресета своя)
strata launch --stop --preset heretic-q36-32k
curl http://127.0.0.1:8080/v1/models           # отвечает ли сервер
strata monitor --url http://127.0.0.1:8080     # мониторинг в реальном времени
strata logs --follow                           # журнал движка
```

Пользоваться:

```bash
# чат в браузере: http://127.0.0.1:8080
# другие программы: http://127.0.0.1:8080/v1, ключ любой, модель qwen3.6-35b-a3b-ud-q4_k_xl
G:\Work\OAI\scripts\claude-local.cmd                 # Claude Code на локальной модели (из папки проекта)
G:\Work\OAI\scripts\claude-local.cmd -p "задача"     # один запрос без диалога
```

Проверка отказов и способностей (~12 мин):

```bash
cd /g/Work/OAI && .venv/Scripts/python.exe scripts/evaluate.py --ablated http://127.0.0.1:8080/v1 --max-tokens 3072 --log logs/eval.json
```

Разовая настройка с нуля (уже сделана, нужна при переустановке):

```bash
strata update --yes --no-control   # движок Strata
cd /g/Work/OAI && .venv/Scripts/python.exe -I scripts/strata_fix_down.py \
  "X:/OAI-models/qwen36-heretic/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-Q4_K_M.gguf" \
  "X:/OAI-models/qwen36-heretic-strata/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf" --verify   # ~2.5 мин
strata launch --family qwen36 --model ud-q4_k_xl --model-path "X:\OAI-models\qwen36-heretic-strata" \
  --vision off --context 128k --parallel 1 --access local --port 8080 \
  --save-preset heretic-q36-128k --yes --no-tui
```

Запасной вариант без Strata (llama.cpp, медленнее; Strata перед этим остановить). Модели лежат на SSD `X:\OAI-models` (перенесены с HDD `G:` 2026-11-22):

```bash
cd /g/Work/OAI && CPU_MOE=22 CTX=8192 bash scripts/serve.sh \
  "X:/OAI-models/qwen36-heretic/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-Q4_K_M.gguf"
```

Пока работает Strata, llama-server и LM Studio одновременно не запускать: модель держит в RAM ~20 ГБ.

### GUI-вариант (без пентест-специфики)

```bash
bash scripts/download.sh mradermacher/gemma-4-12B-it-uncensored-heretic-GGUF Q5_K_M
# дальше модель видна в LM Studio и Bionic
```

### Inkling-2-Mini Uncensored, до 326K контекста (Strata + наш патч движка)

Два ярлыка на рабочем столе. Оба поднимают один и тот же сервер Strata на `http://127.0.0.1:8080`
(свой движок `strata-ink-build\strata-inkling.exe`, общий код запуска в `scripts/inkling-strata.ps1`):

- **«Inkling Agent»**: окно с рабочей папкой, контекстом и галочкой bypass, кнопка «Запустить». Через минуту
  в браузере открывается веб-чат Strata на русском. Инструменты ему даёт наш MCP-сервер `scripts/inkling_mcp.py`:
  чтение файлов, поиск по имени и тексту, запись, правка, команды PowerShell, сведения о системе. Доступ ко
  всему компьютеру; рабочая папка только задаёт, от чего считаются относительные пути и где запускаются
  команды. Без галочки перед каждой записью и командой всплывает окно Windows «Inkling: … Разрешить?»
  (по умолчанию выбрано «Нет»), чтение и поиск идут без вопросов. Папку и галочку можно менять, не
  перезагружая модель: они лежат в `%LOCALAPPDATA%\inkling\agent-state.json`, и MCP-сервер читает их при каждом
  вызове. Кнопка «Остановить сервер» выгружает модель.
- **«Inkling CLI»**: консоль, стрелками выбираются контекст и разрешения («Спрашивать» или «Без
  ограничений», то есть `--dangerously-skip-permissions`), путь к папке вводится с клавиатуры (Enter — последняя папка).
  Дальше Claude Code работает на Inkling через Anthropic API Strata. При выходе можно остановить сервер.
  Без меню: `scripts\inkling-claude.ps1 -Mode 320k|128k -Folder <папка> [-Bypass] [-Prompt "задача"] [-KeepServer]`.

| Режим (`--bench`, 2026-11-25) | Контекст | Чтение промпта | Генерация |
|---|---:|---:|---:|
| 320K (эксперты 6.0 ГиБ в VRAM) | 326K | 2053 ток/с на 8K, 877 в среднем до 320K | 38 на 8K, на 320K 25 |
| 128K (эксперты 8.0 ГиБ в VRAM) | 128K | 2491 на 8K | 47 |

API-ключа у сервера нет. Strata без ключа сама отклоняет запросы с чужих веб-страниц (проверка Origin) и
DNS rebinding (проверка Host), а MCP-инструменты выполняет только для своей страницы. Пока сервер работает,
доступно ~11 ГБ RAM (сброс отображения GGUF после загрузки, `STRATA_INK_TRIM_WS`). Во время загрузки
(~40 с) свободной памяти временно меньше 1 ГБ. Журналы: `logs/strata-ink-serve.log`, `logs/strata-ink-server.*`.

Запасной вариант на патченой llama.cpp остался: `scripts/inkling-agent-llama.ps1` и `scripts/inkling-claude-llama.ps1`
(они зовут `scripts/inkling.cmd`, сервер с ключом `%LOCALAPPDATA%\inkling\api-key.txt`). Оба варианта слушают порт 8080:
новые лаунчеры сами останавливают llama-server Inkling, старые требуют остановить Strata.

Claude Code на Inkling: первый ответ в сессии дольше (модель читает его системный промпт ~16K токенов).
Проверка: задача «создай primes.py и запусти» решена за 46 с (на llama.cpp похожая шла 1 мин 53 с).
Подробности и замеры: `docs/02-research.md` §2.4.3–2.4.4.

## Продвинутый путь (опционально): своя аблитерация

Если когда-нибудь захочется сделать собственную версию, а не готовую:

```bash
source .venv/Scripts/activate
python scripts/abliterate.py --model Qwen/Qwen3-8B --output X:/OAI-models/qwen3-8b-abliterated
bash scripts/quantize.sh X:/OAI-models/qwen3-8b-abliterated q5_k_m
```

Обоснование выбора движков и моделей — в `docs/02-research.md`.
