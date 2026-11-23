# Claude Code на локальном Inkling-2-Mini (патченая llama.cpp).
# Выбор контекста стрелками, папка проекта вводится с клавиатуры, сервер поднимается сам.
# Запуск: ярлык «Inkling CLI» или
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\inkling-claude.ps1
# Переменные Claude Code задаются только в этом окне, обычный облачный Claude Code не затронут.
# Без меню: -Mode 320k|fast|128k -Folder <папка> [-Bypass] [-Prompt "задача"] (с -Prompt один запрос, claude -p).
# -Bypass: Claude Code без запросов разрешений (--dangerously-skip-permissions).
# Файл сохранён в UTF-8 с BOM: без BOM Windows PowerShell 5.1 читает кириллицу как ANSI.
param(
    [ValidateSet('320k', 'fast', '128k')] [string] $Mode,
    [string] $Folder,
    [string] $Prompt,
    [switch] $Bypass
)

$ErrorActionPreference = 'Stop'
$Root     = Split-Path $PSScriptRoot -Parent
$Exe      = Join-Path $Root 'llama.cpp-src\build\bin\llama-server.exe'
$Launcher = Join-Path $PSScriptRoot 'inkling.cmd'
$Url      = 'http://127.0.0.1:8080'
$State    = Join-Path $env:LOCALAPPDATA 'inkling'
$LastDir  = Join-Path $State 'last-folder.txt'
$Host.UI.RawUI.WindowTitle = 'Inkling CLI'

$Options = @(
    @{ Name = '320K';         Arg = '';     Ctx = 327680; Note = 'максимум контекста, чтение промпта быстрее (673 ток/с), ответ 38 ток/с' },
    @{ Name = '320K, быстрый ответ'; Arg = 'fast'; Ctx = 327680; Note = 'тот же контекст, ответ 41 ток/с, чтение 586 ток/с' },
    @{ Name = '128K';         Arg = '128k'; Ctx = 131072; Note = 'всё быстрее: чтение 918 ток/с, ответ 42 ток/с' }
)

function Select-Option($title, $items) {
    $sel = 0
    Write-Host $title -ForegroundColor Cyan
    Write-Host '  стрелки вверх/вниз, Enter - выбрать, Esc - выход' -ForegroundColor DarkGray
    $top = [Console]::CursorTop
    [Console]::CursorVisible = $false
    try {
        while ($true) {
            [Console]::SetCursorPosition(0, $top)
            for ($i = 0; $i -lt $items.Count; $i++) {
                $line = '  {0,-22} {1}' -f $items[$i].Name, $items[$i].Note
                $line = $line.PadRight([Console]::WindowWidth - 1).Substring(0, [Console]::WindowWidth - 1)
                if ($i -eq $sel) { Write-Host ('>' + $line.Substring(1)) -ForegroundColor Black -BackgroundColor Cyan }
                else { Write-Host $line }
            }
            $k = [Console]::ReadKey($true)
            switch ($k.Key) {
                'UpArrow'   { $sel = ($sel - 1 + $items.Count) % $items.Count }
                'DownArrow' { $sel = ($sel + 1) % $items.Count }
                'Enter'     { return $items[$sel] }
                'Escape'    { return $null }
            }
        }
    } finally { [Console]::CursorVisible = $true }
}

function Read-Folder {
    $default = $null
    if (Test-Path $LastDir) { $default = (Get-Content $LastDir -Raw -ErrorAction SilentlyContinue).Trim() }
    while ($true) {
        $hint = if ($default) { " [Enter - $default]" } else { '' }
        $in = Read-Host "`nПапка проекта$hint"
        $in = $in.Trim().Trim('"')
        if (-not $in -and $default) { $in = $default }
        if (-not $in) { continue }
        $in = [Environment]::ExpandEnvironmentVariables($in)
        if (Test-Path $in -PathType Container) {
            $full = (Resolve-Path $in).Path
            New-Item -ItemType Directory -Force $State | Out-Null
            Set-Content $LastDir $full -Encoding UTF8
            return $full
        }
        Write-Host "  Папки нет: $in" -ForegroundColor Yellow
    }
}

function Get-ApiKey {
    # постоянный случайный ключ сервера; без него любая открытая в браузере страница могла бы
    # отправить POST /tools и выполнить команду (подтверждение «Allow once» есть только в чате)
    $f = Join-Path $State 'api-key.txt'
    if (-not (Test-Path $f)) {
        New-Item -ItemType Directory -Force $State | Out-Null
        $b = New-Object byte[] 24; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
        Set-Content $f (($b | ForEach-Object { $_.ToString('x2') }) -join '') -Encoding ASCII -NoNewline
    }
    (Get-Content $f -Raw).Trim()
}
function Get-ServerCtx {
    try { return [int](Invoke-RestMethod "$Url/props" -TimeoutSec 2 -Headers @{ Authorization = "Bearer $(Get-ApiKey)" }).default_generation_settings.n_ctx } catch { return $null }
}

function Test-Port { try { (Invoke-RestMethod "$Url/health" -TimeoutSec 2).status -eq 'ok' } catch { $false } }

function Get-OurServer {
    Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" | Where-Object { $_.ExecutablePath -eq $Exe }
}

Write-Host "`n  Inkling-2-Mini Uncensored + Claude Code`n" -ForegroundColor White
if ($Mode) {
    $opt = $Options | Where-Object { $_.Arg -eq $(if ($Mode -eq '320k') { '' } else { $Mode }) }
} else {
    $opt = Select-Option 'Длина контекста:' $Options
    if (-not $opt) { exit 0 }
}
Write-Host "  Выбрано: $($opt.Name)" -ForegroundColor Green
$Perms = @(
    @{ Name = 'Спрашивать';     Note = 'Claude Code спрашивает перед правкой файлов и командами'; Bypass = $false },
    @{ Name = 'Без ограничений'; Note = 'bypass: всё выполняется сразу, без вопросов';           Bypass = $true }
)
if ($Mode) {
    $perm = $Perms[[int][bool]$Bypass]
} else {
    Write-Host ''
    $perm = Select-Option 'Разрешения:' $Perms
    if (-not $perm) { exit 0 }
}
Write-Host "  Разрешения: $($perm.Name)" -ForegroundColor $(if ($perm.Bypass) { 'Yellow' } else { 'Green' })
if ($Folder) {
    if (-not (Test-Path $Folder -PathType Container)) { Write-Host "Папки нет: $Folder" -ForegroundColor Red; exit 1 }
    $folder = (Resolve-Path $Folder).Path
} else {
    $folder = Read-Folder
}

# сервер: переиспользовать, перезапустить с другим контекстом или поднять
$ctx = Get-ServerCtx
$ours = Get-OurServer
if ((Test-Port) -and -not $ours) {
    Write-Host "`nПорт 8080 занят другим сервером (Strata?). Остановите его и запустите снова." -ForegroundColor Red
    Read-Host 'Enter - выход' | Out-Null; exit 1
}
if ($ours -and $ctx -ne $opt.Ctx) {
    Write-Host "`nСервер Inkling запущен с контекстом $ctx, перезапускаю с $($opt.Ctx)..." -ForegroundColor Yellow
    $ours | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Start-Sleep 3
    $ours = $null
}
if (-not $ours) {
    Write-Host "`nЗапускаю сервер Inkling ($($opt.Name))..." -ForegroundColor Cyan
    [void](Get-ApiKey)
    $env:NOBROWSER = '1'
    & cmd /c "`"$Launcher`" $($opt.Arg)"
    Remove-Item Env:NOBROWSER
    if (-not (Get-ServerCtx)) { Write-Host 'Сервер не поднялся, смотрите окно "Inkling server".' -ForegroundColor Red; Read-Host 'Enter - выход' | Out-Null; exit 1 }
} else {
    Write-Host "`nСервер Inkling уже работает с нужным контекстом." -ForegroundColor Green
}

# Claude Code -> локальный сервер (только это окно)
$model = 'inkling'
$env:ANTHROPIC_BASE_URL = $Url
$env:ANTHROPIC_AUTH_TOKEN = Get-ApiKey
$env:ANTHROPIC_API_KEY = ''
foreach ($v in 'ANTHROPIC_MODEL', 'ANTHROPIC_SMALL_FAST_MODEL', 'ANTHROPIC_DEFAULT_SONNET_MODEL', 'ANTHROPIC_DEFAULT_OPUS_MODEL', 'ANTHROPIC_DEFAULT_HAIKU_MODEL') { Set-Item "env:$v" $model }
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = '1'
$env:DISABLE_AUTOUPDATER = '1'
$env:DISABLE_TELEMETRY = '1'
$env:CLAUDE_CODE_MAX_CONTEXT_TOKENS = "$($opt.Ctx)"
$env:CLAUDE_CODE_MAX_OUTPUT_TOKENS = '8192'

Set-Location $folder
Write-Host "`nClaude Code в $folder (контекст $($opt.Ctx)). Первый ответ дольше: модель читает системный промпт ~16K токенов.`n" -ForegroundColor Cyan
$ccArgs = @()
if ($perm.Bypass) { $ccArgs += '--dangerously-skip-permissions' }
if ($Prompt) { & claude @ccArgs -p $Prompt; exit $LASTEXITCODE }
& claude @ccArgs

$ans = Read-Host "`nОстановить сервер Inkling? [Y/n]"
if ($ans -notmatch '^[nNтТ]') { Get-OurServer | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; Write-Host 'Сервер остановлен.' }
