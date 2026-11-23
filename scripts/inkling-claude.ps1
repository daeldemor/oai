# Claude Code на локальном Inkling-2-Mini через Strata (Anthropic API /v1/messages).
# Выбор контекста и разрешений стрелками, папка проекта вводится с клавиатуры, сервер поднимается сам.
# Запуск: ярлык «Inkling CLI» или
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\inkling-claude.ps1
# Переменные Claude Code задаются только в этом окне, обычный облачный Claude Code не затронут.
# Без меню: -Mode 320k|128k -Folder <папка> [-Bypass] [-Prompt "задача"] (с -Prompt один запрос, claude -p).
# -Bypass: Claude Code без запросов разрешений (--dangerously-skip-permissions).
# Запасной вариант на llama.cpp: scripts\inkling-claude-llama.ps1.
# Файл сохранён в UTF-8 с BOM: без BOM Windows PowerShell 5.1 читает кириллицу как ANSI.
param(
    [ValidateSet('320k', '128k')] [string] $Mode,
    [string] $Folder,
    [string] $Prompt,
    [switch] $Bypass,
    [switch] $KeepServer
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'inkling-strata.ps1')
$LastDir = Join-Path $InkState 'last-folder.txt'
$Host.UI.RawUI.WindowTitle = 'Inkling CLI'

$Options = @(
    @{ Name = '320K'; Key = '320k'; Note = 'максимум контекста: чтение промпта ~1940 ток/с, ответ ~40 ток/с' },
    @{ Name = '128K'; Key = '128k'; Note = 'всё быстрее: чтение ~2390 ток/с, ответ ~44 ток/с' }
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
            New-Item -ItemType Directory -Force $InkState | Out-Null
            Set-Content $LastDir $full -Encoding UTF8
            return $full
        }
        Write-Host "  Папки нет: $in" -ForegroundColor Yellow
    }
}

Write-Host "`n  Inkling-2-Mini Uncensored + Claude Code (Strata)`n" -ForegroundColor White
if ($Mode) {
    $opt = $Options | Where-Object { $_.Key -eq $Mode }
} else {
    $opt = Select-Option 'Длина контекста:' $Options
    if (-not $opt) { exit 0 }
}
Write-Host "  Выбрано: $($opt.Name)" -ForegroundColor Green
$Perms = @(
    @{ Name = 'Спрашивать';      Note = 'Claude Code спрашивает перед правкой файлов и командами'; Bypass = $false },
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

$ctx = $InkModes[$opt.Key].Ctx
$h = Get-InkHealth
if ($h -and (Get-InkServer) -and [int]$h.max_context -eq $ctx) {
    Write-Host "`nСервер Inkling уже работает с нужным контекстом." -ForegroundColor Green
} else {
    Write-Host "`nЗапускаю сервер Inkling на Strata ($($opt.Name)), около минуты..." -ForegroundColor Cyan
    $err = Start-InkServer $opt.Key
    if ($err) { Write-Host $err -ForegroundColor Red; Read-Host 'Enter - выход' | Out-Null; exit 1 }
}

# Claude Code -> локальный сервер (только это окно). Ключа у сервера нет, токен любой непустой.
$model = 'inkling'
$env:ANTHROPIC_BASE_URL = $InkUrl
$env:ANTHROPIC_AUTH_TOKEN = 'local'
$env:ANTHROPIC_API_KEY = ''
foreach ($v in 'ANTHROPIC_MODEL', 'ANTHROPIC_SMALL_FAST_MODEL', 'ANTHROPIC_DEFAULT_SONNET_MODEL', 'ANTHROPIC_DEFAULT_OPUS_MODEL', 'ANTHROPIC_DEFAULT_HAIKU_MODEL') { Set-Item "env:$v" $model }
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = '1'
$env:DISABLE_AUTOUPDATER = '1'
$env:DISABLE_TELEMETRY = '1'
$env:CLAUDE_CODE_MAX_CONTEXT_TOKENS = "$ctx"
$env:CLAUDE_CODE_MAX_OUTPUT_TOKENS = '8192'

Set-Location $folder
Write-Host "`nClaude Code в $folder (контекст $ctx). Первый ответ дольше: модель читает системный промпт ~16K токенов.`n" -ForegroundColor Cyan
$ccArgs = @()
if ($perm.Bypass) { $ccArgs += '--dangerously-skip-permissions' }
if ($Prompt) { & claude @ccArgs -p $Prompt; exit $LASTEXITCODE }
& claude @ccArgs

if ($KeepServer) { exit 0 }
$ans = Read-Host "`nОстановить сервер Inkling? [Y/n]"
if ($ans -notmatch '^[nNтТ]') { Stop-InkServer; Write-Host 'Сервер остановлен.' }
