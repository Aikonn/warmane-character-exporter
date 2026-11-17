<#
Mini launcher for the Warmane character exporter (Windows, PowerShell 5.1, no extra software).

Double-click Start-Report.cmd. It asks for an armory link, asks where to save the HTML report,
runs the exporter, then opens the report in the default browser.

For testing or scripting the prompts can be skipped:
  .\Start-Report.ps1 -Link https://armory.warmane.com/character/Aikka/Onyxia/summary -Output C:\temp\report.html [-Quick] [-Offline] [-NoOpen]
-Quick makes the quick report (gear, talents, glyphs, professions, raid readiness; 3 requests); the default is the full PvE report.
-Offline makes no requests and rebuilds from data already collected.
#>
param(
    [string]$Link,
    [string]$Output,
    [switch]$Offline,
    [switch]$NoOpen,
    [switch]$Quick,
    [switch]$Full,
    [switch]$InstallPython
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
# The window is hidden, so an unexpected error would end the script silently: always tell the user.
trap {
    try { [System.IO.File]::AppendAllText((Join-Path $PSScriptRoot ".warmane-cache\launcher-error.log"), ("[" + (Get-Date) + "] " + ($_ | Out-String) + "`r`n")) } catch { }
    [void][System.Windows.Forms.MessageBox]::Show("Unexpected error: " + $_.Exception.Message + "`r`n(details in .warmane-cache\launcher-error.log)", "Warmane Character Exporter", "OK", "Error")
    exit 1
}
[System.Windows.Forms.Application]::EnableVisualStyles()

$root = $PSScriptRoot
Set-Location $root
$cache = Join-Path $root ".warmane-cache"
New-Item -ItemType Directory -Force -Path $cache, (Join-Path $root ".tools\tmp") | Out-Null
$logOut = Join-Path $cache "launcher.log"
$modeFile = Join-Path $cache "launcher-mode.txt"
$logErr = Join-Path $cache "launcher-error.log"
$pattern = 'armory\.warmane\.com/character/([^/\s?#"''<>]+)/([^/\s?#"''<>]+)'

function Show-Message([string]$text, [string]$title, [string]$icon = "Information") {
    [void][System.Windows.Forms.MessageBox]::Show($text, $title, "OK", $icon)
}

function Get-DownloadsFolder {
    # The user's Downloads folder, also when it was moved (known folder lookup); fallback: %USERPROFILE%\Downloads.
    try {
        Add-Type -Namespace Win32 -Name Known -MemberDefinition '[DllImport("shell32.dll")] public static extern int SHGetKnownFolderPath([MarshalAs(UnmanagedType.LPStruct)] System.Guid id, uint flags, System.IntPtr token, out System.IntPtr path);' -ErrorAction SilentlyContinue
        $ptr = [System.IntPtr]::Zero
        if ([Win32.Known]::SHGetKnownFolderPath([System.Guid]"374DE290-123F-4565-9164-39C4925E467B", 0, [System.IntPtr]::Zero, [ref]$ptr) -eq 0) {
            $path = [System.Runtime.InteropServices.Marshal]::PtrToStringUni($ptr)
            [System.Runtime.InteropServices.Marshal]::FreeCoTaskMem($ptr)
            if ($path -and (Test-Path $path)) { return $path }
        }
    } catch { }
    $fallback = Join-Path $env:USERPROFILE "Downloads"
    if (Test-Path $fallback) { return $fallback }
    return [Environment]::GetFolderPath("MyDocuments")
}

function Test-PythonVersion([string]$exe) {
    try {
        $v = & $exe -c "import sys; print(sys.version_info >= (3, 12))" 2>$null
        return ($v -eq "True")
    } catch { return $false }
}

function Find-Python {
    $embedded = Join-Path $root ".tools\python312\python.exe"
    if (Test-Path $embedded) { return $embedded }
    foreach ($name in "python", "py") {
        $found = Get-Command $name -ErrorAction SilentlyContinue
        if ($found -and (Test-PythonVersion $found.Source)) { return $found.Source }
    }
    return $null
}

function Install-Python {
    # First run on a machine without Python 3.12+: fetch the official portable (embeddable) Python into .tools\python312.
    $url = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
    $zip = Join-Path $root ".tools\python-embed.zip"
    $target = Join-Path $root ".tools\python312"
    $note = New-Object System.Windows.Forms.Form
    $note.Text = "Warmane Character Exporter"
    $note.StartPosition = "CenterScreen"
    $note.FormBorderStyle = "FixedDialog"
    $note.ControlBox = $false
    $note.ClientSize = New-Object System.Drawing.Size(420, 70)
    $label = New-Object System.Windows.Forms.Label
    $label.Text = "First run: downloading portable Python (about 11 MB) from python.org ..."
    $label.Location = New-Object System.Drawing.Point(12, 20)
    $label.Size = New-Object System.Drawing.Size(396, 40)
    $note.Controls.Add($label)
    $note.Show()
    [System.Windows.Forms.Application]::DoEvents()
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        New-Item -ItemType Directory -Force -Path (Join-Path $root ".tools") | Out-Null
        $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
        if ($curl) {
            & $curl.Source -sS -L -m 300 -o $zip $url
            if ($LASTEXITCODE -ne 0) { throw "curl failed with exit code $LASTEXITCODE" }
        } else {
            Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
        }
        if (Test-Path $target) { Remove-Item -Recurse -Force $target }
        Expand-Archive -Path $zip -DestinationPath $target -Force
        Remove-Item $zip -Force
        $pth = Get-ChildItem $target -Filter "*._pth" | Select-Object -First 1
        [System.IO.File]::WriteAllText($pth.FullName, "python312.zip`r`n.`r`n..\..\src`r`nimport site`r`n", [System.Text.Encoding]::ASCII)
        return $true
    } catch {
        Show-Message ("Could not download Python: " + $_.Exception.Message + "`r`nInstall Python 3.12 or newer from https://www.python.org/downloads/ and start again.") "Warmane Character Exporter" "Error"
        return $false
    } finally {
        $note.Close()
    }
}

function Invoke-Updater([string]$command) {
    $stdoutPath = Join-Path $root (".tools\tmp\updater-{0}.out" -f [guid]::NewGuid().ToString("N"))
    $stderrPath = Join-Path $root (".tools\tmp\updater-{0}.err" -f [guid]::NewGuid().ToString("N"))
    $savedTemp = $env:TEMP
    $savedTmp = $env:TMP
    $savedPath = $env:PYTHONPATH
    $savedEncoding = $env:PYTHONIOENCODING
    try {
        $env:TEMP = Join-Path $root ".tools\tmp"
        $env:TMP = $env:TEMP
        $env:PYTHONPATH = Join-Path $root "src"
        $env:PYTHONIOENCODING = "utf-8"
        $process = Start-Process -FilePath $python -ArgumentList "-m warmane_exporter.updater $command" `
            -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath -PassThru
        while (-not $process.HasExited) {
            [System.Windows.Forms.Application]::DoEvents()
            Start-Sleep -Milliseconds 100
        }
        $process.WaitForExit()
        $stdout = if (Test-Path $stdoutPath) { [System.IO.File]::ReadAllText($stdoutPath, [System.Text.Encoding]::UTF8) } else { "" }
        $stderr = if (Test-Path $stderrPath) { [System.IO.File]::ReadAllText($stderrPath, [System.Text.Encoding]::UTF8) } else { "" }
        return [pscustomobject]@{ ExitCode = [int]$process.ExitCode; Stdout = $stdout.Trim(); Stderr = $stderr.Trim() }
    } catch {
        return [pscustomobject]@{ ExitCode = 1; Stdout = ""; Stderr = $_.Exception.Message }
    } finally {
        $env:TEMP = $savedTemp
        $env:TMP = $savedTmp
        $env:PYTHONPATH = $savedPath
        $env:PYTHONIOENCODING = $savedEncoding
        foreach ($path in $stdoutPath, $stderrPath) {
            if (Test-Path $path) { Remove-Item -LiteralPath $path -Force }
        }
    }
}

function Show-Settings([System.Windows.Forms.Form]$owner, [hashtable]$shared) {
    $settings = New-Object System.Windows.Forms.Form
    $settings.Text = "Settings"
    $settings.StartPosition = "CenterParent"
    $settings.FormBorderStyle = "FixedDialog"
    $settings.MaximizeBox = $false
    $settings.MinimizeBox = $false
    $settings.ClientSize = New-Object System.Drawing.Size(480, 230)
    $settings.Font = $owner.Font

    $updates = New-Object System.Windows.Forms.GroupBox
    $updates.Text = "Updates"
    $updates.Location = New-Object System.Drawing.Point(12, 10)
    $updates.Size = New-Object System.Drawing.Size(456, 170)
    $status = New-Object System.Windows.Forms.Label
    $status.Text = "Not checked yet. Checking contacts github.com."
    $status.Location = New-Object System.Drawing.Point(14, 26)
    $status.Size = New-Object System.Drawing.Size(428, 34)
    $latest = New-Object System.Windows.Forms.Label
    $latest.Text = "Latest: -"
    $latest.Location = New-Object System.Drawing.Point(14, 62)
    $latest.Size = New-Object System.Drawing.Size(428, 34)
    $tooltip = New-Object System.Windows.Forms.ToolTip
    $checkButton = New-Object System.Windows.Forms.Button
    $checkButton.Text = "Check for updates"
    $checkButton.Location = New-Object System.Drawing.Point(14, 102)
    $checkButton.Size = New-Object System.Drawing.Size(148, 28)
    $updateButton = New-Object System.Windows.Forms.Button
    $updateButton.Text = "Update now"
    $updateButton.Location = New-Object System.Drawing.Point(174, 102)
    $updateButton.Size = New-Object System.Drawing.Size(110, 28)
    $updateButton.Enabled = $false
    $manual = New-Object System.Windows.Forms.LinkLabel
    $manual.Text = "Manual update: github.com/Aikonn/warmane-character-exporter"
    $manual.Location = New-Object System.Drawing.Point(14, 140)
    $manual.Size = New-Object System.Drawing.Size(428, 20)
    $manual.Add_LinkClicked({
        Start-Process -FilePath "https://github.com/Aikonn/warmane-character-exporter"
    }.GetNewClosure())
    $updates.Controls.AddRange(@($status, $latest, $checkButton, $updateButton, $manual))

    $close = New-Object System.Windows.Forms.Button
    $close.Text = "Close"
    $close.Size = New-Object System.Drawing.Size(90, 28)
    $close.Location = New-Object System.Drawing.Point(378, 190)
    $close.DialogResult = "Cancel"
    $settings.CancelButton = $close
    $settings.Controls.AddRange(@($updates, $close))

    $state = @{ Check = $null }
    $checkButton.Add_Click({
        $status.Text = "Checking..."
        $status.ForeColor = [System.Drawing.SystemColors]::ControlText
        $latest.Text = "Latest: -"
        $tooltip.SetToolTip($status, "")
        $checkButton.Enabled = $false
        $updateButton.Enabled = $false
        $run = Invoke-Updater "check"
        $result = $null
        try {
            $result = ConvertFrom-Json -InputObject $run.Stdout -ErrorAction Stop
        } catch {
            $lastError = @($run.Stderr -split "`r?`n" | Where-Object { $_.Trim() })
            $status.Text = "Check failed. " + $(if ($lastError.Count -gt 0) { $lastError[-1] } else { "The updater returned invalid JSON." })
            $status.ForeColor = [System.Drawing.Color]::DarkRed
            $state.Check = $null
            $checkButton.Enabled = $true
            return
        }
        $state.Check = $result
        if ($result.latest) {
            try {
                $date = [DateTimeOffset]::Parse([string]$result.latest.date).ToLocalTime().ToString("yyyy-MM-dd HH:mm")
                $latest.Text = 'Latest: {0} "{1}"' -f $date, $result.latest.message
            } catch {
                $latest.Text = 'Latest: "{0}"' -f $result.latest.message
            }
        }
        switch ([string]$result.status) {
            "up_to_date" { $status.Text = "Up to date." }
            "update_available" {
                $status.Text = "Update available: " + $result.message
                $paths = @($result.changed) + @($result.missing) + @($result.stale)
                $paths = @($paths | Where-Object { $_ })
                $shown = @($paths | Select-Object -First 20)
                $more = $paths.Count - $shown.Count
                if ($more -gt 0) { $shown += "and $more more" }
                if ($shown.Count -gt 0) { $tooltip.SetToolTip($status, ($shown -join "`r`n")) }
                $updateButton.Enabled = $true
            }
            "git_clone" {
                $status.Text = [string]$result.message
                if ($result.behind) { $status.Text += " (behind GitHub)" }
            }
            "error" {
                $status.Text = [string]$result.message
                $status.ForeColor = [System.Drawing.Color]::DarkRed
            }
            default {
                $status.Text = "Check failed. The updater returned an unexpected result."
                $status.ForeColor = [System.Drawing.Color]::DarkRed
                $state.Check = $null
            }
        }
        $checkButton.Enabled = $true
    }.GetNewClosure())
    $updateButton.Add_Click({
        if (-not $state.Check -or $state.Check.status -ne "update_available") { return }
        $answer = [System.Windows.Forms.MessageBox]::Show(
            "Download the latest version (about 4 MB) from GitHub and replace the program files? Reports, cache and Python stay.",
            "Warmane Character Exporter", "YesNo", "Question"
        )
        if ($answer -ne "Yes") { return }
        $status.Text = "Updating..."
        $status.ForeColor = [System.Drawing.SystemColors]::ControlText
        $checkButton.Enabled = $false
        $updateButton.Enabled = $false
        $run = Invoke-Updater "apply"
        $result = $null
        try {
            $result = ConvertFrom-Json -InputObject $run.Stdout -ErrorAction Stop
        } catch {
            $lastError = @($run.Stderr -split "`r?`n" | Where-Object { $_.Trim() })
            $status.Text = "Update failed. " + $(if ($lastError.Count -gt 0) { $lastError[-1] } else { "The updater returned invalid JSON." })
            $status.ForeColor = [System.Drawing.Color]::DarkRed
            $checkButton.Enabled = $true
            $updateButton.Enabled = $true
            return
        }
        if ($run.ExitCode -eq 0 -and $result.status -eq "updated") {
            Show-Message "Updated. The launcher will now restart. If it does not open, start Start-Report.cmd again." "Warmane Character Exporter"
            $shared.Restart = $true
            $settings.Close()
            $owner.Close()
            return
        }
        $status.Text = [string]$result.message
        $status.ForeColor = if ($result.status -eq "error") { [System.Drawing.Color]::DarkRed } else { [System.Drawing.SystemColors]::ControlText }
        $checkButton.Enabled = $true
        $updateButton.Enabled = ($state.Check -and $state.Check.status -eq "update_available")
    }.GetNewClosure())
    [void]$settings.ShowDialog($owner)
}

function Read-Link {
    $shared = @{ Restart = $false }
    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Warmane Character Exporter"
    $form.StartPosition = "CenterScreen"
    $form.FormBorderStyle = "FixedDialog"
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.ClientSize = New-Object System.Drawing.Size(520, 240)
    $label = New-Object System.Windows.Forms.Label
    $label.Text = "Paste the armory link of the character (Onyxia or Icecrown):"
    $label.Location = New-Object System.Drawing.Point(12, 12)
    $label.AutoSize = $true
    $box = New-Object System.Windows.Forms.TextBox
    $box.Location = New-Object System.Drawing.Point(12, 38)
    $box.Size = New-Object System.Drawing.Size(496, 24)
    try { if ([System.Windows.Forms.Clipboard]::ContainsText()) { $clip = [System.Windows.Forms.Clipboard]::GetText(); if ($clip -match $pattern) { $box.Text = $clip.Trim() } } } catch { }
    $hint = New-Object System.Windows.Forms.Label
    $hint.Text = "Example: https://armory.warmane.com/character/Aikka/Onyxia/summary"
    $hint.ForeColor = [System.Drawing.Color]::Gray
    $hint.Location = New-Object System.Drawing.Point(12, 68)
    $hint.AutoSize = $true
    $quickButton = New-Object System.Windows.Forms.RadioButton
    $quickButton.Text = "Quick report: gear, talents, glyphs, professions and raid readiness (fast, 3 requests)"
    $quickButton.Location = New-Object System.Drawing.Point(12, 98)
    $quickButton.Size = New-Object System.Drawing.Size(496, 22)
    $fullButton = New-Object System.Windows.Forms.RadioButton
    $fullButton.Text = "Full PvE report: adds raid progression, achievements, reputation and mounts (slower)"
    $fullButton.Location = New-Object System.Drawing.Point(12, 124)
    $fullButton.Size = New-Object System.Drawing.Size(496, 22)
    $rosterButton = New-Object System.Windows.Forms.RadioButton
    $rosterButton.Text = "Raid roster: quick report for a list of characters"
    $rosterButton.Location = New-Object System.Drawing.Point(12, 150)
    $rosterButton.Size = New-Object System.Drawing.Size(496, 22)
    if (Test-Path $modeFile) { $lastMode = (Get-Content $modeFile -Raw).Trim() } else { $lastMode = "full" }
    if ($Quick -or ($lastMode -eq "quick" -and -not $Full)) {
        $quickButton.Checked = $true
    } elseif ($lastMode -eq "roster" -and -not $Quick -and -not $Full) {
        $rosterButton.Checked = $true
    } else {
        $fullButton.Checked = $true
    }
    $box.Enabled = -not $rosterButton.Checked
    $rosterButton.Add_CheckedChanged({ $box.Enabled = -not $rosterButton.Checked }.GetNewClosure())
    $ok = New-Object System.Windows.Forms.Button
    $ok.Text = "Create report"
    $ok.Size = New-Object System.Drawing.Size(110, 28)
    $ok.Location = New-Object System.Drawing.Point(288, 190)
    $ok.DialogResult = "OK"
    $settingsButton = New-Object System.Windows.Forms.Button
    $settingsButton.Text = ([char]0x2699).ToString() + " Settings"
    $settingsButton.FlatStyle = "Flat"
    $settingsButton.FlatAppearance.BorderSize = 0
    $settingsButton.ForeColor = [System.Drawing.SystemColors]::GrayText
    $settingsButton.Size = New-Object System.Drawing.Size(100, 28)
    $settingsButton.Location = New-Object System.Drawing.Point(12, 190)
    $settingsButton.Cursor = [System.Windows.Forms.Cursors]::Hand
    $settingsButton.Font = $form.Font
    $settingsButton.Add_Click({ Show-Settings $form $shared }.GetNewClosure())
    $cancel = New-Object System.Windows.Forms.Button
    $cancel.Text = "Cancel"
    $cancel.Size = New-Object System.Drawing.Size(100, 28)
    $cancel.Location = New-Object System.Drawing.Point(408, 190)
    $cancel.DialogResult = "Cancel"
    $form.AcceptButton = $ok
    $form.CancelButton = $cancel
    $form.Controls.AddRange(@($label, $box, $hint, $quickButton, $fullButton, $rosterButton, $settingsButton, $ok, $cancel))
    while ($true) {
        $form.TopMost = $true      # appears in front once; the user can still put other windows over it
        $form.Add_Shown({ $form.Activate(); $form.TopMost = $false })
        $dialogResult = $form.ShowDialog()
        $script:restartLauncher = $shared.Restart
        if ($dialogResult -ne "OK") { return $null }
        if ($rosterButton.Checked) {
            $script:RosterMode = $true
            try { Set-Content -Path $modeFile -Value "roster" -Encoding ASCII } catch { }
            return ""
        }
        if ($box.Text -match $pattern) {
            $script:RosterMode = $false
            $script:Quick = [bool]$quickButton.Checked
            try { Set-Content -Path $modeFile -Value $(if ($script:Quick) { "quick" } else { "full" }) -Encoding ASCII } catch { }
            return $box.Text.Trim()
        }
        Show-Message "That does not look like a Warmane armory character link." "Warmane Character Exporter" "Warning"
    }
}

function Read-Roster([string]$initialNames) {
    $realmFile = Join-Path $cache "launcher-realm.txt"
    $folderFile = Join-Path $cache "launcher-roster-folder.txt"
    $lastRealm = if (Test-Path $realmFile) { (Get-Content $realmFile -Raw).Trim() } else { "Onyxia" }
    if ($lastRealm -notin @("Onyxia", "Icecrown")) { $lastRealm = "Onyxia" }
    $lastFolder = if (Test-Path $folderFile) { (Get-Content $folderFile -Raw).Trim() } else { Get-DownloadsFolder }
    if (-not $lastFolder) { $lastFolder = Get-DownloadsFolder }

    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Raid roster reports"
    $form.StartPosition = "CenterScreen"
    $form.FormBorderStyle = "FixedDialog"
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.ClientSize = New-Object System.Drawing.Size(620, 430)

    $namesLabel = New-Object System.Windows.Forms.Label
    $namesLabel.Text = "Character names (one per line):"
    $namesLabel.Location = New-Object System.Drawing.Point(12, 12)
    $namesLabel.AutoSize = $true
    $names = New-Object System.Windows.Forms.TextBox
    $names.Location = New-Object System.Drawing.Point(12, 36)
    $names.Size = New-Object System.Drawing.Size(596, 200)
    $names.Multiline = $true
    $names.AcceptsReturn = $true
    $names.ScrollBars = "Vertical"
    $names.WordWrap = $false
    $names.Text = $initialNames

    $realmLabel = New-Object System.Windows.Forms.Label
    $realmLabel.Text = "Realm:"
    $realmLabel.Location = New-Object System.Drawing.Point(12, 248)
    $realmLabel.AutoSize = $true
    $realm = New-Object System.Windows.Forms.ComboBox
    $realm.Location = New-Object System.Drawing.Point(74, 244)
    $realm.Size = New-Object System.Drawing.Size(150, 24)
    $realm.DropDownStyle = "DropDownList"
    [void]$realm.Items.AddRange([object[]]@("Onyxia", "Icecrown"))
    $realm.SelectedItem = $lastRealm

    $refresh = New-Object System.Windows.Forms.CheckBox
    $refresh.Text = "Refresh all"
    $refresh.Location = New-Object System.Drawing.Point(250, 246)
    $refresh.AutoSize = $true

    $folderLabel = New-Object System.Windows.Forms.Label
    $folderLabel.Text = "Output folder:"
    $folderLabel.Location = New-Object System.Drawing.Point(12, 286)
    $folderLabel.AutoSize = $true
    $folder = New-Object System.Windows.Forms.TextBox
    $folder.Location = New-Object System.Drawing.Point(12, 310)
    $folder.Size = New-Object System.Drawing.Size(500, 24)
    $folder.Text = $lastFolder
    $browse = New-Object System.Windows.Forms.Button
    $browse.Text = "Browse..."
    $browse.Location = New-Object System.Drawing.Point(518, 308)
    $browse.Size = New-Object System.Drawing.Size(90, 28)
    $browse.Add_Click({
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $dialog.Description = "Choose where to save the roster reports"
        $dialog.ShowNewFolderButton = $true
        $dialog.SelectedPath = $folder.Text
        if ($dialog.ShowDialog($form) -eq "OK") { $folder.Text = $dialog.SelectedPath }
    }.GetNewClosure())

    $create = New-Object System.Windows.Forms.Button
    $create.Text = "Create reports"
    $create.Size = New-Object System.Drawing.Size(110, 28)
    $create.Location = New-Object System.Drawing.Point(378, 378)
    $create.DialogResult = "OK"
    $cancel = New-Object System.Windows.Forms.Button
    $cancel.Text = "Cancel"
    $cancel.Size = New-Object System.Drawing.Size(100, 28)
    $cancel.Location = New-Object System.Drawing.Point(498, 378)
    $cancel.DialogResult = "Cancel"
    $form.AcceptButton = $create
    $form.CancelButton = $cancel
    $form.Controls.AddRange(@(
        $namesLabel, $names, $realmLabel, $realm, $refresh, $folderLabel,
        $folder, $browse, $create, $cancel
    ))

    while ($true) {
        $form.TopMost = $true
        $form.Add_Shown({ $form.Activate(); $form.TopMost = $false })
        if ($form.ShowDialog() -ne "OK") { return $null }
        if ($realm.SelectedItem -and $folder.Text.Trim()) {
            try {
                [System.IO.File]::WriteAllText($realmFile, [string]$realm.SelectedItem, [System.Text.Encoding]::UTF8)
                [System.IO.File]::WriteAllText($folderFile, $folder.Text.Trim(), [System.Text.Encoding]::UTF8)
            } catch {
                Show-Message ("Could not remember roster settings: " + $_.Exception.Message) "Raid roster reports" "Warning"
            }
            return [pscustomobject]@{
                Names = $names.Text
                Realm = [string]$realm.SelectedItem
                Refresh = [bool]$refresh.Checked
                OutputFolder = $folder.Text.Trim()
            }
        }
        Show-Message "Choose a realm and output folder." "Raid roster reports" "Warning"
    }
}

if (-not ("Win32.Native" -as [type])) {
    Add-Type -Namespace Win32 -Name Native -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr hWnd);'
}

function Invoke-ProgressProcess([string]$arguments, [string]$windowTitle, [switch]$RosterMode) {
    [System.IO.File]::WriteAllText($logOut, "")
    [System.IO.File]::WriteAllText($logErr, "")
    $script:cancelled = $false
    $progressState = @{ Process = $null; Cancelled = $false }
    $wait = New-Object System.Windows.Forms.Form
    $wait.Text = "Warmane Character Exporter"
    $wait.StartPosition = "CenterScreen"
    $wait.FormBorderStyle = "FixedDialog"
    $wait.MaximizeBox = $false
    $wait.ClientSize = New-Object System.Drawing.Size(520, 175)
    $title = New-Object System.Windows.Forms.Label
    $title.Text = $windowTitle
    $title.Location = New-Object System.Drawing.Point(12, 12)
    $title.AutoSize = $true
    $percentLabel = New-Object System.Windows.Forms.Label
    $percentLabel.Text = "0%"
    $percentLabel.Font = New-Object System.Drawing.Font("Segoe UI", 22)
    $percentLabel.Location = New-Object System.Drawing.Point(12, 36)
    $percentLabel.Size = New-Object System.Drawing.Size(120, 44)
    $status = New-Object System.Windows.Forms.Label
    $status.Text = "Starting"
    $status.Location = New-Object System.Drawing.Point(140, 46)
    $status.Size = New-Object System.Drawing.Size(250, 40)
    $stop = New-Object System.Windows.Forms.Button
    $stop.Text = "Stop"
    $stop.Location = New-Object System.Drawing.Point(402, 46)
    $stop.Size = New-Object System.Drawing.Size(106, 28)
    $stop.Enabled = $false
    $stop.Add_Click({
        $processToStop = $progressState.Process
        if (-not $processToStop -or $processToStop.HasExited) { return }
        if ($RosterMode) {
            try {
                [System.IO.File]::WriteAllText((Join-Path $cache "stop-request"), "stop")
            } catch {
                Show-Message ("Could not request a roster stop: " + $_.Exception.Message) "Raid roster reports" "Error"
                return
            }
            $stop.Enabled = $false
            $status.Text = "Stopping roster and preparing the partial summary..."
            $deadline = [DateTime]::UtcNow.AddSeconds(15)
            while (-not $processToStop.HasExited -and [DateTime]::UtcNow -lt $deadline) {
                [System.Windows.Forms.Application]::DoEvents()
                Start-Sleep -Milliseconds 100
            }
            if (-not $processToStop.HasExited) { try { $processToStop.Kill() } catch { } }
        } else {
            $answer = [System.Windows.Forms.MessageBox]::Show(
                "Stop the export? Data already fetched is kept, so a new run continues where this one stopped.",
                "Warmane Character Exporter", "YesNo", "Question"
            )
            if ($answer -eq "Yes") {
                $progressState.Cancelled = $true
                $status.Text = "Stopping export..."
                try { $processToStop.Kill() } catch { }
            }
        }
    }.GetNewClosure())
    $elapsedLabel = New-Object System.Windows.Forms.Label
    $elapsedLabel.Text = "Elapsed 0:00"
    $elapsedLabel.ForeColor = [System.Drawing.Color]::Gray
    $elapsedLabel.Location = New-Object System.Drawing.Point(12, 100)
    $elapsedLabel.Size = New-Object System.Drawing.Size(496, 65)
    $wait.Controls.AddRange(@($title, $percentLabel, $status, $stop, $elapsedLabel))
    $wait.Add_FormClosing({
        param($sender, $e)
        if ($script:process -and -not $script:process.HasExited) {
            $answer = [System.Windows.Forms.MessageBox]::Show("Stop the export? Data already fetched is kept, so a new run continues where this one stopped.", "Warmane Character Exporter", "YesNo", "Question")
            if ($answer -eq "Yes") { $script:cancelled = $true; try { $script:process.Kill() } catch { } } else { $e.Cancel = $true }
        }
    })
    $wait.Show()
    $wait.TopMost = $true
    $wait.TopMost = $false
    $wait.Activate()
    [void][Win32.Native]::SetForegroundWindow($wait.Handle)
    $env:WARMANE_PROGRESS = "1"
    $clock = [System.Diagnostics.Stopwatch]::StartNew()

    $script:process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput $logOut -RedirectStandardError $logErr -PassThru
    $process = $script:process
    $progressState.Process = $process
    $null = $process.Handle
    $stop.Enabled = $true
    $tick = 0
    $lastText = "Starting"
    while (-not $process.HasExited) {
        [System.Windows.Forms.Application]::DoEvents()
        if ($script:cancelled -or $progressState.Cancelled) { break }
        Start-Sleep -Milliseconds 100
        $tick++
        if ($tick % 3 -eq 0 -and (Test-Path $logOut)) {
            try {
                $lines = @(Get-Content $logOut -Tail 40 -Encoding UTF8 -ErrorAction Stop | Where-Object { $_ -like "PROGRESS|*" })
                if ($lines.Count -gt 0) {
                    $parts = $lines[-1].Split("|", 3)
                    $percentLabel.Text = $parts[1] + "%"
                    $lastText = $parts[2]
                }
            } catch { }
        }
        $seconds = [int]$clock.Elapsed.TotalSeconds
        $pos = [math]::Abs(([int][math]::Floor($tick / 3) % 10) - 5)
        $track = (0..5 | ForEach-Object { if ($_ -eq $pos) { "o" } else { "." } }) -join " "
        $status.Text = $lastText
        $elapsedLabel.Text = ("Working  {0}`r`nElapsed {1}:{2:00}. Requests start 1 second apart; rate limits increase spacing to 3, then 5 seconds. The window can be minimized or placed behind other windows." -f $track, [math]::Floor($seconds / 60), ($seconds % 60))
    }
    $process.WaitForExit()
    $code = $process.ExitCode
    if ($progressState.Cancelled) { $script:cancelled = $true }
    $stop.Enabled = $false
    $script:process = $null
    $wait.Close()
    return [int]$code
}

$python = Find-Python
if (-not $python) {
    $answer = "Yes"
    if (-not $InstallPython) {
        $answer = [System.Windows.Forms.MessageBox]::Show("Python 3.12 or newer was not found.`r`nDownload a portable copy (about 11 MB, from python.org) into this folder? Nothing is installed on the system.", "Warmane Character Exporter", "YesNo", "Question")
    }
    if ($answer -ne "Yes" -or -not (Install-Python)) { exit 1 }
    $python = Find-Python
    if (-not $python) { Show-Message "Python is still not available after the download." "Warmane Character Exporter" "Error"; exit 1 }
}

$script:RosterMode = $false
$script:restartLauncher = $false
if (-not $Link) {
    $Link = Read-Link
    # Exit outside the WinForms callback; exit from its event handler raises ExitException.
    if ($script:restartLauncher) {
        $launcher = Join-Path $root "Start-Report.vbs"
        Start-Process -FilePath "wscript.exe" -ArgumentList ('//nologo "{0}"' -f $launcher)
        exit 0
    }
    if (-not $script:RosterMode -and -not $Link) { exit 0 }
}
if (-not $script:RosterMode) {
    if ($Link -notmatch $pattern) {
        Show-Message "Not an armory character link: $Link" "Warmane Character Exporter" "Error"
        exit 2
    }
    $charName = $Matches[1]
    $charRealm = $Matches[2]

    if (-not $Output) {
        $dialog = New-Object System.Windows.Forms.SaveFileDialog
        $dialog.Title = "Where to save the report"
        $dialog.Filter = "HTML report (*.html)|*.html"
        $dialog.DefaultExt = "html"
        $dialog.AutoUpgradeEnabled = $false   # classic dialog: the modern one restores a remembered window size per program and could open collapsed
        $kind = if ($Quick) { "quick" } else { "pve" }
        $dialog.FileName = ("{0}-{1}-{2}.html" -f $charName.ToLower(), $charRealm.ToLower(), $kind)
        $startDir = Get-DownloadsFolder
        $dialog.InitialDirectory = $startDir
        $owner = New-Object System.Windows.Forms.Form
        $owner.FormBorderStyle = "None"
        $owner.TopMost = $true
        $owner.ShowInTaskbar = $false
        $owner.StartPosition = "CenterScreen"
        $owner.Opacity = 0
        $owner.Size = New-Object System.Drawing.Size(1, 1)
        $owner.Show()
        $owner.Activate()
        $pick = $dialog.ShowDialog($owner)
        $owner.Close()
        if ($pick -ne "OK") { exit 0 }
        $Output = $dialog.FileName
    }
}

$env:TEMP = Join-Path $root ".tools\tmp"
$env:TMP = $env:TEMP
$env:PYTHONPATH = Join-Path $root "src"
$env:PYTHONIOENCODING = "utf-8"
$code = 0
if ($script:RosterMode) {
    $namesText = ""
    while ($true) {
        $selection = Read-Roster $namesText
        if ($null -eq $selection) { exit 0 }
        $namesText = $selection.Names
        $namesPath = Join-Path $root (".tools\tmp\roster-names-{0}.txt" -f [guid]::NewGuid().ToString("N"))
        $utf8 = New-Object System.Text.UTF8Encoding -ArgumentList $false
        [System.IO.File]::WriteAllText($namesPath, $namesText, $utf8)
        $outputFolder = [System.IO.Path]::GetFullPath($selection.OutputFolder.Trim())
        $pathRoot = [System.IO.Path]::GetPathRoot($outputFolder)
        if ($outputFolder.Equals($pathRoot, [StringComparison]::OrdinalIgnoreCase)) {
            $outputFolder += "."
        } else {
            $outputFolder = $outputFolder.TrimEnd([char[]]@('\'))
        }
        $arguments = '-m warmane_exporter.roster --realm "{0}" --names-file "{1}" --output-dir "{2}"' -f `
            $selection.Realm, $namesPath, $outputFolder
        if ($selection.Refresh) { $arguments += " --refresh" }
        $nameCount = @($namesText -split '\r?\n' | Where-Object { $_.Trim() }).Count
        $windowTitle = "Creating raid roster reports ($nameCount characters, $($selection.Realm))"
        try {
            $code = Invoke-ProgressProcess $arguments $windowTitle -RosterMode
        } finally {
            if (Test-Path $namesPath) { Remove-Item -LiteralPath $namesPath -Force }
        }
        if ($script:cancelled) { exit 0 }

        $errorLines = @()
        if (Test-Path $logErr) { $errorLines = @(Get-Content $logErr -Encoding UTF8 | Where-Object { $_.Trim() }) }
        if ($code -eq 2) {
            $details = if ($errorLines.Count -gt 0) { $errorLines -join "`n" } else { "The roster input was not accepted." }
            Show-Message $details "Raid roster input errors" "Warning"
            continue
        }
        if ($code -eq 0 -or $code -eq 1) {
            $summaryLines = @(Get-Content $logOut -Encoding UTF8 | Where-Object { $_ -like "summary: *" })
            if ($summaryLines.Count -gt 0) {
                $summaryPath = $summaryLines[-1].Substring(9).Trim()
                if ($code -eq 1) {
                    $lastError = if ($errorLines.Count -gt 0) { $errorLines[-1] } else { "The run stopped early." }
                    Show-Message ("The roster run stopped early. {0}" -f $lastError) "Raid roster reports" "Warning"
                }
                if (-not $NoOpen) { Start-Process -FilePath $summaryPath }
                exit $code
            }
        }
        $tail = @()
        foreach ($file in $logOut, $logErr) {
            if (Test-Path $file) { $tail += Get-Content $file -Tail 12 -Encoding UTF8 }
        }
        Show-Message ("The roster reports could not be created (exit code {0}).`n`n{1}`n`nFull log: {2}" -f $code, ($tail -join "`n"), $logOut) "Raid roster reports" "Error"
        exit 1
    }
}

$arguments = '-m warmane_exporter.run "{0}" --html-output "{1}"' -f $Link, $Output
if ($Offline) { $arguments += " --offline" }
if ($Quick) { $arguments += " --quick" }
$code = Invoke-ProgressProcess $arguments "Creating the report for $charName ($charRealm)"
if ($script:cancelled) { exit 0 }

if ($code -eq 0 -and (Test-Path $Output)) {
    if (-not $NoOpen) { Start-Process -FilePath $Output }
    exit 0
}

$tail = @()
foreach ($file in $logOut, $logErr) {
    if (Test-Path $file) { $tail += Get-Content $file -Tail 12 -Encoding UTF8 }
}
Show-Message ("The report could not be created (exit code {0}).`n`n{1}`n`nFull log: {2}" -f $code, ($tail -join "`n"), $logOut) "Warmane Character Exporter" "Error"
exit 1
