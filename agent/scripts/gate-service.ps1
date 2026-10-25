# gate-service.ps1 - state gate for the M76 dashboard service. Read-only by default.
#   powershell -NoProfile -ExecutionPolicy Bypass -File agent\scripts\gate-service.ps1 [-SmokeTest]
# Exit 0 = no FAIL. Exit 1 = at least one FAIL. Exit 2 = PSScriptAnalyzer not installed (prints the install command).
# -SmokeTest (amendment audit-26 A1): starts a supervisor on spare port 8098, checks 200, then stops the
# supervisor and its server BY PID after a command-line match, and removes the 8098 files (audit-27 a27-01).
# It refuses to start when 8098 is already in use. Without -SmokeTest nothing is started or stopped.

param(
    [switch]$SmokeTest
)

$ErrorActionPreference = "Stop"

$repo    = Resolve-Path (Join-Path $PSScriptRoot "..\..") | Select-Object -ExpandProperty Path
$supv    = Join-Path $repo "llm-monitor\service-supervisor.ps1"
$server  = Join-Path $repo "llm-monitor\server.py"
$restart = Join-Path $repo "restart-llm-monitor.ps1"
$logDir  = Join-Path $env:LOCALAPPDATA "LLMMonitor"

$results = New-Object System.Collections.Generic.List[object]
function Add-Gate([string]$id, [string]$status, [string]$evidence) {
    $results.Add([pscustomobject]@{ Id = $id; Status = $status; Evidence = $evidence })
}

# ---- Prerequisite: PSScriptAnalyzer ----------------------------------------------
if (-not (Get-Module -ListAvailable -Name PSScriptAnalyzer)) {
    Write-Output "ERROR  PSScriptAnalyzer is not installed."
    Write-Output "       Install once, in a normal PowerShell window:"
    Write-Output "       Install-Module PSScriptAnalyzer -Scope CurrentUser -Force"
    exit 2
}
Import-Module PSScriptAnalyzer

$scripts = @($supv, $restart, (Join-Path $repo "llm-monitor\install-service.ps1"),
             (Join-Path $repo "agent\scripts\lint-handover.ps1"),
             (Join-Path $repo "tests\lint-handover\run-tests.ps1"), $PSCommandPath) |
           Where-Object { Test-Path $_ }

# ---- G1: analyser, Error severity fails; Write-Host is WARN only --------------------
$errs = @(); $warns = @()
foreach ($s in $scripts) {
    foreach ($f in @(Invoke-ScriptAnalyzer -Path $s -Severity Error, Warning)) {
        $line = "$(Split-Path $s -Leaf):$($f.Line) $($f.RuleName)"
        if ($f.Severity -eq 'Error') { $errs += $line } else { $warns += $line }
    }
}
if ($errs.Count -eq 0) { Add-Gate "G1" "PASS" ("0 errors; warnings: " + $warns.Count + " (" + (($warns | ForEach-Object { ($_ -split ' ')[-1] } | Sort-Object -Unique) -join ', ') + ")") }
else { Add-Gate "G1" "FAIL" ($errs -join '; ') }

# ---- G1b: bare boolean words (the analyser and parser do not catch these) ------------
# A bare true/false parses as a command call. Find those command calls in the syntax tree; this
# ignores comments and here-strings (such as the supervisor's embedded C#), unlike a text regex.
$bare = @()
$bareFiles = @(Get-ChildItem -Path (Join-Path $repo "llm-monitor") -Filter *.ps1 -File) +
             @(Get-ChildItem -Path (Join-Path $repo "agent\scripts") -Filter *.ps1 -File) +
             @(Get-Item $restart -ErrorAction SilentlyContinue)
foreach ($f in $bareFiles) {
    $ast = [System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$null, [ref]$null)
    $hits = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] -and
        $n.GetCommandName() -in @('true', 'false') }, $true)
    foreach ($h in $hits) { $bare += "$($f.Name):$($h.Extent.StartLineNumber)" }
}
if ($bare.Count -eq 0) { Add-Gate "G1b" "PASS" "no bare boolean assignments" }
else { Add-Gate "G1b" "FAIL" ("bare boolean at " + ($bare -join ', ')) }

# ---- G2: parse ---------------------------------------------------------------------------
$parseErr = @()
foreach ($s in $scripts) {
    $e = $null
    [System.Management.Automation.Language.Parser]::ParseFile($s, [ref]$null, [ref]$e) | Out-Null
    if ($e.Count -gt 0) { $parseErr += "$(Split-Path $s -Leaf): $($e.Count)" }
}
if ($parseErr.Count -eq 0) { Add-Gate "G2" "PASS" ("parse OK: " + $scripts.Count + " files") }
else { Add-Gate "G2" "FAIL" ($parseErr -join '; ') }

# ---- G3: owner chain for 8090 ------------------------------------------------------------
$g3 = $null; $g3Ev = ""
$listen = @(Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue)
if ($listen.Count -eq 0) { $g3Ev = "nothing listens on 8090" }
else {
    $srvPid = $listen[0].OwningProcess
    $srv = Get-CimInstance Win32_Process -Filter "ProcessId=$srvPid"
    $wrap = if ($srv) { Get-CimInstance Win32_Process -Filter "ProcessId=$($srv.ParentProcessId)" } else { $null }
    $sup  = if ($wrap) { Get-CimInstance Win32_Process -Filter "ProcessId=$($wrap.ParentProcessId)" } else { $null }
    if ($srv -and -not $srv.CommandLine) {
        # Session-0 chain (boot task, S4U): command lines are hidden from the desktop. Accept it only
        # when the supervisor's fresh state file names exactly this server, wrapper and a live supervisor.
        $st = $null
        try { $st = Get-Content -LiteralPath (Join-Path $logDir "service-8090.state.json") -Raw -ErrorAction Stop | ConvertFrom-Json } catch { $st = $null }
        $age = if ($st) { [int]((Get-Date) - [datetime]$st.heartbeat).TotalSeconds } else { -1 }
        $g3 = [bool]($st -and $st.server_pid -eq $srvPid -and $st.wrapper_pid -eq $srv.ParentProcessId -and
            $wrap -and $wrap.ParentProcessId -eq $st.supervisor_pid -and $sup -and $sup.Name -match '^powershell' -and
            $age -ge 0 -and $age -le 30)
        $g3Ev = "server $srvPid -> wrapper $($srv.ParentProcessId) -> supervisor $($wrap.ParentProcessId), session $($srv.SessionId): command lines hidden; state file attests=$g3 (heartbeat ${age}s)"
        $script:g3State = $st
    } else {
        $okServer = $srv -and ($srv.CommandLine -match [regex]::Escape($server))
        $okWrap   = $wrap -and ($wrap.CommandLine -match 'run-server-8090\.cmd')
        $okSup    = $sup -and ($sup.Name -match '^powershell') -and ($sup.CommandLine -match 'service-supervisor\.ps1')
        $g3Ev = "server $srvPid(ok=$okServer) -> wrapper $($srv.ParentProcessId)(ok=$okWrap) -> supervisor $($wrap.ParentProcessId)(ok=$okSup)"
        $g3 = ($okServer -and $okWrap -and $okSup)
    }
    $script:g3Server = $srv; $script:g3Sup = $sup
}
if ($g3) { Add-Gate "G3" "PASS" $g3Ev }
else { Add-Gate "G3" "FAIL" ($g3Ev + " (served but unsupervised if any link is missing)") }

# ---- G4 / G5: scheduled tasks -------------------------------------------------------------
function Test-Task([string]$name, [string]$logon, [string]$id) {
    $t = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if (-not $t) { Add-Gate $id "FAIL" "task $name not found"; return }
    $limit = $t.Settings.ExecutionTimeLimit
    $arg = $t.Actions[0].Arguments
    $ok = ($t.State -in @('Ready','Running')) -and ($t.Principal.LogonType -eq $logon) -and ($limit -eq 'PT0S') -and ($arg -match 'service-supervisor\.ps1')
    $ev = "state=$($t.State) logon=$($t.Principal.LogonType) limit=$limit supervisor-action=$($arg -match 'service-supervisor')"
    Add-Gate $id ($(if ($ok) { "PASS" } else { "FAIL" })) $ev
}
Test-Task "LLMMonitor" "Interactive" "G4"
Test-Task "LLMMonitorBoot" "S4U" "G5"

# ---- G6: process time later than file time ------------------------------------------------
$g6Bad = @()
$supFile = Get-Item $supv
$srvFile = Get-Item $server
# Start times come from the process, or from the state file when the process is hidden (session 0).
$supStarted = if ($script:g3Sup.CreationDate) { [datetime]$script:g3Sup.CreationDate } elseif ($script:g3State) { [datetime]$script:g3State.supervisor_started } else { $null }
$srvStarted = if ($script:g3Server.CreationDate) { [datetime]$script:g3Server.CreationDate } elseif ($script:g3State) { [datetime]$script:g3State.server_started } else { $null }
if ($supStarted -and ($supStarted -lt $supFile.LastWriteTime)) { $g6Bad += "supervisor started $supStarted before $($supFile.Name) written $($supFile.LastWriteTime)" }
if ($srvStarted -and ($srvStarted -lt $srvFile.LastWriteTime)) { $g6Bad += "server started $srvStarted before server.py written $($srvFile.LastWriteTime)" }
if ($script:g3Sup -and -not $supStarted) { $g6Bad += "supervisor start time unknown" }
if ($null -eq $script:g3Sup) { Add-Gate "G6" "WARN" "no supervisor to compare (see G3)" }
elseif ($g6Bad.Count -eq 0) { Add-Gate "G6" "PASS" "supervisor and server started after their files were written" }
else { Add-Gate "G6" "FAIL" ($g6Bad -join '; ') }

# ---- G7: stray artefacts (rule R2; audit-27 a27-05) ----------------------------------------------
# Task and milestone folders hold only .md files; no scratch folder is left; the log folder holds no
# probe logs and no spare-port (8091-8099) test files.
$stray = @()
foreach ($d in @("agent\tasks", "agent\milestones")) {
    $p = Join-Path $repo $d
    if (Test-Path $p) {
        $stray += Get-ChildItem -Path $p -Recurse -File -Force | Where-Object { $_.Extension -ne '.md' -and $_.Name -ne '.gitkeep' } |
            ForEach-Object { $_.FullName.Substring($repo.Length + 1) }
    }
}
$stray += Get-ChildItem -Path (Join-Path $repo "agent") -Directory -Filter 'scratch-*' |
    ForEach-Object { "$($_.FullName.Substring($repo.Length + 1)) (scratch folder left behind)" }
if (Test-Path $logDir) {
    $stray += Get-ChildItem -Path $logDir -File |
        Where-Object { $_.Name -match '^(probe\.|t-.*\.log$|run-server-809[1-9]\.cmd$|service-809[1-9]\.|stop-\d+\.request$)' } |
        ForEach-Object { "LLMMonitor\$($_.Name)" }
}
if ($stray.Count -eq 0) { Add-Gate "G7" "PASS" "no scripts in task/milestone folders, no scratch folders, no probe or spare-port files" }
else { Add-Gate "G7" "FAIL" ("stray: " + ($stray -join '; ')) }

# ---- G8: name-based kill patterns in repo scripts --------------------------------------------
# Same pattern as lint-handover.ps1 L8 (audit-27 a27-02): -Name/-ProcessName, a pipeline into
# Stop-Process/spps/kill (Get-Process python | Stop-Process), taskkill, pkill, killall, wmic terminate.
$killRx = '(?i)\b(Stop-Process|spps|kill)\b[^|\r\n]*\s-(Name|ProcessName|n)\b|\|\s*(Stop-Process|spps|kill)\b|\btaskkill\b|\bpkill\b|\bkillall\b|\bwmic\b.*\b(delete|terminate)\b|\bkill\s+\S*\.exe\b|\bkill\s+python'
$kills = @()
$killFiles = @(Get-ChildItem -Path (Join-Path $repo "llm-monitor") -Filter *.ps1 -File) +
             @(Get-ChildItem -Path (Join-Path $repo "agent\scripts") -Filter *.ps1 -File) +
             @(Get-Item $restart -ErrorAction SilentlyContinue)
foreach ($f in $killFiles) {
    $n = 0
    foreach ($ln in Get-Content -LiteralPath $f.FullName -Encoding UTF8) {
        $n++
        if ($ln -match '^\s*#') { continue }
        if ($ln -match '\$\w*Rx\s*=') { continue }   # a pattern definition, not an instruction
        if ($ln -match $killRx) { $kills += "$($f.Name):$n" }
    }
}
if ($kills.Count -eq 0) { Add-Gate "G8" "PASS" "no name-based kill commands in scripts" }
else { Add-Gate "G8" "FAIL" ($kills -join ', ') }

# ---- G9: live probes (read-only) ------------------------------------------------------------
foreach ($pair in @(@("G9a", 8090, "/api/stats"), @("G9b", 8081, "/health"))) {
    try {
        $code = (Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:$($pair[1])$($pair[2])" -TimeoutSec 5).StatusCode
        Add-Gate $pair[0] $(if ($code -eq 200) { "PASS" } else { "FAIL" }) "port $($pair[1]) returned $code"
    } catch { Add-Gate $pair[0] "FAIL" "port $($pair[1]) no answer: $($_.Exception.Message.Split([Environment]::NewLine)[0])" }
}

# ---- G10: smoke test on spare port (opt-in) ----------------------------------------------------
function Invoke-StopIfMatch([int]$procId, [string]$pattern, [string]$label) {
    # Stops a PID only when its command line matches (rule R7). Returns a note for the evidence.
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
    if (-not $p) { return "$label $procId already gone" }
    if ($p.CommandLine -notmatch $pattern) { return "$label $procId NOT stopped: command line does not match" }
    try { Stop-Process -Id $procId -Force -ErrorAction Stop; return "$label $procId stopped" }
    catch { return "$label $procId stop failed: $($_.Exception.Message)" }
}
if ($SmokeTest) {
    $spare = 8098
    if (@(Get-NetTCPConnection -LocalPort $spare -State Listen -ErrorAction SilentlyContinue).Count -gt 0) {
        Add-Gate "G10" "FAIL" "port $spare is already in use; smoke test not started and nothing stopped"
    } else {
        $sp = $null; $ok = $false; $notes = @()
        $supRx = [regex]::Escape($supv) + '.*-Port\s+' + $spare + '\b'
        $srvRx = [regex]::Escape($server) + '"?\s+' + $spare + '\b'
        try {
            $sp = Start-Process powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$supv`"",'-Port',"$spare" -WindowStyle Hidden -PassThru
            $deadline = (Get-Date).AddSeconds(15)
            while ((Get-Date) -lt $deadline -and -not $ok) {
                Start-Sleep -Seconds 1
                try { $ok = ((Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:$spare/api/stats" -TimeoutSec 3).StatusCode -eq 200) } catch { $null = $_ }
            }
        } finally {
            # Supervisor first, so it cannot restart the server; then the server, then the wrapper.
            $srvPid = Get-NetTCPConnection -LocalPort $spare -State Listen -ErrorAction SilentlyContinue |
                Select-Object -First 1 -ExpandProperty OwningProcess
            $wrapPid = if ($srvPid) { (Get-CimInstance Win32_Process -Filter "ProcessId=$srvPid").ParentProcessId } else { $null }
            if ($sp) { $notes += Invoke-StopIfMatch $sp.Id $supRx "supervisor" }
            if ($srvPid) { $notes += Invoke-StopIfMatch $srvPid $srvRx "server" }
            if ($wrapPid) { $notes += Invoke-StopIfMatch $wrapPid ('run-server-' + $spare + '\.cmd') "wrapper" }
            Start-Sleep -Seconds 1
            if (@(Get-NetTCPConnection -LocalPort $spare -State Listen -ErrorAction SilentlyContinue).Count -eq 0) {
                Get-ChildItem -Path $logDir -File |
                    Where-Object { $_.Name -match ('^(run-server-' + $spare + '\.cmd|service-' + $spare + '\.)') } |
                    Remove-Item -Force
                $notes += "port $spare free; test files removed"
            } else { $ok = $false; $notes += "port $spare still in use after cleanup" }
        }
        Add-Gate "G10" $(if ($ok) { "PASS" } else { "FAIL" }) ("spare-port supervisor start, /api/stats 200=$ok; " + ($notes -join '; '))
    }
} else {
    Add-Gate "G10" "SKIP" "run with -SmokeTest to start a spare-port supervisor (opt-in)"
}

# ---- output ----------------------------------------------------------------------------------------
$fails = @($results | Where-Object { $_.Status -eq 'FAIL' }).Count
foreach ($r in $results) { Write-Output ("{0,-5} {1,-4} {2}" -f $r.Status, $r.Id, $r.Evidence) }
Write-Output ""
if ($fails -eq 0) { Write-Output "OVERALL: PASS (no FAIL; WARN and SKIP do not fail)"; exit 0 }
Write-Output "OVERALL: FAIL ($fails check(s))"
exit 1
