@echo off
REM Registers the LLMMonitor scheduled task (see install-service.ps1).
REM Runs at each logon of the current user; the logon task needs no administrator rights.
REM With -WithBoot it also registers the boot task, which needs an elevated native shell.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-service.ps1" %*
exit /b %ERRORLEVEL%
