# Накладывает наши правки на установленный Strata control (serve/*.py, serve/web/*): patches/strata-control-*.patch.
# После обновления Strata правки пропадают; запустите этот скрипт. Уже наложенный патч пропускается.
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\strata-patch.ps1 [-Check]
param([switch]$Check)
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}   # иначе при перехвате вывода кириллица ломается
. (Join-Path $PSScriptRoot 'inkling-strata.ps1')
$ctl = Get-StrataControl
$ver = Split-Path $ctl -Leaf
$patches = Get-ChildItem (Join-Path $InkRoot 'patches') -Filter "strata-control-$ver-*.patch"
if (-not $patches) { "Нет патчей для Strata control $ver (есть: $((Get-ChildItem (Join-Path $InkRoot 'patches') -Filter 'strata-control-*.patch').Name -join ', ')). Их нужно перенести на новую версию."; exit 1 }
foreach ($p in $patches) {
    Push-Location $ctl
    try {
        git apply --reverse --check $p.FullName 2>$null
        if ($LASTEXITCODE -eq 0) { "$($p.Name): уже наложен"; continue }
        git apply --check $p.FullName
        if ($LASTEXITCODE -ne 0) { "$($p.Name): не накладывается на эту версию, нужен перенос"; continue }
        if ($Check) { "$($p.Name): можно наложить"; continue }
        # оригиналы рядом, как .orig: от них и строятся патчи
        Select-String -Path $p.FullName -Pattern '^\+\+\+ b/(.+)$' | ForEach-Object {
            $f = Join-Path $ctl $_.Matches[0].Groups[1].Value
            if (-not (Test-Path "$f.orig")) { Copy-Item $f "$f.orig" }
        }
        git apply $p.FullName
        if ($LASTEXITCODE -eq 0) { "$($p.Name): наложен" } else { "$($p.Name): ошибка" }
    } finally { Pop-Location }
}
"Перезапустите сервер Strata, чтобы правки заработали."
