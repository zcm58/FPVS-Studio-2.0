@echo off
setlocal DisableDelayedExpansion

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0scripts\setup_windows.ps1"
exit /b %ERRORLEVEL%
