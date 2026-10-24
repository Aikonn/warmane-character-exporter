<#
Mini launcher for the Warmane character exporter (Windows, PowerShell 5.1, no extra software).

Double-click Start-Report.cmd. It asks for an armory link, asks where to save the HTML report,
runs the exporter, then opens the report in the default browser.

For testing or scripting the prompts can be skipped:
  .\Start-Report.ps1 -Link https://armory.warmane.com/character/Aikka/Onyxia/summary -Output C:\temp\report.html [-Offline] [-NoOpen]
-Offline makes no requests and rebuilds from data already collected.
#>
param(
    [string]$Link,
    [string]$Output,
    [switch]$Offline,
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$root = $PSScriptRoot
Set-Location $root
$cache = Join-Path $root ".warmane-cache"
New-Item -ItemType Directory -Force -Path $cache, (Join-Path $root ".tools\tmp") | Out-Null
$logOut = Join-Path $cache "launcher.log"
$logErr = Join-Path $cache "launcher-error.log"
$lastDirFile = Join-Path $cache "launcher-last-dir.txt"
$pattern = 'armory\.warmane\.com/character/([^/\s?#"''<>]+)/([^/\s?#"''<>]+)'

function Show-Message([string]$text, [string]$title, [string]$icon = "Information") {
    [void][System.Windows.Forms.MessageBox]::Show($text, $title, "OK", $icon)
}

function Find-Python {
    $embedded = Join-Path $root ".tools\python312\python.exe"
    if (Test-Path $embedded) { return $embedded }
    foreach ($name in "python", "py") {
        $found = Get-Command $name -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    return $null
}

function Read-Link {
    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Warmane Character Exporter"
    $form.StartPosition = "CenterScreen"
    $form.FormBorderStyle = "FixedDialog"
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.ClientSize = New-Object System.Drawing.Size(520, 130)
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
    $ok = New-Object System.Windows.Forms.Button
    $ok.Text = "Create report"
    $ok.Size = New-Object System.Drawing.Size(110, 28)
    $ok.Location = New-Object System.Drawing.Point(288, 92)
    $ok.DialogResult = "OK"
    $cancel = New-Object System.Windows.Forms.Button
    $cancel.Text = "Cancel"
    $cancel.Size = New-Object System.Drawing.Size(100, 28)
    $cancel.Location = New-Object System.Drawing.Point(408, 92)
    $cancel.DialogResult = "Cancel"
    $form.AcceptButton = $ok
    $form.CancelButton = $cancel
    $form.Controls.AddRange(@($label, $box, $hint, $ok, $cancel))
    while ($true) {
        if ($form.ShowDialog() -ne "OK") { return $null }
        if ($box.Text -match $pattern) { return $box.Text.Trim() }
        Show-Message "That does not look like a Warmane armory character link." "Warmane Character Exporter" "Warning"
    }
}

$python = Find-Python
if (-not $python) {
    Show-Message "Python was not found. Expected .tools\python312\python.exe in the project folder." "Warmane Character Exporter" "Error"
    exit 1
}

if (-not $Link) {
    $Link = Read-Link
    if (-not $Link) { exit 0 }
}
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
    $dialog.FileName = ("{0}-{1}-pve.html" -f $charName.ToLower(), $charRealm.ToLower())
    $startDir = [Environment]::GetFolderPath("MyDocuments")
    if (Test-Path $lastDirFile) {
        $saved = (Get-Content $lastDirFile -Raw).Trim()
        if ($saved -and (Test-Path $saved)) { $startDir = $saved }
    }
    $dialog.InitialDirectory = $startDir
    if ($dialog.ShowDialog() -ne "OK") { exit 0 }
    $Output = $dialog.FileName
    Set-Content -Path $lastDirFile -Value (Split-Path -Parent $Output) -Encoding ASCII
}

$env:TEMP = Join-Path $root ".tools\tmp"
$env:TMP = $env:TEMP
$env:PYTHONPATH = Join-Path $root "src"
$env:PYTHONIOENCODING = "utf-8"
$arguments = '-m warmane_exporter.run "{0}" --html-output "{1}"' -f $Link, $Output
if ($Offline) { $arguments += " --offline" }

$script:cancelled = $false
$wait = New-Object System.Windows.Forms.Form
$wait.Text = "Warmane Character Exporter"
$wait.StartPosition = "CenterScreen"
$wait.FormBorderStyle = "FixedDialog"
$wait.MaximizeBox = $false
$wait.ClientSize = New-Object System.Drawing.Size(520, 150)
$title = New-Object System.Windows.Forms.Label
$title.Text = "Creating the report for $charName ($charRealm)"
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
$status.Size = New-Object System.Drawing.Size(368, 40)
$elapsedLabel = New-Object System.Windows.Forms.Label
$elapsedLabel.Text = "Elapsed 0:00"
$elapsedLabel.ForeColor = [System.Drawing.Color]::Gray
$elapsedLabel.Location = New-Object System.Drawing.Point(12, 100)
$elapsedLabel.Size = New-Object System.Drawing.Size(496, 40)
$wait.Controls.AddRange(@($title, $percentLabel, $status, $elapsedLabel))
$wait.Add_FormClosing({
    param($sender, $e)
    if ($script:process -and -not $script:process.HasExited) {
        $answer = [System.Windows.Forms.MessageBox]::Show("Stop the export? Data already fetched is kept, so a new run continues where this one stopped.", "Warmane Character Exporter", "YesNo", "Question")
        if ($answer -eq "Yes") { $script:cancelled = $true; try { $script:process.Kill() } catch { } } else { $e.Cancel = $true }
    }
})
$wait.Show()
$env:WARMANE_PROGRESS = "1"
$clock = [System.Diagnostics.Stopwatch]::StartNew()

$script:process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput $logOut -RedirectStandardError $logErr -PassThru
$process = $script:process
$null = $process.Handle   # keeps the exit code readable after the process ends
$tick = 0
$lastText = "Starting"
while (-not $process.HasExited) {
    [System.Windows.Forms.Application]::DoEvents()
    if ($script:cancelled) { break }
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
    $pos = [math]::Abs((($tick / 3) % 10) - 5)   # 0..5..1, moves left and right
    $track = (0..5 | ForEach-Object { if ($_ -eq $pos) { "o" } else { "." } }) -join " "
    $status.Text = $lastText
    $elapsedLabel.Text = ("Working  {0}`r`nElapsed {1}:{2:00}. Requests to Warmane are spaced 1 second apart, so this takes a while. The window can be minimized or placed behind other windows." -f $track, [math]::Floor($seconds / 60), ($seconds % 60))
}
$process.WaitForExit()
$code = $process.ExitCode
$script:process = $null
$wait.Close()
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
