@echo off
rem Double-click launcher: asks for an armory link and a save location, then opens the report in the browser.
rem The script starts in its own hidden process so this console window closes at once.
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0Start-Report.ps1" %*
exit /b
