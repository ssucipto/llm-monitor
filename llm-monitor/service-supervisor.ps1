# service-supervisor.ps1 - LLM monitor service supervisor (the action of the LLMMonitor scheduled tasks).
# Starts server.py in the foreground, restarts it with backoff when it exits, and logs every start and
# exit with a timestamp to service-<port>.log. Never stops a process by name. Exits quietly when our
# server already serves the port under a live supervisor; takes over an orphaned server of ours.
#   powershell -NoProfile -ExecutionPolicy Bypass -File service-supervisor.ps1 [-Port 8090]
#
# Cross-session control (audit-27). The boot task runs this script in session 0 (S4U), where the
# desktop user can neither read the command lines nor stop the processes. So:
# - The wrapper and server run in a kill-on-close job owned by this script: when the supervisor ends,
#   however it ends, Windows stops its server too. No orphans.
# - service-<port>.state.json records the supervisor, wrapper and server PIDs with a heartbeat, so
#   tools that cannot read the command lines can still attest the chain.
# - A stop-<port>.request file newer than this supervisor's start makes it stop its own server and
#   exit (restart-llm-monitor.ps1 writes it).

param(
    [int]$Port = 8090
)

$ErrorActionPreference = "Stop"

$dir         = $PSScriptRoot
$server      = Join-Path $dir "server.py"
$logDir      = Join-Path $env:LOCALAPPDATA "LLMMonitor"
$svcLog      = Join-Path $logDir ("service-$Port.log")
$runCmd      = Join-Path $logDir ("run-server-$Port.cmd")
$stateFile   = Join-Path $logDir ("service-$Port.state.json")
$stopFile    = Join-Path $logDir ("stop-$Port.request")
$ownLogs     = @((Join-Path $logDir "service-$Port.out.log"), (Join-Path $logDir "service-$Port.err.log"))
$maxLogBytes = 5MB
$stateMaxAge = 30   # seconds; a heartbeat older than this is stale
$supStart    = Get-Date

if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class LlmMonitorJob {
    [StructLayout(LayoutKind.Sequential)]
    struct BasicLimit { public long PerProcessUserTimeLimit; public long PerJobUserTimeLimit; public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize; public UIntPtr MaximumWorkingSetSize; public uint ActiveProcessLimit;
        public UIntPtr Affinity; public uint PriorityClass; public uint SchedulingClass; }
    [StructLayout(LayoutKind.Sequential)]
    struct IoCounters { public ulong R, W, O, RB, WB, OB; }
    [StructLayout(LayoutKind.Sequential)]
    struct ExtendedLimit { public BasicLimit Basic; public IoCounters Io; public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit; public UIntPtr PeakProcessMemoryUsed; public UIntPtr PeakJobMemoryUsed; }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateJobObject(IntPtr attributes, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref ExtendedLimit info, uint size);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool IsProcessInJob(IntPtr process, IntPtr job, out bool result);
    static IntPtr job = IntPtr.Zero;
    public static void Create() {
        job = CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero) throw new System.ComponentModel.Win32Exception();
        ExtendedLimit info = new ExtendedLimit();
        info.Basic.LimitFlags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if (!SetInformationJobObject(job, 9, ref info, (uint)Marshal.SizeOf(typeof(ExtendedLimit))))
            throw new System.ComponentModel.Win32Exception();
    }
    public static void Assign(IntPtr process) {
        bool inJob;
        if (IsProcessInJob(process, job, out inJob) && inJob) return;
        if (!AssignProcessToJobObject(job, process)) throw new System.ComponentModel.Win32Exception();
    }
}
"@

function Write-Lifecycle([string]$msg) {
    # Logging must never end the supervisor: another writer (a second supervisor, the restart script)
    # can hold the file for a moment, so retry briefly and then drop the line.
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    for ($try = 1; $try -le 5; $try++) {
        try { Add-Content -Path $svcLog -Value "[$stamp] supervisor: $msg" -Encoding ascii -ErrorAction Stop; return }
        catch { Start-Sleep -Milliseconds 200 }
    }
}

function Read-State {
    try { return (Get-Content -LiteralPath $stateFile -Raw -ErrorAction Stop | ConvertFrom-Json) } catch { return $null }
}

function Write-State($wrapperPid, $serverPid, $serverStarted) {
    $state = [ordered]@{
        port               = $Port
        supervisor_pid     = $PID
        supervisor_session = (Get-Process -Id $PID).SessionId
        supervisor_started = $supStart.ToString("o")
        wrapper_pid        = $wrapperPid
        server_pid         = $serverPid
        server_started     = $serverStarted
        heartbeat          = (Get-Date).ToString("o")
    }
    try { $state | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding ascii -ErrorAction Stop } catch { $null = $_ }
}

function Clear-OwnState {
    # Only the supervisor named in the state file removes it; a duplicate that exits leaves it alone.
    $s = Read-State
    if ($s -and $s.supervisor_pid -eq $PID) { Remove-Item -LiteralPath $stateFile -Force -ErrorAction SilentlyContinue }
}

function Close-Supervisor([int]$code, [string]$reason) {
    # Every deliberate exit logs its end, so an exit never leaves the log silent (review-012 F3).
    Clear-OwnState
    Write-Lifecycle "supervisor end ($reason, exit $code)"
    exit $code
}

function Test-StateAttest([int]$ownerPid) {
    # True when a fresh state file names this PID as the server. Used only when the owner's command
    # line cannot be read (a session-0 chain seen from the desktop).
    $s = Read-State
    if (-not $s -or $s.server_pid -ne $ownerPid) { return $false }
    $age = ((Get-Date) - [datetime]$s.heartbeat).TotalSeconds
    if ($age -gt $stateMaxAge) { return $false }
    $sup = Get-CimInstance Win32_Process -Filter "ProcessId=$($s.supervisor_pid)" -ErrorAction SilentlyContinue
    return [bool]($sup -and $sup.Name -match '^powershell')
}

function Get-PortState {
    # "free"   = nothing listens on the port
    # "ours"   = every owner runs this server.py under a live supervisor (or, when its command line
    #            cannot be read, a fresh state file attests it)
    # "orphan" = every owner runs this server.py, but at least one has no live supervisor above it
    #            ($script:orphans holds those PIDs)
    # "other"  = anything else. Never touched.
    $script:orphans = @()
    $owners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
    if ($owners.Count -eq 0) { return "free" }
    foreach ($owner in $owners) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$owner" -ErrorAction SilentlyContinue
        if ($proc -and -not $proc.CommandLine -and (Test-StateAttest $owner)) { continue }
        if (-not $proc -or $proc.CommandLine -notmatch [regex]::Escape($server)) { return "other" }
        if (-not (Test-Supervised $proc)) { $script:orphans += $owner }
    }
    if ($script:orphans.Count -gt 0) { return "orphan" }
    return "ours"
}

function Test-Supervised($proc) {
    # True when the server's parent is our run-server-<port>.cmd wrapper and the wrapper's parent is a
    # live powershell running this supervisor script.
    $wrap = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)" -ErrorAction SilentlyContinue
    if (-not $wrap -or $wrap.CommandLine -notmatch [regex]::Escape((Split-Path $runCmd -Leaf))) { return $false }
    $sup = Get-CimInstance Win32_Process -Filter "ProcessId=$($wrap.ParentProcessId)" -ErrorAction SilentlyContinue
    return [bool]($sup -and $sup.Name -match '^powershell' -and
        $sup.CommandLine -match [regex]::Escape((Split-Path $PSCommandPath -Leaf)))
}

function Invoke-OrphanStop {
    # Stops each orphaned server of ours by PID, re-checking its command line first (never by name).
    foreach ($o in $script:orphans) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$o" -ErrorAction SilentlyContinue
        if ($proc -and $proc.CommandLine -match [regex]::Escape($server)) {
            Write-Lifecycle "orphan server pid $o has no live supervisor; stopping it by PID and taking over"
            Stop-Process -Id $o -Force
        }
    }
    $deadline = (Get-Date).AddSeconds(15)
    while ((Get-Date) -lt $deadline) {
        if ((Get-PortState) -eq "free") { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Test-StopRequested {
    # A request counts only when it was written after this supervisor started.
    if (-not (Test-Path -LiteralPath $stopFile)) { return $false }
    return ((Get-Item -LiteralPath $stopFile).LastWriteTime -gt $supStart)
}

function Get-Python {
    $p = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if (-not $p) { $p = (Get-Command py.exe -ErrorAction SilentlyContinue).Source }
    return $p
}

function Invoke-RotateLog([string]$path) {
    # Keep one previous generation. Rename, never truncate, so an older traceback survives.
    if ((Test-Path $path) -and ((Get-Item $path).Length -gt $maxLogBytes)) {
        Move-Item -Path $path -Destination "$path.1" -Force
        Write-Lifecycle ("rotated " + (Split-Path $path -Leaf) + " (over $maxLogBytes bytes)")
    }
}

function Write-RunCmd([string]$python) {
    # A .cmd file avoids quoting problems. The redirects append stdout and stderr across restarts.
    $out = Join-Path $logDir "service-$Port.out.log"
    $err = Join-Path $logDir "service-$Port.err.log"
    $content = "@echo off`r`n" +
        "`"$python`" `"$server`" $Port >> `"$out`" 2>> `"$err`"`r`n" +
        "exit /b %ERRORLEVEL%`r`n"
    Set-Content -Path $runCmd -Value $content -Encoding ascii
}

function Get-ServerChild([int]$wrapperPid) {
    # The python child of the wrapper, once it has started (same session, so its command line is readable).
    $deadline = (Get-Date).AddSeconds(10)
    while ((Get-Date) -lt $deadline) {
        $c = Get-CimInstance Win32_Process -Filter "ParentProcessId=$wrapperPid" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match [regex]::Escape($server) } | Select-Object -First 1
        if ($c) { return $c }
        if (-not (Get-Process -Id $wrapperPid -ErrorAction SilentlyContinue)) { return $null }
        Start-Sleep -Milliseconds 200
    }
    return $null
}

function Invoke-OwnServerStop([string]$why) {
    # Stops this supervisor's own wrapper and server by PID (children in its job), then ends.
    $s = Read-State
    if ($s -and $s.supervisor_pid -eq $PID) {
        $targets = @(@($s.server_pid, [regex]::Escape($server)), @($s.wrapper_pid, [regex]::Escape((Split-Path $runCmd -Leaf))))
        foreach ($t in $targets) {
            $p = if ($t[0]) { Get-CimInstance Win32_Process -Filter "ProcessId=$($t[0])" -ErrorAction SilentlyContinue } else { $null }
            if ($p -and $p.CommandLine -match $t[1]) { Stop-Process -Id $t[0] -Force -ErrorAction SilentlyContinue }
        }
    }
    Close-Supervisor 0 $why
}

# ---- main -------------------------------------------------------------------

# Terminating errors also leave a trace in the log.
trap {
    Clear-OwnState
    Write-Lifecycle "supervisor end (terminating error: $($_.Exception.Message))"
    break
}

$python = Get-Python
if (-not $python) {
    Write-Lifecycle "FAIL: no python.exe or py.exe on PATH"
    Close-Supervisor 1 "no python"
}

$session = (Get-Process -Id $PID).SessionId
Write-Lifecycle "supervisor start (pid $PID, port $Port, session $session, python $python)"
[LlmMonitorJob]::Create()

$backoff = 5
while ($true) {
    $state = Get-PortState
    if ($state -eq "ours") {
        Write-Lifecycle "port $Port is already served by our server.py; this supervisor exits"
        Close-Supervisor 0 "already served"
    }
    if ($state -eq "orphan" -and -not (Invoke-OrphanStop)) {
        Write-Lifecycle "FAIL: port $Port still held 15 s after stopping the orphan; not starting"
        Close-Supervisor 1 "orphan would not stop"
    }
    if ($state -eq "other") {
        Write-Lifecycle "FAIL: port $Port is held by another process; not starting and not touching it"
        Close-Supervisor 1 "other owner"
    }

    # Per-port log files (service-<port>.*). The old launcher that held the shared files is gone
    # (task replacement verified 2026-10-17), so no busy-file check is needed.
    Invoke-RotateLog $svcLog
    foreach ($p in $ownLogs) { Invoke-RotateLog $p }

    # Write the run file only now: a supervisor that exits above must not rewrite the batch file that a
    # live cmd.exe is executing (cmd reads batch files by offset).
    Write-RunCmd $python
    $started = Get-Date
    $proc = Start-Process -FilePath $runCmd -WindowStyle Hidden -PassThru
    [LlmMonitorJob]::Assign($proc.Handle)
    $srv = Get-ServerChild $proc.Id
    if ($srv) {
        # A server that started before the wrapper joined the job is added explicitly.
        $srvHandle = (Get-Process -Id $srv.ProcessId).Handle
        [LlmMonitorJob]::Assign($srvHandle)
        Write-State $proc.Id $srv.ProcessId $started.ToString("o")
        Write-Lifecycle "server start (wrapper pid $($proc.Id), server pid $($srv.ProcessId))"
    } else {
        Write-Lifecycle "server start (wrapper pid $($proc.Id), server did not appear within 10 s)"
    }

    $beat = Get-Date
    while (-not $proc.WaitForExit(1000)) {
        if (Test-StopRequested) {
            Write-Lifecycle "stop requested ($stopFile); stopping own server"
            Invoke-OwnServerStop "stop requested"
        }
        if (((Get-Date) - $beat).TotalSeconds -ge 10 -and $srv) {
            Write-State $proc.Id $srv.ProcessId $started.ToString("o")
            $beat = Get-Date
        }
    }
    $ran = [int]((Get-Date) - $started).TotalSeconds
    Write-Lifecycle "server exit code $($proc.ExitCode) after $ran s"
    Clear-OwnState

    if ($ran -ge 300) { $backoff = 5 } else { $backoff = [Math]::Min($backoff * 2, 60) }
    Write-Lifecycle "restart in $backoff s"
    $wake = (Get-Date).AddSeconds($backoff)
    while ((Get-Date) -lt $wake) {
        if (Test-StopRequested) { Close-Supervisor 0 "stop requested during backoff" }
        Start-Sleep -Milliseconds 500
    }
}
