# Changelog

## 2026-11-23

- Патч `serve/inkling_dialect.py` Strata control 0.1.66 (`patches/strata-control-0.1.66-inkling.patch`).
  Шаги с инструментами теперь переиспользуют кэш промпта: раньше `reused` был 0, каждый шаг заново читал
  25–40K токенов. Размышления модели видны в чате: раньше они пропадали, и долгий ответ выглядел зависшим.
  Сырой вывод последнего ответа пишется в `logs\inkling-raw-last.txt`. Разбор в `docs/02-research.md` §2.4.4.

- Ярлыки «Inkling Agent» и «Inkling CLI» переведены на Strata (режимы 320K и 128K): `scripts/inkling-strata.ps1`,
  новые `scripts/inkling-agent.ps1` и `scripts/inkling-claude.ps1`. Старые версии на llama.cpp оставлены
  как `*-llama.ps1`.
- `scripts/inkling_mcp.py`: MCP-сервер инструментов для веб-чата Strata (файлы, поиск, PowerShell). Перед записью
  и командами спрашивает подтверждение окном Windows, если не включён bypass.
- Патч движка Strata: `STRATA_INK_TRIM_WS=1` освобождает ~11 ГБ RAM после загрузки.

- Наш uncensored Inkling-2-Mini (`AD-IQ3_S`) запущен в Strata 0.2.20 на 326K контекста: патч движка
  `patches/strata-v0.2.20-inkling-320k.patch`, конфиги `configs/strata-ink-320k*.json`, замеры в `docs/02-research.md` §2.4.3.
- Разобрана память Strata: движок держит отображение всего GGUF (12.4 ГБ) после загрузки. Сброс рабочего набора
  освобождает ~10.8 ГБ без потери скорости.
- Поправка: у Strata есть веб-чат, инструменты в нём подключаются через MCP-серверы.
- Сводная таблица всех вариантов (Qwen3.6 и Inkling на llama.cpp и Strata) в §2.4.3.
- `scripts/bench_openai.py`: опция `--salt`, чтобы замер не попадал в кэш промпта.
- Разбор maya-inkling-mini и Strata-паков Inkling (§2.4.2).
