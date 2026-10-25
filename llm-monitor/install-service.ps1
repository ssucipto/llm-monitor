# install-service.ps1 - registers the LLMMonitor scheduled task.
# The task runs service-supervisor.ps1 at each logon of the current user.
#   powershell -NoProfile -ExecutionPolicy Bypass -File install-service.ps1
# Safe to run again: it replaces the task. The logon task needs no administrator rights. The -WithBoot (boot) task needs an elevated native shell (see the note below).
# -WithBoot adds LLMMonitorBoot (runs at system startup, S4U: no password). Decided as option B on 2026-10-16 (task T6).

param(
    [switch]$WithBoot
)

$ErrorActionPreference = "Stop"

$supervisor = Join-Path $PSScriptRoot "service-supervisor.ps1"
if (-not (Test-Path $supervisor)) { throw "missing $supervisor" }

$user = "$env:USERDOMAIN\$env:USERNAME"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$supervisor`""

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

$logon = New-ScheduledTaskTrigger -AtLogOn -User $user

# Remove the old tasks first. The old LLMMonitorBoot ran llm-monitor-start.bat and never fired before sign-in.
# Do NOT mask failures: if unregister is denied (the task sits in the protected admin store), continuing
# would leave the OLD task (old action, PT72H limit) in place and fail misleadingly at Register.
$denied = @()
foreach ($old in @("LLMMonitorBoot", "LLMMonitor")) {
    if (Get-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue) {
        try {
            Unregister-ScheduledTask -TaskName $old -Confirm:$false
        } catch {
            $denied += $old
        }
    }
}
if ($denied.Count -gt 0) {
    Write-Host "Cannot replace $(($denied) -join ', '): Access is denied from this shell."
    Write-Host "Re-run this script from a normal desktop PowerShell window (or right-click 'Run as administrator')"
    Write-Host "so the old tasks can be unregistered first. Aborting without registering a duplicate."
    exit 1
}

Register-ScheduledTask -TaskName "LLMMonitor" -Action $action -Trigger $logon `
    -Settings $settings -Principal $principal | Out-Null
Write-Host "Registered LLMMonitor: runs service-supervisor.ps1 at logon."

if ($WithBoot) {
    # Option B (decided 2026-10-16): run at system startup, no password stored (S4U).
    # Caveat (audit-25 F3): -AtStartup registration is denied from restricted shells, and the
    # reboot test has never run. Needs an elevated native shell; behaviour on reboot is UNVERIFIED.
    Write-Host "Note: -WithBoot needs an elevated native shell; boot behaviour is not yet reboot-tested."
    $bootPrincipal = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel Limited
    $boot = New-ScheduledTaskTrigger -AtStartup
    Register-ScheduledTask -TaskName "LLMMonitorBoot" -Action $action -Trigger $boot `
        -Settings $settings -Principal $bootPrincipal | Out-Null
    Write-Host "Registered LLMMonitorBoot: runs service-supervisor.ps1 at system startup (S4U)."
}
Write-Host "Start now with: Start-ScheduledTask -TaskName LLMMonitor"
Write-Host "Stop with:      Stop-ScheduledTask -TaskName LLMMonitor   (then Disable-ScheduledTask to keep it off)"
