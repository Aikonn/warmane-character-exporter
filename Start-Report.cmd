@echo off
rem Double-click launcher: asks for an armory link and a save location, then opens the report in the browser.
rem Start-Report.vbs runs the script with no console window; this window closes at once.
start "" wscript.exe //nologo "%~dp0Start-Report.vbs" %*
exit /b
