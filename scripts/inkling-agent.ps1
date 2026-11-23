# Inkling в веб-чате Strata с инструментами: окно выбора рабочей папки, контекста и подтверждений,
# затем сервер Strata (если ещё не запущен) и чат в браузере. Инструменты (файлы, поиск, команды PowerShell)
# даёт scripts\inkling_mcp.py; доступ ко всему компьютеру, рабочая папка — только точка отсчёта для путей.
# Без галочки bypass перед записью файла и командой появляется окно Windows «Разрешить?».
# Запуск: ярлык «Inkling Agent» или
#   powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File scripts\inkling-agent.ps1
# Запасной вариант на llama.cpp: scripts\inkling-agent-llama.ps1.
# Файл в UTF-8 с BOM: без BOM Windows PowerShell 5.1 читает кириллицу как ANSI.

. (Join-Path $PSScriptRoot 'inkling-strata.ps1')
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$LastDir = Join-Path $InkState 'last-folder.txt'
$Modes = @(
    @{ Text = '320K: максимум контекста (чтение 1940 ток/с, ответ ~40)'; Key = '320k' },
    @{ Text = '128K: всё быстрее (чтение 2390 ток/с, ответ ~44)';       Key = '128k' }
)

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Inkling Agent (Strata)'
$form.ClientSize = New-Object System.Drawing.Size(580, 310)
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.StartPosition = 'CenterScreen'
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$icon = Join-Path $InkRoot 'assets\icons\inkling-agent.ico'
if (Test-Path $icon) { $form.Icon = New-Object System.Drawing.Icon($icon) }

$lblDir = New-Object System.Windows.Forms.Label
$lblDir.Text = 'Рабочая папка (от неё считаются относительные пути и запускаются команды):'
$lblDir.SetBounds(16, 14, 548, 22)
$form.Controls.Add($lblDir)

$txtDir = New-Object System.Windows.Forms.TextBox
$txtDir.SetBounds(16, 40, 444, 26)
$txtDir.Text = if (Test-Path $LastDir) { (Get-Content $LastDir -Raw -ErrorAction SilentlyContinue).Trim() } else { $env:USERPROFILE }
$form.Controls.Add($txtDir)

$btnBrowse = New-Object System.Windows.Forms.Button
$btnBrowse.Text = 'Обзор…'
$btnBrowse.SetBounds(468, 38, 96, 30)
$btnBrowse.Add_Click({
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = 'Рабочая папка агента Inkling'
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
$cmbCtx.SetBounds(100, 80, 464, 26)
$Modes | ForEach-Object { [void]$cmbCtx.Items.Add($_.Text) }
$cmbCtx.SelectedIndex = 0
$h = Get-InkHealth
if ($h -and (Get-InkServer) -and [int]$h.max_context -eq 131072) { $cmbCtx.SelectedIndex = 1 }   # не перезагружать зря
$form.Controls.Add($cmbCtx)

$BypassFile = Join-Path $InkState 'agent-bypass.txt'
$chkBypass = New-Object System.Windows.Forms.CheckBox
$chkBypass.Text = 'Без подтверждений (bypass): модель пишет файлы и запускает команды, не спрашивая'
$chkBypass.SetBounds(16, 114, 548, 26)
$chkBypass.Checked = (Test-Path $BypassFile) -and ((Get-Content $BypassFile -Raw -ErrorAction SilentlyContinue).Trim() -eq '1')
$form.Controls.Add($chkBypass)

$lblWarn = New-Object System.Windows.Forms.Label
$lblWarn.Text = "Модель может читать и менять любые файлы и запускать команды на этом компьютере, без песочницы. " +
                "Без галочки перед каждой записью и командой появится окно «Разрешить?»; чтение и поиск идут без вопросов. " +
                "Папку и галочку можно менять при работающем сервере, модель не перезагружается."
$lblWarn.ForeColor = [System.Drawing.Color]::FromArgb(160, 90, 0)
$lblWarn.SetBounds(16, 146, 548, 66)
$form.Controls.Add($lblWarn)
$chkBypass.Add_CheckedChanged({
    $lblWarn.ForeColor = if ($chkBypass.Checked) { [System.Drawing.Color]::FromArgb(190, 30, 30) } else { [System.Drawing.Color]::FromArgb(160, 90, 0) }
})

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.SetBounds(16, 220, 548, 40)
$lblStatus.ForeColor = [System.Drawing.Color]::DimGray
$form.Controls.Add($lblStatus)

$btnStop = New-Object System.Windows.Forms.Button
$btnStop.Text = 'Остановить сервер'
$btnStop.SetBounds(16, 264, 160, 34)
$btnStop.Enabled = [bool](Get-InkServer)
$form.Controls.Add($btnStop)

$btnStart = New-Object System.Windows.Forms.Button
$btnStart.Text = 'Запустить'
$btnStart.SetBounds(352, 264, 104, 34)
$form.AcceptButton = $btnStart
$form.Controls.Add($btnStart)

$btnCancel = New-Object System.Windows.Forms.Button
$btnCancel.Text = 'Закрыть'
$btnCancel.SetBounds(464, 264, 100, 34)
$btnCancel.Add_Click({ $form.Close() })
$form.CancelButton = $btnCancel
$form.Controls.Add($btnCancel)

function Set-Status($text) { $lblStatus.Text = $text; $form.Refresh() }
if (Get-InkServer) { Set-Status 'Сервер Inkling уже работает: «Запустить» откроет чат с новыми настройками.' }

$btnStop.Add_Click({
    Set-Status 'Останавливаю сервер…'
    Stop-InkServer
    $btnStop.Enabled = $false
    Set-Status 'Сервер остановлен, видеопамять и RAM свободны.'
})

$btnStart.Add_Click({
    $dir = [Environment]::ExpandEnvironmentVariables($txtDir.Text.Trim().Trim('"'))
    if (-not $dir -or -not (Test-Path $dir -PathType Container)) {
        [System.Windows.Forms.MessageBox]::Show($form, 'Такой папки нет. Выберите папку через «Обзор…».', 'Inkling Agent') | Out-Null
        return
    }
    $dir = (Resolve-Path $dir).Path
    New-Item -ItemType Directory -Force $InkState | Out-Null
    Set-Content $LastDir $dir -Encoding UTF8
    Set-Content $BypassFile $(if ($chkBypass.Checked) { '1' } else { '0' }) -Encoding ASCII
    Set-InkAgentState $dir $chkBypass.Checked

    foreach ($c in $btnStart, $btnStop, $btnBrowse, $cmbCtx, $chkBypass, $txtDir) { $c.Enabled = $false }
    $mode = $Modes[$cmbCtx.SelectedIndex].Key
    $hh = Get-InkHealth
    if (-not ($hh -and (Get-InkServer) -and [int]$hh.max_context -eq $InkModes[$mode].Ctx)) {
        Set-Status 'Загружаю модель, это около минуты…'
    }
    $err = Start-InkServer $mode { [System.Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 200 }
    if ($err) {
        [System.Windows.Forms.MessageBox]::Show($form, $err, 'Inkling Agent') | Out-Null
        $form.Close(); return
    }
    Start-Process "$InkUrl/?lang=ru"
    $form.Close()
})

[void]$form.ShowDialog()
