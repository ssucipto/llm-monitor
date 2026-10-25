# restart-llm-monitor.ps1 - restart the LLM monitor dashboard (milestones 76, 77; audit-27).
# 1. For the task port (8090): stops the LLMMonitor and LLMMonitorBoot scheduled tasks. A task that
#    cannot be stopped is reported, not hidden.
# 2. Stops any supervisor still running for the port, and then any server still owning the port, each
#    by PID and only after its command line names this dashboard's script (full path). Never by name.
# 3. Starts the LLMMonitor task again (task port), or a supervisor for any other port, and waits for
#    /api/stats to answer. Every action is logged to %LOCALAPPDATA%\LLMMonitor\service-<port>.log.
#   powershell -NoProfile -ExecutionPolicy Bypass -File restart-llm-monitor.ps1 [-Port 8090]

param(
    [int]$Port = 8090,
    [string]$TaskName = "LLMMonitor",
    [string]$BootTaskName = "LLMMonitorBoot"
)

$ErrorActionPreference = "Stop"

$server     = Join-Path $PSScriptRoot "llm-monitor\server.py"
$supervisor = Join-Path $PSScriptRoot "llm-monitor\service-supervisor.ps1"
foreach ($f in @($server, $supervisor)) { if (-not (Test-Path $f)) { throw "not found: $f" } }
$logDir    = Join-Path $env:LOCALAPPDATA "LLMMonitor"
$svcLog    = Join-Path $logDir "service-$Port.log"
$stateFile = Join-Path $logDir "service-$Port.state.json"
$stopFile  = Join-Path $logDir "stop-$Port.request"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }

function Write-RestartLog([string]$msg) {
    # Same file and format as the supervisor, so a stop from outside is never silent (audit-27 a27-06).
    Write-Host $msg
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    for ($try = 1; $try -le 5; $try++) {
        try { Add-Content -Path $svcLog -Value "[$stamp] restart: $msg" -Encoding ascii -ErrorAction Stop; return }
        catch { Start-Sleep -Milliseconds 200 }
    }
}

function Get-TaskPort($task) {
    # The task action passes -Port only when it is not the default 8090.
    if ($task.Actions[0].Arguments -match '-Port\s+(\d+)') { return [int]$matches[1] }
    return 8090
}

function Test-StateAttest([int]$ownerPid) {
    # A session-0 chain (boot task, S4U) hides its command lines from the desktop. A fresh state file
    # written by our supervisor, naming this PID as its server, attests it instead.
    try { $s = Get-Content -LiteralPath $stateFile -Raw -ErrorAction Stop | ConvertFrom-Json } catch { return $false }
    if ($s.server_pid -ne $ownerPid) { return $false }
    return (((Get-Date) - [datetime]$s.heartbeat).TotalSeconds -le 30)
}

function Get-OurOwner {
    # Returns the PIDs listening on the port. Throws if any owner is not our server.py.
    $owners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
    $ours = @()
    foreach ($o in $owners) {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId=$o" -ErrorAction SilentlyContinue
        if ($p -and $p.CommandLine -match [regex]::Escape($server)) {
            $ours += $o
        } elseif ($p -and -not $p.CommandLine -and (Test-StateAttest $o)) {
            $script:crossSession = $true
            $ours += $o
        } else {
            $name = if ($p) { $p.Name } else { "unknown" }
            throw "Port $Port is owned by PID $o ($name), which is not our server.py. Not stopping it."
        }
    }
    return ,$ours
}

function Get-OurSupervisor {
    # PIDs of powershell processes running this repo's service-supervisor.ps1 for this port.
    $found = @()
    $procs = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue)
    foreach ($p in $procs) {
        if ($p.ProcessId -eq $PID) { continue }
        if ($p.CommandLine -notmatch [regex]::Escape($supervisor)) { continue }
        $pp = if ($p.CommandLine -match '-Port\s+(\d+)') { [int]$matches[1] } else { 8090 }
        if ($pp -eq $Port) { $found += $p.ProcessId }
    }
    return ,$found
}

function Wait-PortFree([int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        if ((Get-OurOwner).Count -eq 0) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return ((Get-OurOwner).Count -eq 0)
}

Write-RestartLog "restart requested (pid $PID, port $Port)"

# Refuse before touching anything when a foreign process owns the port.
$script:crossSession = $false
try { $null = Get-OurOwner } catch { Write-RestartLog "REFUSED $($_.Exception.Message)"; throw }

# 0. Ask every supervisor of this port to stop its own server. This is the only stop that works for a
#    session-0 (boot task) chain, which the desktop may not terminate; it is also the graceful path.
Set-Content -LiteralPath $stopFile -Value "requested by restart-llm-monitor.ps1 pid $PID at $(Get-Date -Format o)" -Encoding ascii
Write-RestartLog "stop request written ($stopFile)"
$graceful = (Get-Date).AddSeconds(10)
while ((Get-Date) -lt $graceful -and @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).Count -gt 0) {
    Start-Sleep -Milliseconds 500
}

# 1. Tasks that serve this port.
$tasks = @()
foreach ($name in @($TaskName, $BootTaskName)) {
    $t = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($t -and (Get-TaskPort $t) -eq $Port) { $tasks += $t }
}
foreach ($t in $tasks) {
    if ($t.State -ne 'Running') { continue }
    try {
        Stop-ScheduledTask -TaskName $t.TaskName -ErrorAction Stop
        Write-RestartLog "stopped task $($t.TaskName)"
    } catch {
        Write-RestartLog "WARN could not stop task $($t.TaskName): $($_.Exception.Message.Split([Environment]::NewLine)[0]); stopping its supervisor by PID instead"
    }
}

# 2. Supervisors first (so none restarts the server), then servers. PID only, command line checked.
foreach ($s in (Get-OurSupervisor)) {
    Write-RestartLog "stopping supervisor PID $s (service-supervisor.ps1, port $Port)"
    Stop-Process -Id $s -Force
}
foreach ($o in (Get-OurOwner)) {
    Write-RestartLog "stopping our server PID $o on :$Port"
    try { Stop-Process -Id $o -Force -ErrorAction Stop }
    catch { Write-RestartLog "WARN could not stop PID ${o}: $($_.Exception.Message)" }
}

if (-not (Wait-PortFree 15)) {
    $holder = (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
    Write-RestartLog "FAIL port $Port still busy 15 s after stopping owners (PID $holder)"
    Remove-Item -LiteralPath $stopFile -Force -ErrorAction SilentlyContinue
    throw "port $Port still busy (PID $holder). If it runs in session 0 with no supervisor, stop it from an elevated shell: Stop-Process -Id $holder"
}
Remove-Item -LiteralPath $stopFile -Force -ErrorAction SilentlyContinue

# 3. Start again: the logon task for its port, otherwise a supervisor of our own.
$startTask = $tasks | Where-Object { $_.TaskName -eq $TaskName } | Select-Object -First 1
if ($startTask) {
    Start-ScheduledTask -TaskName $TaskName
    Write-RestartLog "started task $TaskName"
} else {
    Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$supervisor`"", '-Port', "$Port") | Out-Null
    Write-RestartLog "no task serves port $Port; started service-supervisor.ps1 -Port $Port directly"
}

$ok = $false
$deadline = (Get-Date).AddSeconds(25)
while ((Get-Date) -lt $deadline -and -not $ok) {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:$Port/api/stats" -TimeoutSec 3
        $ok = ($r.StatusCode -eq 200)
    } catch {
        Start-Sleep -Seconds 1
    }
}

if ($ok) {
    Write-RestartLog "Dashboard up on http://localhost:$Port"
} else {
    Write-RestartLog "WARN dashboard not answering after 25 s"
    Write-Warning "Dashboard not answering yet. See $svcLog and $(Join-Path $logDir "service-$Port.err.log")"
}
