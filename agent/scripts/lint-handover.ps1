# lint-handover.ps1 - checks a handover against the rules in agent/skills/local.handover-executor.md.
# Read-only. Exit 0 = all checks pass. Exit 1 = at least one FAIL. Exit 2 = usage or file not found.
#   powershell -NoProfile -ExecutionPolicy Bypass -File agent\scripts\lint-handover.ps1 -Path <handover.md> [-Explain] [-Head <sha>]
# -Head replaces `git rev-parse HEAD` for check L2. The fixture tests use it so they do not depend on the
# live commit (audit-27 a27-03).

param(
    [Parameter(Mandatory = $true)][string]$Path,
    [switch]$Explain,
    [string]$Head = ""
)

$ErrorActionPreference = "Stop"

$repo  = Resolve-Path (Join-Path $PSScriptRoot "..\..") | Select-Object -ExpandProperty Path
$skill = Join-Path $repo "agent\skills\local.handover-executor.md"

if (-not (Test-Path $Path)) { Write-Output "ERROR  file not found: $Path"; exit 2 }
if (-not (Test-Path $skill)) { Write-Output "ERROR  skill not found: $skill"; exit 2 }

$lines = @(Get-Content -LiteralPath $Path -Encoding UTF8)
$results = New-Object System.Collections.Generic.List[object]

function Add-Result([string]$id, [string]$name, [bool]$ok, [string]$reason, [int]$line = 0) {
    $results.Add([pscustomobject]@{ Id = $id; Name = $name; Ok = $ok; Reason = $reason; Line = $line })
}

# ---- section map: heading text -> start/end line index (0-based) -----------
$sections = @{}
$currentHead = $null; $currentStart = 0
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^## (.+?)\s*$') {
        if ($currentHead) { $sections[$currentHead] = @($currentStart, ($i - 1)) }
        $currentHead = $matches[1].Trim(); $currentStart = $i
    }
}
if ($currentHead) { $sections[$currentHead] = @($currentStart, ($lines.Count - 1)) }

function Get-SectionLine([string]$head) {
    if (-not $sections.ContainsKey($head)) { return @() }
    $r = $sections[$head]
    return @($lines[$r[0]..$r[1]])
}

# ---- fenced-block mask: $inFence[i] = $true if line i is inside ``` ... ``` --
$inFence = @($false) * $lines.Count
$fence = $false
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\s*```') { $fence = -not $fence; $inFence[$i] = $true; continue }
    $inFence[$i] = $fence
}

# ---- rules block -------------------------------------------------------------
$bIdx = [array]::IndexOf($lines, '<!-- HANDOVER-RULES v1 BEGIN -->')
$eIdx = [array]::IndexOf($lines, '<!-- HANDOVER-RULES v1 END -->')
$inRules = @($false) * $lines.Count
if ($bIdx -ge 0 -and $eIdx -gt $bIdx) { for ($i = $bIdx; $i -le $eIdx; $i++) { $inRules[$i] = $true } }

# ---- L1 front matter ----------------------------------------------------------
$fmEnd = -1
if ($lines.Count -gt 0 -and $lines[0].Trim() -eq '---') {
    for ($i = 1; $i -lt $lines.Count; $i++) { if ($lines[$i].Trim() -eq '---') { $fmEnd = $i; break } }
}
if ($fmEnd -lt 0) {
    Add-Result "L1" "front matter present" $false "no front matter block between --- lines" 1
} else {
    $fm = $lines[1..($fmEnd - 1)]
    $keys = @('handover_version','handoff_mode','from_executor','to_executor','date','status')
    $missing = @($keys | Where-Object { -not ($fm -match ("^" + $_ + ":")) })
    if ($missing.Count -eq 0) { Add-Result "L1" "front matter keys" $true "" }
    else { Add-Result "L1" "front matter keys" $false ("missing: " + ($missing -join ', ')) 1 }
}

# ---- L2 git_commit ------------------------------------------------------------
$gitLine = $lines | Where-Object { $_ -match '^git_commit:' } | Select-Object -First 1
if (-not $gitLine) {
    Add-Result "L2" "git_commit matches HEAD (or drift noted)" $false "git_commit key missing"
} else {
    $commit = ($gitLine -replace '^git_commit:\s*', '').Trim()
    $head = if ($Head) { $Head } else { (& git -C $repo rev-parse HEAD 2>$null) }
    $hasDrift = [bool]($lines | Where-Object { $_ -match '^\s*drift:' })
    if ($commit -eq $head -or $hasDrift) { Add-Result "L2" "git_commit matches HEAD (or drift noted)" $true "" }
    else { Add-Result "L2" "git_commit matches HEAD (or drift noted)" $false "handover commit $commit, HEAD $head, no drift line" }
}

# ---- L3 rules block present once ----------------------------------------------
$nB = @($lines | Where-Object { $_ -eq '<!-- HANDOVER-RULES v1 BEGIN -->' }).Count
$nE = @($lines | Where-Object { $_ -eq '<!-- HANDOVER-RULES v1 END -->' }).Count
if ($nB -eq 1 -and $nE -eq 1) { Add-Result "L3" "rules block present once" $true "" }
else { Add-Result "L3" "rules block present once" $false "BEGIN found $nB, END found $nE" }

# ---- L4 rules block identical to the skill -------------------------------------
function Get-RulesText([string[]]$src) {
    $b = [array]::IndexOf($src, '<!-- HANDOVER-RULES v1 BEGIN -->')
    $e = [array]::IndexOf($src, '<!-- HANDOVER-RULES v1 END -->')
    if ($b -lt 0 -or $e -le $b) { return $null }
    return (($src[($b + 1)..($e - 1)] | ForEach-Object { $_.TrimEnd() }) -join "`n").Trim()
}
$hText = Get-RulesText $lines
$sText = Get-RulesText @(Get-Content -LiteralPath $skill -Encoding UTF8)
if ($null -eq $hText) { Add-Result "L4" "rules block identical to skill" $false "no rules block to compare" }
elseif ($hText -eq $sText) { Add-Result "L4" "rules block identical to skill" $true "" }
else { Add-Result "L4" "rules block identical to skill" $false "text differs from the rules block in the skill" }

# ---- L5 required headings ------------------------------------------------------
$req = @('Permission','Steps','Stop rules','Do NOT','What to send back')
$missH = @($req | Where-Object { -not $sections.ContainsKey($_) })
if ($missH.Count -eq 0) { Add-Result "L5" "required headings present" $true "" }
else { Add-Result "L5" "required headings present" $false ("missing: " + ($missH -join ', ')) }

# ---- L6 each step names exactly one file ---------------------------------------
$pathRx = '\.(md|ps1|py|json|yml|yaml|cmd|bat|sh|txt|xml)$'
function Get-PathToken([string]$text) {
    $found = @()
    foreach ($m in [regex]::Matches($text, '`([^`]+)`')) {
        $tok = $m.Groups[1].Value
        if ($tok -match '^(https?://)' -or $tok -match '\s' -or $tok -match '[<>{}*]') { continue }
        if ($tok -match '[\\/]' -or $tok -match $pathRx) { $found += $tok }
    }
    return ,$found
}
if ($sections.ContainsKey('Steps')) {
    $r = $sections['Steps']
    $stepFail = $null
    for ($i = $r[0] + 1; $i -le $r[1]; $i++) {
        if ($inFence[$i]) { continue }
        if ($lines[$i] -match '^\s*(\d+\.|-|\*\*Step)') {
            $n = (Get-PathToken $lines[$i]).Count
            if ($n -ne 1 -and -not $stepFail) { $stepFail = @(($i + 1), $n) }
        }
    }
    if (-not $stepFail) { Add-Result "L6" "each step names one file" $true "" }
    else { Add-Result "L6" "each step names one file" $false ("step names " + $stepFail[1] + " file path(s), expected 1") $stepFail[0] }
} else { Add-Result "L6" "each step names one file" $false "no Steps section" }

# ---- L7 verdict lines are followed by a fenced command and output --------------
$exemptHeads = @('Rules','Do NOT','Stop rules','Environment notes (Zed, Windows, restricted shell)','Model fit','Required sections of a handover','Template','Changelog')
$exempt = @($false) * $lines.Count
foreach ($h in $exemptHeads) {
    if ($sections.ContainsKey($h)) { $r = $sections[$h]; for ($i = $r[0]; $i -le $r[1]; $i++) { $exempt[$i] = $true } }
}
$verdictRx = '^\s*([-*]|\d+\.)?\s*(\*\*)?(PASS|FAIL|\u2705)'
$l7Bad = $null
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($inRules[$i] -or $inFence[$i] -or $exempt[$i]) { continue }
    if ($lines[$i] -match $verdictRx) {
        $ok = $false
        for ($j = $i + 1; $j -le [Math]::Min($i + 15, $lines.Count - 1); $j++) {
            if ($lines[$j] -match '^\s*```') {
                $block = @()
                for ($k = $j + 1; $k -lt $lines.Count -and $lines[$k] -notmatch '^\s*```'; $k++) { $block += $lines[$k] }
                if ($block | Where-Object { $_ -match '^\s*(\$ |PS>|powershell|python|git |Get-|Select-|Invoke-|Test-|Start-|Stop-|fsutil|schtasks|cmd )' }) { $ok = $true }
                break
            }
        }
        if (-not $ok -and -not $l7Bad) { $l7Bad = $i + 1 }
    }
}
if (-not $l7Bad) { Add-Result "L7" "verdict lines carry command and output" $true "" }
else { Add-Result "L7" "verdict lines carry command and output" $false "PASS/FAIL line has no fenced command block within 15 lines" $l7Bad }

# ---- L8 no name-based kills as instructions ------------------------------------
# Same pattern as gate-service.ps1 G8 (audit-27 a27-02): -Name/-ProcessName, a pipeline into
# Stop-Process/spps/kill (Get-Process python | Stop-Process), taskkill, pkill, killall, wmic terminate.
$killRx = '(?i)\b(Stop-Process|spps|kill)\b[^|\r\n]*\s-(Name|ProcessName|n)\b|\|\s*(Stop-Process|spps|kill)\b|\btaskkill\b|\bpkill\b|\bkillall\b|\bwmic\b.*\b(delete|terminate)\b|\bkill\s+\S*\.exe\b|\bkill\s+python'
$l8Bad = $null
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($inRules[$i] -or $inFence[$i] -or $exempt[$i]) { continue }
    if ($lines[$i] -match $killRx -and -not $l8Bad) { $l8Bad = $i + 1 }
}
if (-not $l8Bad) { Add-Result "L8" "no name-based kill instructions" $true "" }
else { Add-Result "L8" "no name-based kill instructions" $false "name-based kill instruction" $l8Bad }

# ---- L9 backticked repo paths exist -------------------------------------------
$l9Bad = @()
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($inRules[$i] -or $inFence[$i] -or $exempt[$i]) { continue }
    if ($lines[$i] -match '\(new\)') { continue }
    foreach ($tok in (Get-PathToken $lines[$i])) {
        # Absolute and %VAR% paths are checked as they are, not joined to the repo (audit-27 a27-13).
        $full = [Environment]::ExpandEnvironmentVariables($tok)
        if ($full -match '%\w+%') { continue }
        if (-not [System.IO.Path]::IsPathRooted($full)) { $full = Join-Path $repo $full }
        if (-not (Test-Path $full)) { $l9Bad += "$tok (line $($i + 1))" }
    }
}
if ($l9Bad.Count -eq 0) { Add-Result "L9" "referenced paths exist" $true "" }
else { Add-Result "L9" "referenced paths exist" $false ("missing: " + (($l9Bad | Select-Object -First 3) -join '; ')) }

# ---- L10 receipts path under agent/tasks ---------------------------------------
$sendBack = (Get-SectionLine 'What to send back') -join "`n"
if ($sendBack -match 'agent[\\/]tasks[\\/]') { Add-Result "L10" "receipts path under agent/tasks" $true "" }
else { Add-Result "L10" "receipts path under agent/tasks" $false "What to send back has no agent/tasks/ path" }

# ---- L11 no unresolved placeholders --------------------------------------------
$l11Bad = $null
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($inRules[$i] -or $inFence[$i] -or $exempt[$i]) { continue }
    if ($lines[$i] -match '\bTBD\b|\{[a-zA-Z_][a-zA-Z_ ]*\}' -and -not $l11Bad) { $l11Bad = $i + 1 }
}
if (-not $l11Bad) { Add-Result "L11" "no unresolved placeholders" $true "" }
else { Add-Result "L11" "no unresolved placeholders" $false "placeholder text" $l11Bad }

# ---- L12 permission names the forbidden ports ----------------------------------
$perm = (Get-SectionLine 'Permission') -join "`n"
$mentionsRestart = ($perm -match '8090' -or $perm -match '(?i)restart')
if (-not $mentionsRestart) { Add-Result "L12" "forbidden ports named" $true "no restart in Permission" }
elseif ($perm -match '8080' -and $perm -match '8081') { Add-Result "L12" "forbidden ports named" $true "" }
else { Add-Result "L12" "forbidden ports named" $false "Permission allows a restart but does not name both 8080 (gateway) and 8081 (Strata) as forbidden" }

# ---- output ------------------------------------------------------------------------
$rulesText = @{
    "L1" = "R8/Required sections: front matter keys"; "L2" = "Required sections / git claims (R10)"
    "L3" = "Rules block present once (copy verbatim)"; "L4" = "Rules block must match the skill (v1)"
    "L5" = "Required headings (see skill: Required sections)"; "L6" = "R8: one file per step"
    "L7" = "R3: evidence for every claim"; "L8" = "R7: never stop a process by name"
    "L9" = "R8/R10: named paths must exist"; "L10" = "What to send back: receipts path"
    "L11" = "No unresolved placeholders"; "L12" = "Permission: name forbidden ports"
}
$fails = 0
foreach ($r in $results) {
    $status = if ($r.Ok) { "PASS" } else { "FAIL"; $fails++ }
    $where = if ($r.Line -gt 0) { " (line $($r.Line))" } else { "" }
    $why = if ($r.Ok -or -not $r.Reason) { "" } else { " - $($r.Reason)" + $where }
    Write-Output ("{0}  {1} {2}{3}" -f $status, $r.Id, $r.Name, $why)
    if ($Explain -and -not $r.Ok) { Write-Output ("      rule: " + $rulesText[$r.Id]) }
}
Write-Output ""
if ($fails -eq 0) { Write-Output "RESULT: PASS (all checks)"; exit 0 }
Write-Output "RESULT: FAIL ($fails check(s))"
exit 1
