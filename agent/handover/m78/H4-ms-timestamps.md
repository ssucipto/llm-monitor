---
handover_version: 1
handoff_mode: executor
from_executor: claude-opus-5.5
to_executor: strata-iq3s (qwen3.8-flash-next-iq3_s, headless Hermes on 192.168.0.75)
date: 2026-10-25
status: active
git_commit: 93b967d8f2ddc0d9260ba081c065d2bc6a41b89a
drift: HEAD is one commit after git_commit; that commit only adds this handover file (check with git diff --stat 93b967d HEAD). git status --short must be empty before step 1.
---

# Handover M78-H4: millisecond timestamps in the usage ledger (llm-monitor M78, Homelab B-89 T14; tier T0)

## Rules
<!-- HANDOVER-RULES v1 BEGIN -->
RULES (apply to every step; a violation means STOP and report):
R1. Budget probes: at most two variants per question. If the same probe gives an empty or identical result twice, stop probing and state the verdict.
R2. Helper scripts go in agent/scratch-<milestone>/. Run once. Delete after the output is recorded. Never put probes in agent/tasks/ or agent/milestones/.
R3. Evidence for every claim: a PASS/FAIL/PASS line must be followed by the command and its output, in a fenced block. A claim with no output is marked NOT RUN with a reason.
R4. File time vs process time: before recording a verification, record the file LastWriteTime and the process StartTime. If the file is newer, restart the process and re-run.
R5. Parse AND run: after each edit, parse the file, then run it once on a safe path (free spare port, test fixture, dry run).
R6. Two identical failures in a row: stop that step, write NOT RUN with the reason, and continue only with steps that do not depend on it.
R7. Stop only by PID, after checking the command line matches the target. Never stop a process by name (taskkill, Stop-Process -Name, pkill, kill).
R8. One file per step. Name the file in the step. Do not edit other files in that step.
R9. "Supervised", "fixed", "verified" are claims. They need the evidence from R3 and R4. Without it, write "served but unsupervised", "unverified", or NOT RUN.
R10. Check git claims before writing them (for example "tracked" or "committed"): run the git command and paste it.
R11. Do not commit or push unless the handover says so.
R12. If a step needs a permission the handover does not give, stop and ask in one line.
<!-- HANDOVER-RULES v1 END -->

## Start here (receiving agent)
1. Follow D:\Project\Homelab\agent\commands\local.execute.md (Check blocks go into agent/scratch-m78/check.ps1 and run with powershell -File).
2. Run git diff --stat 93b967d HEAD (must list only this handover file) and git status --short (must be empty). If not, stop and ask.
3. Create the receipts file agent/handover/m78/H4-receipts.md with a header: handover path, date, HEAD.
4. This repo is C:\Project\llm-monitor. Run every Check block through
   `powershell -NoProfile -ExecutionPolicy Bypass -File D:\Project\Homelab\agent\delegation\tools\run-check.ps1 -Run m78-H4 -Step N -Check agent/scratch-m78/check.ps1`
   (captures go to D:\Project\Homelab\agent\delegation\runs\m78-H4). Receipts format v2 (D:\Project\Homelab\agent\delegation\EXECUTOR.md).
5. Steps 1-3 are LF files: apply their blocks exactly. Step 4 is CRLF: only the helper named in its Check applies it.

## Problem / context
Live after H3, /api/usage read 0 for Claude Code in every window: Claude Code writes timestamps with milliseconds (2026-10-25T09:42:25.123Z), usage_ledger 1.0 parsed only whole seconds, and stored each row with no time instead of skipping it. H4 parses any ISO 8601 time with a zone, skips and counts a record with no usable time, and on connect removes the rows stored without a time once (and resets the cursors so the next pass reads them again). The orchestrator pre-tested every edit on an exported copy: 29/29, the new cases fail on the base by assert, 5/5 mutants caught.

## Locked decisions (do not re-litigate)
- Exact text only (tier T0).
- Numbers only: no change reads message text.
- `python` typed in PowerShell is a silent no-op shim on this PC: use `py -3.12` exactly as the Check blocks do.
- No e2e run in this handover (run-e2e-tests.sh): the orchestrator runs it after verification.
- The live dashboard on 8090 is NOT restarted here: the orchestrator restarts and checks it after verification.

## Permission
- Allowed: edit only the files named in steps 1-4 (step 4 only through the helper); the receipts file; run the Check commands as written (the mutation proof builds its own temp trees and removes them); delete agent/scratch-m78.
- Not allowed: the gateway on 8080 and Strata on 8081; the dashboard on 8090, restart-llm-monitor.ps1 and the scheduled tasks LLMMonitor / LLMMonitorBoot; llm-monitor/usage.sqlite3; reading ~/.claude or the Hermes state.db; sudo or elevation; commit or push; editing any other file.

## Steps

1. `llm-monitor/usage_ledger.py` — millisecond timestamps, skip a record with no usable time, the one-time repair. 4 edits (1a-1d). Expected: the Check output below.

Edit 1a. Find this text (it occurs exactly once):

```text
def iso_epoch(s):
    """ISO 8601 Z timestamp -> epoch seconds (parse_window's rule); None when it does not parse."""
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None
```

Replace it with:

```text
def iso_epoch(s):
    """ISO 8601 timestamp with a zone (Z or +hh:mm) -> epoch seconds; None when it does not parse or has no zone.
    Claude Code writes milliseconds (2026-10-25T09:42:25.123Z): 1.0 parsed only whole seconds (M78-H4)."""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None
    return dt.timestamp() if dt.tzinfo else None
```

Edit 1b. Find this text (it occurs exactly once):

```text
            cc = u.get("cache_creation") or {}
```

Replace it with:

```text
            ts = iso_epoch(j.get("timestamp"))
            if ts is None:  # no usable time: a row with no time falls in no window, so it is skipped, never stored (M78-H4)
                stats["skipped"] += 1
                continue
            cc = u.get("cache_creation") or {}
```

Edit 1c. Find this text (it occurs exactly once):

```text
                (f"{m.get('id')}:{j.get('requestId')}", j.get("sessionId"), iso_epoch(j.get("timestamp")),
```

Replace it with:

```text
                (f"{m.get('id')}:{j.get('requestId')}", j.get("sessionId"), ts,
```

Edit 1d. Find this text (it occurs exactly once):

```text
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_event ON usage_event(source, msg_key)")
    con.commit()
```

Replace it with:

```text
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_event ON usage_event(source, msg_key)")
    # M78-H4 repair, once: rows stored with no time (before H4) are dropped and every cursor reset, so the next pass reads them again
    if con.execute("DELETE FROM usage_event WHERE source = 'claude_code' AND t IS NULL").rowcount:
        con.execute("DELETE FROM usage_cursor")
    con.commit()
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 -c "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf8').read());print('parse ok')" llm-monitor/usage_ledger.py
(Select-String -Path llm-monitor/usage_ledger.py -SimpleMatch 'dt = datetime.fromisoformat(').Count
(Select-String -Path llm-monitor/usage_ledger.py -SimpleMatch 'stats["skipped"] += 1').Count
(Select-String -Path llm-monitor/usage_ledger.py -SimpleMatch 'con.execute("DELETE FROM usage_cursor")').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path llm-monitor/usage_ledger.py)) -eq 13).Count
```

Expected:

```text
parse ok
1
2
1
CR 0
```

If not: record FAIL with the full output and stop this step (R6).

2. `tests/usage/test_usage_ledger.py` — 5 contract cases for H4. 1 edit (2a). Expected: the Check output below.

Edit 2a. Find this text (it occurs exactly once):

```text
print("ALL PASSED (simulated)" if not fails else f"{len(fails)} FAILED")
```

Replace it with:

```text
# M78-H4: real Claude Code timestamps carry milliseconds; a record whose time does not parse is skipped, never stored with no time
MS = "2026-10-25T09:42:25.123Z"
expect("iso_epoch: a millisecond Z timestamp (Claude Code) parses", abs((ul.iso_epoch(MS) or 0) - 1792921345.123) < 1e-6, ul.iso_epoch(MS))
expect("iso_epoch: an offset timestamp parses; a naive one or junk does not",
       ul.iso_epoch("2026-10-25T09:42:25+00:00") == 1792921345.0 and ul.iso_epoch("2026-10-25T09:42:25") is None and ul.iso_epoch("x") is None)
tmp4 = tempfile.mkdtemp(prefix="m78-h4-")
try:
    proj = os.path.join(tmp4, "projects")
    os.makedirs(os.path.join(proj, "D--Project-Homelab"))
    good, bad = json.loads(msg("m9", "r9", T0)), json.loads(msg("m8", "r8", T0))
    good["timestamp"], bad["timestamp"] = MS, "not a time"
    with open(os.path.join(proj, "D--Project-Homelab", "s4.jsonl"), "w", encoding="utf8", newline="\n") as f:
        f.write(json.dumps(good) + "\n" + json.dumps(bad) + "\n")
    db4 = os.path.join(tmp4, "u.sqlite3")
    con4 = ul.connect(db4)
    st4 = ul.ingest_claude(con4, proj)
    ts4 = [r[0] for r in con4.execute("SELECT t FROM usage_event WHERE source = 'claude_code'")]
    expect("ingest_claude: the millisecond record keeps its time; the one with no usable time is skipped",
           len(ts4) == 1 and abs((ts4[0] or 0) - 1792921345.123) < 1e-6 and st4["skipped"] == 1, (ts4, st4))
    con4.execute("INSERT INTO usage_event (source, msg_key, t) VALUES ('claude_code', 'old:1', NULL)")
    con4.commit()
    con4.close()
    con4 = ul.connect(db4)
    left = con4.execute("SELECT COUNT(*) FROM usage_event WHERE t IS NULL").fetchone()[0]
    curs = con4.execute("SELECT COUNT(*) FROM usage_cursor").fetchone()[0]
    expect("connect: rows stored with no time are removed and the cursors reset", left == 0 and curs == 0, (left, curs))
    st5 = ul.ingest_claude(con4, proj)
    con4.close()
    con4 = ul.connect(db4)
    n4 = con4.execute("SELECT COUNT(*) FROM usage_event WHERE source = 'claude_code'").fetchone()[0]
    curs = con4.execute("SELECT COUNT(*) FROM usage_cursor").fetchone()[0]
    expect("after the repair: the file is read again once (no double count) and a clean connect keeps the cursors",
           n4 == 1 and st5["added"] == 0 and curs == 1, (n4, st5, curs))
    con4.close()
finally:
    shutil.rmtree(tmp4, ignore_errors=True)

print("ALL PASSED (simulated)" if not fails else f"{len(fails)} FAILED")
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 -c "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf8').read());print('parse ok')" tests/usage/test_usage_ledger.py
(Select-String -Path tests/usage/test_usage_ledger.py -SimpleMatch '# M78-H4: real Claude Code timestamps').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path tests/usage/test_usage_ledger.py)) -eq 13).Count
```

Expected:

```text
parse ok
1
CR 0
```

If not: record FAIL with the full output and stop this step (R6).

3. `tests/usage/expected.txt` — the ledger suite's count. 1 edit (3a). Expected: the Check output below.

Edit 3a. Find this text (it occurs exactly once):

```text
test_usage_ledger.py 24
```

Replace it with:

```text
test_usage_ledger.py 29
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
Get-Content tests/usage/expected.txt | Select-Object -Last 2
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path tests/usage/expected.txt)) -eq 13).Count
```

Expected:

```text
test_usage_ledger.py 29
test_usage_api.py 4
CR 0
```

If not: record FAIL with the full output and stop this step (R6).

4. `CHANGELOG.md` — version 0.1.14. 1 edit (4a). This file is stored with CRLF line endings: do NOT use your patch tool. Apply the block with the helper (it converts it to CRLF, needs the Find text exactly once, and writes nothing otherwise); the helper's run is the first line of the Check. Expected: the Check output below.

Edit 4a. Find this text (it occurs exactly once):

```text
## [0.1.13] - 2026-10-25
```

Replace it with:

```text
## [0.1.14] - 2026-10-25

### Fixed
- Usage ledger (M78-H4): Claude Code timestamps with milliseconds were not parsed, so every orchestrator row was stored with no time and every window read 0 for Claude Code. They now parse; a record with no usable time is skipped and counted; the rows stored without a time are removed once and re-read (5 new cases, 29 in all).

## [0.1.13] - 2026-10-25
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 D:\Project\Homelab\agent\delegation\tools\apply_edits.py --handover agent/handover/m78/H4-ms-timestamps.md --step 4
(Select-String -Path CHANGELOG.md -Pattern '^## \[0\.1\.14\]').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path CHANGELOG.md)) -eq 13).Count
```

Expected:

```text
applied 1 edit(s) to CHANGELOG.md (CRLF kept)
1
CR 262
```

If not: record FAIL with the output and STOP (never edit the file by hand; never run the helper twice).

5. `D:\Project\Homelab\agent\delegation\tools\mutation_proof.py` — read only: the mutation proof (local bench). The new cases must fail on the base code by assert, each of the 5 mutants must be caught, and the final tree must pass. Paste the whole output with the freeze line. Expected: the Check output below.

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 D:\Project\Homelab\agent\delegation\tools\mutation_proof.py --repo . --base 93b967d8f2ddc0d9260ba081c065d2bc6a41b89a --tests tests/usage/test_usage_ledger.py --mutants agent/handover/m78/src/files/h4-mutants.tsv --run m78-H4 --bench local --paths llm-monitor tests
"exit=$LASTEXITCODE"
```

Expected:

```text
base: test_usage_ledger.py FAIL(5 cases) OK
mutant 1 killed (assert) by test_usage_ledger.py
mutant 2 killed (assert) by test_usage_ledger.py
mutant 3 killed (assert) by test_usage_ledger.py
mutant 4 killed (assert) by test_usage_ledger.py
mutant 5 killed (assert) by test_usage_ledger.py
mutants: 5/5 killed
final: test_usage_ledger.py PASS 29
freeze: tests/usage/test_usage_ledger.py sha256=ad546599a05952d00f054174d9324d754881b80c0be319ee520f50f80bbf1c59
MUTATION PROOF OK
exit=0
```

If not: record FAIL with the whole output and STOP (never change the test, the module or a mutant).

6. `tests/usage/run-tests.py` — read only: both usage suites. Expected: the Check output below.

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 tests/usage/run-tests.py
"rc=$LASTEXITCODE"
```

Expected:

```text
test_usage_api.py            rc=0 pass=4  ALL PASSED (simulated)
test_usage_ledger.py         rc=0 pass=29  ALL PASSED (simulated)
RESULT rc_all=0
rc=0
```

If not: record FAIL with the whole output and STOP.


## Stop rules
- An anchor is not found, or is found more than once: stop that step, NOT RUN with the count, ask in one line.
- Two identical failures: stop that step, NOT RUN with the reason.
- The last step shows any rc other than 0, any FAIL line, or a lower pass count than Expected: stop (no fixes), run the cleanup line, report.

## Do NOT
- Do not commit or push. Do not deploy anything. Do not stop any process by name. Do not touch 8080 or 8081.
- Do not edit files that no step names. Never weaken, skip or delete an existing test or assertion.
- Never run the helper twice on the same step (it would refuse; nothing is written then).
## What to send back
- Receipts: `agent/handover/m78/H4-receipts.md` (new). Write after every step.
- Each step: a heading "### Step N - file - verdict", then the check.ps1 content and its real output in a fenced block.
- At the end: git status --short (expected: the 4 modified files of steps 1-4, plus the receipts file) and a table step / file / verdict.

## Return handoff (when you finish or block)
Append "Return to Claude" to the receipts: every FAIL and NOT RUN, what you noticed but did not change, and questions.
