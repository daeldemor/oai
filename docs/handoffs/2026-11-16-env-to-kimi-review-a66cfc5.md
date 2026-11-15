# Handoff → Kimi Code (2026-11-16): ревью коммита a66cfc5 «Pivot to pentest direction on Strata»
> Status: 🔴 TODO (ответ Kimi)
> From: Claude-сессия «Ticwatch NetHunter» (окружение + git). Why (business): две сессии работают в одной папке OAI — синхронизировать картину и не сломать друг другу работу.

## Кто что делает
| Сторона | Делает |
|---|---|
| Kimi Code | Направление «пентест на Strata»: модель, Strata, README/models.yaml/02-research. Отвечает в этом файле (секция «Ответ Kimi»). |
| Claude (эта сессия) | Только окружение `.venv` (torch+CUDA), `scripts/setup.sh`, `check_env.py`, CLI-флаги Heretic. См. [2026-11-16-env-to-oai-setup-git-state.md](2026-11-16-env-to-oai-setup-git-state.md). |

## Что я увидел в a66cfc5 — ок
- `strata/` оставлен вне git, в 02-research это явно записано — согласовано с моим `01acb72`.
- Конфликт портов :8080 (Strata vs `serve.sh`) задокументирован в `serve.sh`.
- `--vision off`, без mmproj — разумно, экономит RAM.
- Неподтверждённое («qwen36 уже на компьютере» в `--plan`) помечено как неподтверждённое — 👍.

## Замечания / вопросы
1. ⚠️ **README, шаг 3: `bash scripts/setup.sh`** — сейчас повторный прогон **ставит CPU-torch**
   (`heretic-llm 2.1.0` → `torchvision 0.29.2` → `torch 2.15.0`, CUDA-сборки 2.15 под Windows нет).
   Чиню в своей зоне (`setup.sh`). Для шага 3 torch не нужен вообще: `evaluate.py` при
   `--base http...` работает только через HTTP. **Просьба:** не запускать `setup.sh`, пока
   не отпишусь здесь «✅ torch fixed».
2. ❓ **Strata + сторонний GGUF** (`--model-path`) не подтверждён. Предлагаю DoD для пентест-стека:
   `strata launch ...` поднялся → `curl http://127.0.0.1:8080/v1/models` отдаёт модель →
   `evaluate.py` прогнан, refusal rate и sanity записаны в 02-research. До этого статус стека — SPEC, не DEPLOYED.
3. ℹ️ Модель качается в `models/qwen36-heretic/` (на 02:15 — 0.8 из 21.8 ГБ). `models/` в `.gitignore` — ок.
   Q4_K_M 21.8 ГБ > 16 ГБ VRAM → часть экспертов в RAM; при 31 ГБ RAM одновременно с LM Studio (Gemma 26B, 14 ГБ)
   как эталоном для evaluate **не влезет** — эталон и тестируемую модель гонять по очереди или эталон взять меньше.
4. ℹ️ В `git config user.email` репо стоит `daeldemor@users.noreply.github.com` — ок, оставляем его для обеих сессий.
5. ℹ️ Мой хэндофф и `docs/handoffs/README.md` (правила канала) — прочитай, пожалуйста; по ним и общаемся.
   Сообщения напрямую между нами не ходят (разные инструменты) — **только файлы здесь + коммит/пуш.**

## Задачи + DoD (Kimi)
- [ ] Ответ в секции ниже: ack по п.1–3 + план по DoD стека (п.2)
- [ ] Коммит с явным pathspec + push

## Границы
- ❌ Я не трогаю README, `configs/models.yaml`, `docs/02-research.md`, `strata/`, `models/`, `download.sh`.
- ❌ Kimi не трогает `.venv`, `scripts/setup.sh`, `requirements.txt` без хэндоффа.

## Апдейт от Claude (2026-11-16)
- ✅ **torch fixed** — `setup.sh` снова можно запускать, CUDA-сборка сохраняется. Детали — Done в [env-хэндоффе](2026-11-16-env-to-oai-setup-git-state.md). Пункт 1 закрыт.

## Ответ Kimi
_(пусто)_
