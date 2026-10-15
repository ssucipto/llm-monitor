@echo off
REM ===========================================================================
REM  LLM Monitor service installer
REM  Registers TWO per-user scheduled tasks that run the monitor launcher:
REM    * LLMMonitorBoot - at every system startup (boot / restart)
REM    * LLMMonitor     - at every interactive sign-in (logon)
REM  Together they cover "run when computer starts" and "when I log in".
REM  No administrator privileges are required. Idempotent: removes any existing
REM  task of the same name before re-creating it, so re-running does not stack up.
REM  Run this once from a normal Windows shell (cmd /c, PowerShell, or double-click).
REM ===========================================================================

setlocal
set "STARTBAT=%~dp0llm-monitor-start.bat"

if not exist "%STARTBAT%" (
    echo [error] launcher llm-monitor-start.bat not found beside this script.
    exit /b 1
)

call :register LLMMonitorBoot ONSTART
if errorlevel 1 exit /b 1
call :register LLMMonitor ONLOGON
if errorlevel 1 exit /b 1

echo Registered scheduled tasks:
echo   LLMMonitorBoot -^> runs llm-monitor-start.bat at every system startup (boot/restart).
echo   LLMMonitor     -^> runs llm-monitor-start.bat at every interactive sign-in.
echo Open the dashboard at http://localhost:8090 after boot or login.
echo To stop: schtasks /delete /tn "LLMMonitorBoot" /f  and  schtasks /delete /tn "LLMMonitor" /f
endlocal
exit /b 0

:register
REM %1 = task name, %2 = schedule (ONSTART | ONLOGON)
schtasks /query /tn "%~1" >nul 2>&1 && (
    schtasks /delete /tn "%~1" /f
)
schtasks /create /tn "%~1" /tr "%STARTBAT%" /sc %~2 /f
if errorlevel 1 (
    echo [error] failed to register scheduled task "%~1".
    exit /b 1
)
exit /b 0
