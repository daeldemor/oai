@echo off
rem Inkling-2-Mini Uncensored on the patched llama.cpp: start the server and open the web chat.
rem   inkling.cmd        320K context, faster prompt reading (default)
rem   inkling.cmd fast   320K context, faster generation, slower prompt reading
rem   inkling.cmd 128k   128K context, everything faster
rem Stop: close the "Inkling server" window.
rem Agent mode (web chat gets file and shell tools): set AGENT_DIR=<folder> before the call;
rem the server then runs in that folder with --agent. scripts\inkling-agent.ps1 does this.
rem ASCII only: cmd reads this file in the OEM code page.
setlocal
set "ROOT=%~dp0.."
set "EXE=%ROOT%\llama.cpp-src\build\bin\llama-server.exe"
set "MODEL=C:\Users\rmari\.lmstudio\models\AtomicChat\Inkling-2-Mini-Uncensored-GGUF\Inkling-2-Mini-Uncensored-AD-IQ3_S.gguf"
set "PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.5\bin\x64;%PATH%"
set "PORT=8080"
rem API key: without it any web page open in the browser could POST to /tools and run commands
rem (the "Allow once" prompt lives only in the chat UI). The .ps1 launchers create the key file.
rem The built-in chat itself goes without the key: the patched server trusts browser requests marked
rem Sec-Fetch-Site: same-origin with a loopback Host (see patches/, LLAMA_UI_TRUST_SAME_ORIGIN).
set "LLAMA_UI_TRUST_SAME_ORIGIN=1"
set "KEYFILE=%LOCALAPPDATA%\inkling\api-key.txt"
set "KEYARGS="
if exist "%KEYFILE%" set "KEYARGS=--api-key-file "%KEYFILE%""
if defined AGENT_DIR if not defined KEYARGS (
  echo Agent mode needs an API key: start it from the "Inkling Agent" shortcut.
  pause
  exit /b 1
)

rem experts of the outer layers go to RAM; no "|" in the regexes, cmd would treat it as a pipe
set "ARGS=-c 327680 -ctk q4_0 -ctv q4_0 -ub 192 -ot blk\.[0-3]\.ffn_.*_exps\.=CPU -ot blk\.2[0-3]\.ffn_.*_exps\.=CPU"
if /i "%~1"=="fast" set "ARGS=-c 327680 -ctk q4_0 -ctv q4_0 -ub 128 -ot blk\.[0-2]\.ffn_.*_exps\.=CPU -ot blk\.2[1-3]\.ffn_.*_exps\.=CPU"
if /i "%~1"=="128k" set "ARGS=-c 131072 -ctk q8_0 -ctv q8_0 -ub 384 -ot blk\.[01]\.ffn_.*_exps\.=CPU -ot blk\.2[23]\.ffn_.*_exps\.=CPU"

curl -s -m 2 http://127.0.0.1:%PORT%/health >nul 2>&1
if not errorlevel 1 (
  echo Port %PORT% is busy: Strata or another server is running. Stop it first.
  pause
  exit /b 1
)

set "WD=%ROOT%"
set "AGENTARGS="
if defined AGENT_DIR set "WD=%AGENT_DIR%"
if defined AGENT_DIR set "AGENTARGS=--agent"

start "Inkling server" /min /D "%WD%" "%EXE%" -m "%MODEL%" --host 127.0.0.1 --port %PORT% --parallel 1 -ngl 999 --flash-attn on --jinja --load-mode none -b 2048 --alias inkling --ui-config-file "%ROOT%\configs\inkling-ui.json" %AGENTARGS% %KEYARGS% %ARGS%

echo Loading Inkling, about 30 s...
for /l %%i in (1,1,90) do (
  curl -s -m 2 http://127.0.0.1:%PORT%/health 2>nul | findstr /c:"ok" >nul && goto ready
  ping -n 3 127.0.0.1 >nul
)
echo Server did not start. Open the "Inkling server" window to see the error.
pause
exit /b 1

:ready
echo Inkling is ready: http://127.0.0.1:%PORT%/
if defined NOBROWSER exit /b 0
rem LLAMA_UI_BOOTSTRAP_TOKEN (one-shot, set by inkling-agent.ps1): open the chat through /inkling-bootstrap,
rem which sets the chat's tool permissions: UI_BYPASS=1 allows all tools, otherwise the chat asks each time
if defined LLAMA_UI_BOOTSTRAP_TOKEN (
  start "" "http://127.0.0.1:%PORT%/inkling-bootstrap?t=%LLAMA_UI_BOOTSTRAP_TOKEN%&bypass=%UI_BYPASS%"
) else (
  start "" http://127.0.0.1:%PORT%/
)
