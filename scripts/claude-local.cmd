@echo off
rem Claude Code на локальной heretic Qwen3.6 через Strata (http://127.0.0.1:8080).
rem Переменные действуют только в этом окне: обычный Claude Code (облако) не затрагивается.
rem Сначала поднимите сервер:  strata launch --preset heretic-q36-128k  (или heretic-q36-32k)
rem Запуск:  scripts\claude-local.cmd            (интерактивно, в текущей папке)
rem          scripts\claude-local.cmd -p "задача" (один запрос)
rem Контекст скрипт узнаёт у сервера (/v1/models -> meta.n_ctx). При 64K и больше включается
rem полный набор инструментов Claude Code (20 шт., промпт ~15.6K), при 32K - упрощённый (3 шт.).
rem Переопределить: set CTX=... и/или set FULL_TOOLS=0/1 перед запуском.
setlocal
set MODEL=qwen3.6-35b-a3b-ud-q4_k_xl
set ANTHROPIC_BASE_URL=http://127.0.0.1:8080
set ANTHROPIC_AUTH_TOKEN=strata-local
set ANTHROPIC_API_KEY=
set ANTHROPIC_MODEL=%MODEL%
set ANTHROPIC_SMALL_FAST_MODEL=%MODEL%
set ANTHROPIC_DEFAULT_SONNET_MODEL=%MODEL%
set ANTHROPIC_DEFAULT_OPUS_MODEL=%MODEL%
set ANTHROPIC_DEFAULT_HAIKU_MODEL=%MODEL%
set CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
set DISABLE_AUTOUPDATER=1
set DISABLE_TELEMETRY=1
set CLAUDE_CODE_EFFORT_LEVEL=medium
curl -s -m 3 http://127.0.0.1:8080/v1/models >nul 2>&1 || (echo Strata is not answering on :8080. Start it: strata launch --preset heretic-q36-128k & exit /b 1)
if "%CTX%"=="" for /f %%c in ('powershell -NoProfile -Command "(Invoke-RestMethod http://127.0.0.1:8080/v1/models).data[0].meta.n_ctx"') do set CTX=%%c
if "%CTX%"=="" set CTX=32768
if "%FULL_TOOLS%"=="" (if %CTX% GEQ 65536 (set FULL_TOOLS=1) else (set FULL_TOOLS=0))
set CLAUDE_CODE_MAX_CONTEXT_TOKENS=%CTX%
set CLAUDE_CODE_MAX_OUTPUT_TOKENS=4096
if not "%FULL_TOOLS%"=="1" set CLAUDE_CODE_SIMPLE=1
echo Strata context %CTX%, full tools %FULL_TOOLS%
claude %*
