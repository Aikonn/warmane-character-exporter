@echo off
rem Double-click launcher: asks for an armory link and a save location, then opens the report in the browser.
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0Start-Report.ps1" %*
