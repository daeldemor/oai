@echo off
rem Claude Code на локальной heretic Qwen3.6 через Strata (http://127.0.0.1:8080).
rem Переменные действуют только в этом окне: обычный Claude Code (облако) не затрагивается.
rem Сначала поднимите сервер:  strata launch --preset heretic-q36-32k
rem Запуск:  scripts\claude-local.cmd            (интерактивно, в текущей папке)
rem          scripts\claude-local.cmd -p "задача" (один запрос)
rem Полный набор инструментов (20 шт., промпт ~15.6K): set FULL_TOOLS=1 перед запуском —
rem имеет смысл только если сервер поднят с --context 64k (и CTX=65536).
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
if "%CTX%"=="" set CTX=32768
set CLAUDE_CODE_MAX_CONTEXT_TOKENS=%CTX%
set CLAUDE_CODE_MAX_OUTPUT_TOKENS=4096
if not "%FULL_TOOLS%"=="1" set CLAUDE_CODE_SIMPLE=1
curl -s -m 3 http://127.0.0.1:8080/v1/models >nul 2>&1 || (echo Strata is not answering on :8080. Start it: strata launch --preset heretic-q36-32k & exit /b 1)
claude %*
