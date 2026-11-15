# Handoff → OAI-сессии (2026-11-16): состояние окружения и git
> Status: 🔄 IN PROGRESS
> From: сессия «Ticwatch NetHunter задача» (вела setup OAI + git). Why (business): две сессии работают в одной папке — нужно не перетирать друг друга и знать, что уже сделано.

## Кто что делает
| Сторона | Делает |
|---|---|
| Сессия «Ticwatch NetHunter» | Довести `.venv` до рабочего torch+CUDA, прогнать `check_env.py`, проверить CLI-флаги Heretic в `scripts/abliterate.py`. Дальше в OAI ничего не трогает без хэндоффа. |
| OAI-сессия (oai-38 / oai-49) | Всё остальное по OAI (Strata, download.sh, модели). Перед правкой `scripts/setup.sh`, `requirements.txt`, `.venv` — хэндофф сюда. |

## Что уже сделано
- **Git:** репо `https://github.com/daeldemor/oai`, ветка `main`.
  - `72d80b1` — первичный коммит (docs, configs, scripts, вкл. `scripts/download.sh`).
  - `01acb72` — `strata/` убран из индекса (попал битым gitlink без URL) и добавлен в `.gitignore`.
    Это клон `github.com/Niko1221/Strata` — на диске не тронут. Если нужен в репо — оформить сабмодулем (`git submodule add https://github.com/Niko1221/Strata.git strata`), решение за OAI-сессией.
  - Автор коммитов в локальном конфиге репо: `daeldemor`.
- **`scripts/setup.sh`:** torch ставится первым и с индекса `cu128` (RTX 5070 Ti = Blackwell sm_120, `cu124` его не поддерживает).

## В работе / грабли
- ⚠️ `pip install -r requirements.txt` **заменил CUDA-torch на CPU-сборку `torch 2.15.0+cpu`**:
  `heretic-llm 2.1.0` тянет `torchvision 0.29.2`, тот — `torch 2.15.0`, которой ещё нет на CUDA-индексах под Windows
  (на `cu130` максимум `2.14.1`). Сейчас ставлю `torch 2.14.1+cu130` + совместимый torchvision.
  **Пока это не закрыто — не запускать Heretic/аблитерацию: поедет на CPU.**
- Флаги `--output` / `--n-trials` в `scripts/abliterate.py` не сверены с реальным CLI `heretic-llm 2.1.0`.

## Задачи + DoD (моя часть)
- [ ] `.venv/Scripts/python -c "import torch; print(torch.cuda.is_available())"` → `True`, arch list содержит `sm_120`
- [ ] `setup.sh` исправлен так, чтобы повторный прогон не откатывал torch на CPU
- [ ] `python scripts/check_env.py` — все пункты `[OK]`
- [ ] `heretic --help` сверен с `abliterate.py`, расхождения исправлены
- [ ] done-handoff сюда же (секция «Done») + коммит

## Границы
- ❌ Не скачиваю модели и не запускаю аблитерацию (~16 ГБ загрузки — только с подтверждения пользователя).
- ❌ Не трогаю `strata/`, `scripts/download.sh`, `docs/02-research.md`.
