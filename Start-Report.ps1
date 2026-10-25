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
    [switch]$NoOpen,
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
        $form.TopMost = $true      # appears in front once; the user can still put other windows over it
        $form.Add_Shown({ $form.Activate(); $form.TopMost = $false })
        if ($form.ShowDialog() -ne "OK") { return $null }
        if ($box.Text -match $pattern) { return $box.Text.Trim() }
        Show-Message "That does not look like a Warmane armory character link." "Warmane Character Exporter" "Warning"
    }
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
    $dialog.AutoUpgradeEnabled = $false   # classic dialog: the modern one restores a remembered window size per program and could open collapsed
    $dialog.FileName = ("{0}-{1}-pve.html" -f $charName.ToLower(), $charRealm.ToLower())
    $startDir = Get-DownloadsFolder
    $dialog.InitialDirectory = $startDir
    # Owner window: makes sure the dialog appears in front even though this script runs hidden and may not own the foreground.
    $owner = New-Object System.Windows.Forms.Form
    $owner.FormBorderStyle = "None"      # no caption, so nothing visible is left of this helper window
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
$wait.ClientSize = New-Object System.Drawing.Size(520, 175)
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
$elapsedLabel.Size = New-Object System.Drawing.Size(496, 65)
$wait.Controls.AddRange(@($title, $percentLabel, $status, $elapsedLabel))
$wait.Add_FormClosing({
    param($sender, $e)
    if ($script:process -and -not $script:process.HasExited) {
        $answer = [System.Windows.Forms.MessageBox]::Show("Stop the export? Data already fetched is kept, so a new run continues where this one stopped.", "Warmane Character Exporter", "YesNo", "Question")
        if ($answer -eq "Yes") { $script:cancelled = $true; try { $script:process.Kill() } catch { } } else { $e.Cancel = $true }
    }
})
Add-Type -Namespace Win32 -Name Native -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr hWnd);'
$wait.Show()
# come to the front once (not permanently on top): the topmost flag is set and cleared again right away
$wait.TopMost = $true
$wait.TopMost = $false
$wait.Activate()
[void][Win32.Native]::SetForegroundWindow($wait.Handle)
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
    $pos = [math]::Abs(([int][math]::Floor($tick / 3) % 10) - 5)   # 0..5..1, moves left and right
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
