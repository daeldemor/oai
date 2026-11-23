# Общие функции лаунчеров Inkling на Strata (подключается через точку: . scripts\inkling-strata.ps1).
# Сервер: Strata control (python -m serve.server) + наш патченый движок strata-ink-build\strata-inkling.exe.
# Режимы: 320k (эксперты 5.6 ГиБ в VRAM) и 128k (7.6 ГиБ, всё быстрее). Веб-чат на том же порту, инструменты
# ему даёт scripts\inkling_mcp.py (MCP). API-ключа нет: Strata без ключа сама отклоняет запросы чужих веб-страниц
# (Origin) и DNS rebinding (Host), а инструменты MCP разрешает только со своей страницы.
# Файл в UTF-8 с BOM: без BOM Windows PowerShell 5.1 читает кириллицу как ANSI.

$InkRoot    = Split-Path $PSScriptRoot -Parent
$InkUrl     = 'http://127.0.0.1:8080'
$InkState   = Join-Path $env:LOCALAPPDATA 'inkling'
$InkRunCfg  = Join-Path $InkState 'strata-run.json'
$InkAgent   = Join-Path $InkState 'agent-state.json'
$InkLogDir  = Join-Path $InkRoot 'logs'
$InkEngine  = Join-Path $InkRoot 'strata-ink-build\strata-inkling.exe'
$InkModel   = 'C:\Users\rmari\.lmstudio\models\AtomicChat\Inkling-2-Mini-Uncensored-GGUF\Inkling-2-Mini-Uncensored-AD-IQ3_S.gguf'
$InkTok     = 'C:\Users\rmari\.lmstudio\packs\inkling-2-mini-sq-15\tokenizer'
$InkCuda    = 'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.5\bin\x64'
$InkLlamaExe = Join-Path $InkRoot 'llama.cpp-src\build\bin\llama-server.exe'

$InkModes = @{
    '320k' = @{ Ctx = 327680; Vram = '5.6' }
    '128k' = @{ Ctx = 131072; Vram = '7.6' }
}

function Get-StrataControl {
    # папка активной версии Strata control (там python и serve\server.py)
    $base = Join-Path $env:LOCALAPPDATA 'Strata\components\control'
    $folder = $null
    try { $folder = (Get-Content (Join-Path $base 'active.json') -Raw | ConvertFrom-Json).folder } catch {}
    if (-not $folder) { $folder = (Get-ChildItem $base -Directory | Sort-Object Name | Select-Object -Last 1).Name }
    $dir = Join-Path $base $folder
    if (-not (Test-Path (Join-Path $dir 'python\python.exe'))) { throw "Strata control не найден в $base" }
    $dir
}

function Write-InkRunConfig([string]$Mode) {
    $m = $InkModes[$Mode]
    $ctl = Get-StrataControl
    New-Item -ItemType Directory -Force $InkState, $InkLogDir | Out-Null
    $cfg = [ordered]@{
        exe       = $InkEngine
        args      = @('--native', $InkModel, '--max-context', "$($m.Ctx)", '--kv', 'k8v4', '--kv-offload', 'off',
                      '--vram-experts-gb', $m.Vram)
        # PIN_FRAC: эксперты в закреплённой RAM (prefill вдвое быстрее); KV_PREALLOC: весь KV сразу (иначе рост
        # упирается в VRAM около 180K); TRIM_WS: после загрузки отпустить отображение GGUF (~11 ГБ RAM)
        env       = [ordered]@{ STRATA_INK_PIN_FRAC = '0.6'; STRATA_INK_KV_PREALLOC = '1'; STRATA_INK_TRIM_WS = '1' }
        lib_dirs  = @($InkCuda)
        tokenizer = $InkTok
        model_name = 'inkling'
        arch      = 'inkling2_loop'
        log       = (Join-Path $InkLogDir 'strata-ink-serve.log')
        drafting  = 'off'
        parallel  = 1
        gpu       = 0
        mcp_servers = [ordered]@{
            inkling = [ordered]@{
                command = (Join-Path $ctl 'python\python.exe')
                args    = @('-I', (Join-Path $PSScriptRoot 'inkling_mcp.py'))
            }
        }
        # подтверждение в окне Windows и долгие команды: таймаут вызова 30 мин, до 40 шагов инструментов на ответ
        mcp       = [ordered]@{ timeout_s = 1800; max_rounds = 40; max_result_chars = 30000 }
        # Движок Inkling по умолчанию жадный (temperature 0), карточки сэмплинга для Inkling в Strata нет, веб-чат
        # своих значений не шлёт. Жадная генерация зацикливалась (одинаковые шаги, «&_fields=meta» без конца).
        # Значения по умолчанию llama-server, на которой таких циклов не было; поля запроса их перекрывают.
        sampling  = [ordered]@{ temperature = 0.8; top_p = 0.95; top_k = 40; min_p = 0.05 }
    }
    $json = $cfg | ConvertTo-Json -Depth 6
    [IO.File]::WriteAllText($InkRunCfg, $json, (New-Object Text.UTF8Encoding $false))
}

function Set-InkAgentState([string]$Cwd, [bool]$Bypass) {
    New-Item -ItemType Directory -Force $InkState | Out-Null
    $json = [ordered]@{ cwd = $Cwd; bypass = $Bypass } | ConvertTo-Json
    [IO.File]::WriteAllText($InkAgent, $json, (New-Object Text.UTF8Encoding $false))
}

function Get-InkHealth {
    try { Invoke-RestMethod "$InkUrl/health" -TimeoutSec 2 } catch { $null }
}

function Get-InkServer {
    # наш сервер Strata: python -m serve.server с нашим конфигом
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'serve\.server' -and $_.CommandLine -like "*$InkRunCfg*" }
}

function Get-InkLlama {
    Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" | Where-Object { $_.ExecutablePath -eq $InkLlamaExe }
}

function Stop-InkServer {
    Get-InkServer | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep 2
    Get-CimInstance Win32_Process -Filter "Name='strata-inkling.exe'" |
        Where-Object { $_.ExecutablePath -eq $InkEngine } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

# Поднять сервер в нужном режиме. $OnWait вызывается раз в ~0.2 с, пока идёт загрузка (для окна GUI).
# Возвращает $null при успехе или текст ошибки.
function Start-InkServer([string]$Mode, [scriptblock]$OnWait = $null) {
    $want = $InkModes[$Mode].Ctx
    $h = Get-InkHealth
    $ours = Get-InkServer
    if ($h -and $ours -and [int]$h.max_context -eq $want) { return $null }        # уже работает как надо
    if ($ours) { Stop-InkServer }
    $llama = Get-InkLlama
    if ($llama) {                                                                  # старый сервер Inkling на llama.cpp
        $llama | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
        Start-Sleep 3
    }
    if (Get-InkHealth) { return 'Порт 8080 занят другим сервером (Strata с другой моделью?). Остановите его и запустите снова.' }

    Write-InkRunConfig $Mode
    $ctl = Get-StrataControl
    $out = Join-Path $InkLogDir 'strata-ink-server.out'
    $err = Join-Path $InkLogDir 'strata-ink-server.err'
    # Сырой вывод модели за последний ответ (патч serve/inkling_dialect.py, patches/strata-control-0.1.66-inkling.patch).
    $env:STRATA_INK_RAW_LOG = Join-Path $InkLogDir 'inkling-raw-last.txt'
    Start-Process -FilePath (Join-Path $ctl 'python\python.exe') -WorkingDirectory $ctl -WindowStyle Hidden `
        -ArgumentList @('-m', 'serve.server', '--engine', 'strata', '--config', "`"$InkRunCfg`"",
                        '--host', '127.0.0.1', '--port', '8080', '--no-api-key') `
        -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null
    $t0 = Get-Date
    while (((Get-Date) - $t0).TotalSeconds -lt 240) {
        $h = Get-InkHealth
        if ($h -and $h.loaded) { return $null }
        if (-not (Get-InkServer)) { break }
        $t1 = Get-Date
        while (((Get-Date) - $t1).TotalMilliseconds -lt 2000) {
            if ($OnWait) { & $OnWait } else { Start-Sleep -Milliseconds 200 }
        }
    }
    $tail = (Get-Content $err, $out -Tail 8 -ErrorAction SilentlyContinue) -join "`n"
    return "Сервер не поднялся. Последние строки журнала ($InkLogDir):`n$tail"
}
