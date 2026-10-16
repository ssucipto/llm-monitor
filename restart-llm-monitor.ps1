# Restart the LLM monitor dashboard (llm-monitor\server.py) without touching anything else.
#
# Stops ONLY the process listening on this dashboard's port, and only if that process is
# running server.py. Never kills by process name: the local LLM gateway (:8080) and Strata
# (:8081) are also Python processes and must survive a dashboard restart.
#
#   powershell -File restart-llm-monitor.ps1            # port 8090 (default)
#   powershell -File restart-llm-monitor.ps1 -Port 8091

param(
    [int]$Port = 8090
)

$ErrorActionPreference = "Stop"

$dir    = Join-Path $PSScriptRoot "llm-monitor"
$server = Join-Path $dir "server.py"
$logDir = Join-Path $env:LOCALAPPDATA "LLMMonitor"

if (-not (Test-Path $server)) { throw "server.py not found at $server" }
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }

# 1. Stop whatever owns the dashboard port, but only if it is our server.py.
$owners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique)

foreach ($owner in $owners) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$owner" -ErrorAction SilentlyContinue
    if (-not $proc) { continue }
    # Match the full path, not just "server.py": other dashboards on this PC also run a server.py.
    if ($proc.CommandLine -notmatch [regex]::Escape($server)) {
        throw "Port $Port is owned by PID $owner ($($proc.Name)), which is not $server. Not stopping it."
    }
    Write-Host "Stopping dashboard PID $owner on :$Port"
    Stop-Process -Id $owner -Force
}

if ($owners.Count -gt 0) {
    # Wait for the port to free up before starting again.
    $deadline = (Get-Date).AddSeconds(15)
    while ((Get-Date) -lt $deadline -and (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) {
        Start-Sleep -Milliseconds 500
    }
}

# 2. Start it again, detached, with the same logging as llm-monitor-start.bat.
$python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py.exe -ErrorAction SilentlyContinue).Source }
if (-not $python) { throw "No python interpreter found on PATH." }

Start-Process -FilePath $python `
    -ArgumentList @($server, "$Port") `
    -WorkingDirectory $dir `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir "service.out.log") `
    -RedirectStandardError  (Join-Path $logDir "service.err.log")

Start-Sleep -Seconds 3
try {
    Invoke-RestMethod "http://127.0.0.1:$Port/" -TimeoutSec 5 | Out-Null
    Write-Host "Dashboard up on http://localhost:$Port"
} catch {
    Write-Warning "Dashboard did not answer on :$Port yet. See $logDir\service.err.log"
}
