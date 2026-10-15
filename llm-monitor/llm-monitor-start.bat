@echo off
REM ===========================================================================
REM  LLM Monitor service launcher
REM  Starts the local LLM monitor dashboard (server.py) on port 8090 as a
REM  detached process, so the scheduled task that invokes this returns
REM  immediately. This launcher lives beside server.py, so %~dp0 is the
REM  dashboard dir. server.py also resolves its own DB and static root from
REM  __file__, so it can be launched from any directory. Logs go to
REM  %LOCALAPPDATA%\LLMMonitor.
REM ===========================================================================

setlocal
set "MONITOR_DIR=%~dp0"
set "LOGDIR=%LOCALAPPDATA%\LLMMonitor"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo ===== [%date% %time%] starting LLM monitor =====>> "%LOGDIR%\service.log"

REM Launch detached: PowerShell resolves the interpreter itself (python.exe must be
REM a real Win32 path, not a shell alias), spawns the server, and redirects stdout/stderr.
powershell -NoLogo -Command ^
  "$d='%MONITOR_DIR%'; $log='%LOGDIR%'; if(!(Test-Path $log)){New-Item -ItemType Directory -Force -Path $log|Out-Null}; $p=(Get-Command python.exe -ErrorAction SilentlyContinue).Source; if(-not $p){$p=(Get-Command py.exe -ErrorAction SilentlyContinue).Source}; if(-not $p){Write-Host 'no python interpreter found'; exit 1}; Start-Process -FilePath $p -ArgumentList '$d\server.py','8090' -WorkingDirectory $d -RedirectStandardOutput '$log\service.out.log' -RedirectStandardError '$log\service.err.log'"

endlocal
exit /b 0
