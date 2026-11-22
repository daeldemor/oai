# Inkling в агентном режиме веб-чата: окно выбора папки и контекста, затем сервер с --agent
# в этой папке и чат в браузере. Модель в чате может читать, искать и править файлы и запускать
# команды (инструменты llama-server). Команды идут прямо на этой машине, без песочницы.
# Запуск: ярлык «Inkling Agent» или
#   powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File scripts\inkling-agent.ps1
# Файл в UTF-8 с BOM: без BOM Windows PowerShell 5.1 читает кириллицу как ANSI.

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$Root     = Split-Path $PSScriptRoot -Parent
$Exe      = Join-Path $Root 'llama.cpp-src\build\bin\llama-server.exe'
$Launcher = Join-Path $PSScriptRoot 'inkling.cmd'
$Url      = 'http://127.0.0.1:8080'
$State    = Join-Path $env:LOCALAPPDATA 'inkling'
$LastDir  = Join-Path $State 'last-folder.txt'

$Modes = @(
    @{ Text = '320K: максимум контекста';           Arg = '' },
    @{ Text = '320K: быстрее ответ, медленнее чтение'; Arg = 'fast' },
    @{ Text = '128K: всё быстрее';                  Arg = '128k' }
)

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
function Get-OurServer { Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" | Where-Object { $_.ExecutablePath -eq $Exe } }
function Test-Port { try { (Invoke-RestMethod "$Url/health" -TimeoutSec 2).status -eq 'ok' } catch { $false } }

$font = New-Object System.Drawing.Font('Segoe UI', 10)
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Inkling Agent'
$form.ClientSize = New-Object System.Drawing.Size(560, 268)
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.StartPosition = 'CenterScreen'
$form.Font = $font
$icon = Join-Path $Root 'assets\icons\inkling-agent.ico'
if (Test-Path $icon) { $form.Icon = New-Object System.Drawing.Icon($icon) }

$lblDir = New-Object System.Windows.Forms.Label
$lblDir.Text = 'Папка, в которой агент будет работать:'
$lblDir.SetBounds(16, 14, 520, 22)
$form.Controls.Add($lblDir)

$txtDir = New-Object System.Windows.Forms.TextBox
$txtDir.SetBounds(16, 40, 424, 26)
if (Test-Path $LastDir) { $txtDir.Text = (Get-Content $LastDir -Raw -ErrorAction SilentlyContinue).Trim() }
$form.Controls.Add($txtDir)

$btnBrowse = New-Object System.Windows.Forms.Button
$btnBrowse.Text = 'Обзор…'
$btnBrowse.SetBounds(448, 38, 96, 30)
$btnBrowse.Add_Click({
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = 'Папка для агента Inkling'
    if ($txtDir.Text -and (Test-Path $txtDir.Text)) { $dlg.SelectedPath = $txtDir.Text }
    if ($dlg.ShowDialog($form) -eq 'OK') { $txtDir.Text = $dlg.SelectedPath }
})
$form.Controls.Add($btnBrowse)

$lblCtx = New-Object System.Windows.Forms.Label
$lblCtx.Text = 'Контекст:'
$lblCtx.SetBounds(16, 84, 80, 22)
$form.Controls.Add($lblCtx)

$cmbCtx = New-Object System.Windows.Forms.ComboBox
$cmbCtx.DropDownStyle = 'DropDownList'
$cmbCtx.SetBounds(100, 80, 340, 26)
$Modes | ForEach-Object { [void]$cmbCtx.Items.Add($_.Text) }
$cmbCtx.SelectedIndex = 0
$form.Controls.Add($cmbCtx)

$lblWarn = New-Object System.Windows.Forms.Label
$lblWarn.Text = "Модель сможет читать и менять файлы и запускать команды на этом компьютере, без песочницы. " +
                "Давайте ей папку проекта, а не весь диск. Без подтверждений: в первом запросе стрелка у «Allow once» -> " +
                "«Always allow all tools from Server Tools», браузер запомнит."
$lblWarn.ForeColor = [System.Drawing.Color]::FromArgb(160, 90, 0)
$lblWarn.SetBounds(16, 116, 528, 66)
$form.Controls.Add($lblWarn)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.SetBounds(16, 186, 528, 22)
$lblStatus.ForeColor = [System.Drawing.Color]::DimGray
$form.Controls.Add($lblStatus)

$btnStart = New-Object System.Windows.Forms.Button
$btnStart.Text = 'Запустить'
$btnStart.SetBounds(332, 220, 104, 34)
$form.AcceptButton = $btnStart
$form.Controls.Add($btnStart)

$btnCancel = New-Object System.Windows.Forms.Button
$btnCancel.Text = 'Отмена'
$btnCancel.SetBounds(444, 220, 100, 34)
$btnCancel.Add_Click({ $form.Close() })
$form.CancelButton = $btnCancel
$form.Controls.Add($btnCancel)

function Set-Status($text) { $lblStatus.Text = $text; $form.Refresh() }

$btnStart.Add_Click({
    $dir = [Environment]::ExpandEnvironmentVariables($txtDir.Text.Trim().Trim('"'))
    if (-not $dir -or -not (Test-Path $dir -PathType Container)) {
        [System.Windows.Forms.MessageBox]::Show($form, 'Такой папки нет. Выберите папку через «Обзор…».', 'Inkling Agent') | Out-Null
        return
    }
    $dir = (Resolve-Path $dir).Path
    if ($dir.Length -le 3) {
        $r = [System.Windows.Forms.MessageBox]::Show($form, "Агент получит доступ ко всему диску $dir. Продолжить?", 'Inkling Agent', 'YesNo', 'Warning')
        if ($r -ne 'Yes') { return }
    }
    New-Item -ItemType Directory -Force $State | Out-Null
    Set-Content $LastDir $dir -Encoding UTF8

    $btnStart.Enabled = $false; $btnBrowse.Enabled = $false; $cmbCtx.Enabled = $false
    $ours = Get-OurServer
    if ((Test-Port) -and -not $ours) {
        [System.Windows.Forms.MessageBox]::Show($form, 'Порт 8080 занят другим сервером (Strata?). Остановите его и запустите снова.', 'Inkling Agent') | Out-Null
        $form.Close(); return
    }
    if ($ours) {
        # сервер уже работает (в другой папке или без агента): перезапуск
        Set-Status 'Останавливаю запущенный сервер Inkling…'
        $ours | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
        Start-Sleep 3
    }
    Set-Status 'Загружаю модель, это около 15–30 секунд…'
    $mode = $Modes[$cmbCtx.SelectedIndex].Arg
    $key = Get-ApiKey
    $env:AGENT_DIR = $dir
    $p = Start-Process cmd.exe -ArgumentList "/c `"`"$Launcher`" $mode`"" -WindowStyle Hidden -PassThru
    while (-not $p.HasExited) { [System.Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 200 }
    if (-not (Test-Port)) {
        [System.Windows.Forms.MessageBox]::Show($form, 'Сервер не поднялся. Откройте окно «Inkling server» на панели задач, там ошибка.', 'Inkling Agent') | Out-Null
    } else {
        Set-Clipboard -Value $key
        $seen = Join-Path $State 'api-key-shown.txt'
        if (-not (Test-Path $seen)) {
            [System.Windows.Forms.MessageBox]::Show($form,
                "Сервер защищён ключом, он уже скопирован в буфер обмена.`n`nЕсли чат в браузере попросит API key, вставьте его (Ctrl+V). Браузер запомнит ключ, больше спрашивать не будет.`n`nКлюч лежит в $State\api-key.txt",
                'Inkling Agent') | Out-Null
            Set-Content $seen (Get-Date -Format 'yyyy-MM-dd') -Encoding ASCII
        }
    }
    $form.Close()
})

[void]$form.ShowDialog()
