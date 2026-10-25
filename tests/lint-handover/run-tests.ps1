# run-tests.ps1 - checks that lint-handover.ps1 accepts the good fixtures and rejects each bad fixture
# for exactly the expected reason(s). Exit 0 = every expectation met. Exit 1 = at least one expectation failed.
#   powershell -NoProfile -ExecutionPolicy Bypass -File tests\lint-handover\run-tests.ps1
# The fixtures carry a fixed git_commit; the lint gets that commit through -Head, so the suite does not
# depend on the live HEAD (audit-27 a27-03). One case runs against a different HEAD to prove L2 still bites.

$ErrorActionPreference = "Stop"

$here   = $PSScriptRoot
$repo   = Resolve-Path (Join-Path $here "..\..") | Select-Object -ExpandProperty Path
$lint   = Join-Path $repo "agent\scripts\lint-handover.ps1"
$good   = Join-Path $here "good.md"
$fixtureHead = ((Get-Content -LiteralPath $good | Where-Object { $_ -match '^git_commit:' }) -replace '^git_commit:\s*', '').Trim()

# Generated fixture (temp file, removed below): absolute and %VAR% paths that exist on any machine.
$absFixture = Join-Path ([System.IO.Path]::GetTempPath()) "lint-handover-good-abs-$PID.md"
$abs = (Get-Content -LiteralPath $good -Raw) -replace '(?m)^(- Not allowed: .*)$',
    ("`$1`n- Read only: ``" + (Join-Path $repo "llm-monitor\server.py") + "`` and ``%SystemRoot%\System32\cmd.exe``.")
Set-Content -LiteralPath $absFixture -Value $abs -Encoding utf8 -NoNewline

# fixture -> expected exit code, the exact set of checks that must FAIL (empty = must pass), and the HEAD
$cases = [ordered]@{
    "good.md"             = @{ Exit = 0; Checks = @();           Head = $fixtureHead }
    "good-abs (generated)"= @{ Exit = 0; Checks = @();           Head = $fixtureHead; Path = $absFixture }
    "good.md @ other HEAD"= @{ Exit = 1; Checks = @("L2");       Head = "1111111111111111111111111111111111111111"; Path = $good }
    "bad-no-block.md"     = @{ Exit = 1; Checks = @("L3", "L4"); Head = $fixtureHead }
    "bad-no-evidence.md"  = @{ Exit = 1; Checks = @("L7");       Head = $fixtureHead }
    "bad-name-kill.md"    = @{ Exit = 1; Checks = @("L8");       Head = $fixtureHead }
    "bad-pipe-kill.md"    = @{ Exit = 1; Checks = @("L8");       Head = $fixtureHead }
    "bad-missing-path.md" = @{ Exit = 1; Checks = @("L9");       Head = $fixtureHead }
    "bad-two-files.md"    = @{ Exit = 1; Checks = @("L6");       Head = $fixtureHead }
    "bad-commit.md"       = @{ Exit = 1; Checks = @("L2");       Head = $fixtureHead }
    "bad-no-8080.md"      = @{ Exit = 1; Checks = @("L12");      Head = $fixtureHead }
}

$rows = @()
$allOk = $true
try {
    foreach ($name in $cases.Keys) {
        $want = $cases[$name]
        $path = if ($want.Path) { $want.Path } else { Join-Path $here $name }
        $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $lint -Path $path -Head $want.Head 2>&1
        $code = $LASTEXITCODE
        $failed = @($out | ForEach-Object { if ("$_" -match '^FAIL\s+(L\d+)\b') { $matches[1] } })
        $exitOk = ($code -eq $want.Exit)
        $setOk = ((@($failed | Sort-Object) -join ',') -eq (@($want.Checks | Sort-Object) -join ','))
        $ok = $exitOk -and $setOk
        if (-not $ok) { $allOk = $false }
        $rows += [pscustomobject]@{
            Fixture  = $name
            Exit     = "$code (want $($want.Exit))"
            Expected = if ($want.Checks.Count) { "FAIL " + ($want.Checks -join ',') } else { "PASS all" }
            Got      = if ($failed.Count) { "FAIL " + ($failed -join ',') } else { "PASS all" }
            Result   = if ($ok) { "OK" } else { "MISMATCH" }
        }
    }
} finally {
    Remove-Item -LiteralPath $absFixture -Force -ErrorAction SilentlyContinue
}

$rows | Format-Table -AutoSize | Out-String | Write-Output
if ($allOk) { Write-Output "RESULT: all expectations met"; exit 0 }
Write-Output "RESULT: expectation(s) failed"
exit 1
