# Handoff → Kimi Code (2026-11-16): heretic Qwen3.6 на Strata — причина отказа найдена, нужен слот :8080 + RAM/VRAM
> Status: 🔴 TODO (Kimi: освободить :8080 и память) / 🔄 IN PROGRESS (Claude: запуск на Strata)
> From: Claude-сессия (окружение + git). Why (business): пользователь прямо сказал — «хочу скачать и запустить
> лучшую модель **на страта**, которую хорошо потянет моё железо»; llama.cpp-план Б этому запросу не отвечает,
> пока Strata-путь не исчерпан. А он не исчерпан.

## P0-просьба
`llama-server` (PID 17076, запущен 03:08 через `scripts/serve.sh`, `--n-cpu-moe 22`) держит **:8080, 16 ГБ RAM и
12 ГБ VRAM**. Пока он жив, Strata не поднять (свободно 3–5 ГБ RAM). **Останови его, как закончишь текущий прогон,
и не поднимай заново на :8080**, пока в этом файле не появится «✅ Strata verified» или «⛔ Strata отказ».
Чужой процесс я сам не убиваю.

## Кто что делает
| Сторона | Делает |
|---|---|
| Claude | Запуск heretic-модели на Strata, замер ток/с, `evaluate.py`, правка Strata-фактов в README / `configs/models.yaml` / `docs/02-research.md` §2.2 (пользователь: «продолжай работать в том числе за Кими») |
| Kimi | Освобождает :8080/RAM/VRAM; коммитит **свои** незакоммиченные правки (`scripts/serve.sh`, ответ в review-хэндоффе) сама; план Б держит как запасной, не как основной |

## Что найдено (факты, проверено мной)
1. **Почему `--model-path` отказал.** `strata_control/models.py: plan_import` принимает только архитектуру
   `qwen4exp` (Flash-Next). Для Qwen3.6 (`qwen35moe`) свой файл подаётся иначе:
   `--family qwen36 --model ud-q4_k_xl --model-path <папка>`, а файл в папке должен называться
   **`Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`** (`setup.py: OWN_PATH_FAMILIES`). Так setup проходит («qwen36 UD-Q4_K_XL is ready»).
2. **Движка не было вовсе**: `strata doctor` показывал только terminal/monitor. Поставлен `strata update --yes --no-control`
   → engine 0.1.60 `windows-x86_64-cuda-cuda13`.
3. **Вторая причина — формат экспертов.** Движок на загрузке:
   `blk.5.experts are Q4_K/Q4_K, which the native expert kernels do not take`.
   Ядра (`src/kernels/cuda/iq_kernels.cu`, `STRATA_GU_FMTS` / `STRATA_D_FMTS`) берут gate/up в Q4_K/Q5_K/Q6_K/Q8_0,
   а **down — не в Q4_K** (только Q5_1/Q5_0/Q4_1/Q4_0/Q8_0/Q5_K/Q6_K/IQ4_*). Q4_K_M кладёт down в Q6_K на 21 слое
   (их движок принял: blk.0–4) и в Q4_K на 20 слоях (на них падает).
4. **Лечение без скачивания**: `scripts/strata_fix_down.py` перекодирует 20 down-тензоров Q4_K → Q5_1
   (суб-блок Q4_K = блок Q5_1 один в один: тот же 4-битный код, scale/min в float16; остальное байт в байт).
   Результат: `X:\OAI-models\qwen36-heretic-strata\Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`, 22 786 946 208 байт.
5. **`G:` — это HDD** (ST1000DM003), а не SSD. Поэтому Strata-копию я положил на SSD `X:` (870 EVO).
   Модель с `G:` грузится ~2 мин и при нехватке RAM читается с диска на каждом токене.
6. **Моя вина по твоему замеру.** С 02:58 до 03:13 мой перекодировщик читал/писал 22 ГБ на том же `G:` и держал
   ~11 ГБ RAM под mmap. Твои 0.26 ток/с prompt / 0.78 ток/с decode (logs-server.txt) сняты под этой нагрузкой —
   **не записывай их в 02-research как характеристику llama.cpp-пути**, перемерь на чистой машине.

## Контракт (команда запуска Strata)
```
strata launch --family qwen36 --model ud-q4_k_xl --model-path "X:\OAI-models\qwen36-heretic-strata" ^
  --vision off --context 32k --parallel 1 --access local --port 8080 --save-preset heretic-q36-32k --yes --no-tui
```

## Задачи + DoD
- [ ] Kimi: `llama-server` остановлен, :8080 свободен (или ответ здесь, почему нет)
- [ ] Claude: движок Strata загрузил перекодированный файл (или зафиксирован дословный отказ)
- [ ] Claude: `curl http://127.0.0.1:8080/v1/models` + тестовый completion + ток/с
- [ ] Claude: `evaluate.py` (refusal rate + sanity) → `docs/02-research.md`
- [ ] Claude: README / models.yaml / 02-research §2.2 приведены к фактам; этот файл закрыт

## Границы
- ❌ Не запускаю Strata, пока жив твой `llama-server` (память не делится).
- ❌ Не трогаю и не коммичу твои незакоммиченные правки (`scripts/serve.sh`, review-хэндофф), `llama.cpp-bin/`, `logs-server.txt`.
- ❌ Официальный Unsloth UD-Q4_K_XL (сток, с отказами) не качаю, пока heretic-путь не провален.

## Ссылки и грабли
- Review-хэндофф с DoD стека: [2026-11-16-env-to-kimi-review-a66cfc5.md](2026-11-16-env-to-kimi-review-a66cfc5.md)
- `packs/` (создаёт Strata setup в cwd), `llama.cpp-bin/`, `logs-server.txt` — не в `.gitignore`; добавлю `packs/`, остальное — твоё.
- На машине 31 ГБ RAM: Strata в гибридном режиме держит экспертов в RAM (~19 ГБ) — параллельно с LM Studio / llama-server не поднимется.
