---
handover_version: 1
handoff_mode: executor
from_executor: claude-opus-5.5
to_executor: strata-iq3s (qwen3.8-flash-next-iq3_s, headless Hermes on 192.168.0.75)
date: 2026-10-25
status: active
git_commit: 825e6f14c613929d77349ec962b893027bce7dd0
drift: HEAD is one commit after git_commit; that commit only adds this handover file (check with git diff --stat 825e6f1 HEAD). git status --short must be empty before step 1.
---

# Handover M78-H5: executor models, repo boundary, a stable API test, and CI (llm-monitor M78, Homelab B-89 T13; tier T0)

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
2. Run git diff --stat 825e6f1 HEAD (must list only this handover file) and git status --short (must be empty). If not, stop and ask.
3. Create the receipts file agent/handover/m78/H5-receipts.md with a header: handover path, date, HEAD.
4. This repo is C:\Project\llm-monitor. Run every Check block through
   `powershell -NoProfile -ExecutionPolicy Bypass -File D:\Project\Homelab\agent\delegation\tools\run-check.ps1 -Run m78-H5 -Step N -Check agent/scratch-m78/check.ps1`
   (captures go to D:\Project\Homelab\agent\delegation\runs\m78-H5). Receipts format v2 (D:\Project\Homelab\agent\delegation\EXECUTOR.md).
5. Steps 1-4 are LF files: apply their blocks exactly. Step 5 is a new file. Steps 6-7 are CRLF: only the helper named in each Check applies them.

## Problem / context
Homelab's post-implementation review found three things in the usage ledger: the executor was recognised by two hard-coded model names (a new quant would read as executor 0 with Hermes 'ok'); the repo filter was a bare prefix (llm-monitor-old matched llm-monitor); and llm-monitor had no CI. While pre-testing the CI on Ubuntu, the API test failed every second run: it bound the fixed port 18099, and Linux keeps the last run's sockets in TIME_WAIT for about a minute (the server turns address reuse off on purpose). H5 fixes all four exactly as given; the orchestrator pre-tested every edit on an exported copy (33 + 5 cases, the new cases fail on the base by assert, 4/4 mutants caught) and the CI steps twice in a row on Ubuntu.

## Locked decisions (do not re-litigate)
- Exact text only (tier T0). Steps 6-7 go through apply_edits.py because those files are CRLF.
- Numbers only: no change reads message text.
- `python` typed in PowerShell is a silent no-op shim on this PC: use `py -3.12` exactly as the Check blocks do.
- No e2e run in this handover (run-e2e-tests.sh): the orchestrator runs it after verification.
- The live dashboard on 8090 is NOT restarted here: the orchestrator restarts and checks it after verification.

## Permission
- Allowed: edit only the files named in steps 1-7 (steps 6-7 only through the helper); create the file of step 5; the receipts file; run the Check commands as written (the API test starts its own server on a free port and stops it; the mutation proof builds its own temp trees); delete agent/scratch-m78.
- Not allowed: the gateway on 8080 and Strata on 8081; the dashboard on 8090, restart-llm-monitor.ps1 and the scheduled tasks LLMMonitor / LLMMonitorBoot; llm-monitor/usage.sqlite3; reading ~/.claude or the Hermes state.db; sudo or elevation; commit or push; editing any other file.

## Steps

1. `llm-monitor/usage_ledger.py` — executor models from LLM_MONITOR_EXECUTOR_MODELS and named in the answer; the repo filter at a path boundary. 5 edits (1a-1e). Expected: the Check output below.

Edit 1a. Find this text (it occurs exactly once):

```text
Storage: its own SQLite file (usage_event rows + usage_cursor byte cursors), WAL so the dashboard can read while we write."""
```

Replace it with:

```text
Storage: its own SQLite file (usage_event rows + usage_cursor byte cursors), WAL so the dashboard can read while we write.
v1.1 (M78-H5, Homelab review-043 CR-009/CR-011): LLM_MONITOR_EXECUTOR_MODELS sets the executor models and /api/usage names
them (executor_models); the repo filter stops at a path boundary."""
```

Edit 1b. Find this text (it occurs exactly once):

```text
# the models that run executors: their Hermes rows are executor usage, not orchestrator usage
EXECUTOR_MODELS = ("strata-iq3_s", "qwen3.8-flash-next-iq3_s")
```

Replace it with:

```text
# the models that run executors: their Hermes rows are executor usage, not orchestrator usage. A new quant or model name
# goes in LLM_MONITOR_EXECUTOR_MODELS (comma-separated); otherwise it would read as executor 0 with Hermes "ok" (M78-H5)
EXECUTOR_MODELS = tuple(m.strip() for m in (os.environ.get("LLM_MONITOR_EXECUTOR_MODELS")
                                            or "strata-iq3_s,qwen3.8-flash-next-iq3_s").split(",") if m.strip())
```

Edit 1c. Find this text (it occurs exactly once):

```text
            if repo is not None and not norm_repo(r[6]).startswith(norm_repo(repo)):  # repo column
```

Replace it with:

```text
            want = norm_repo(repo) if repo is not None else None
            if want is not None and not (norm_repo(r[6]) == want or norm_repo(r[6]).startswith(want + "/")):  # a path boundary (M78-H5)
```

Edit 1d. Find this text (it occurs exactly once):

```text
    ex = keep(con.execute("SELECT * FROM usage_event WHERE source='hermes' AND model IN (?,?) AND t <= ? AND t_end >= ?",
                          (EXECUTOR_MODELS[0], EXECUTOR_MODELS[1], t, f)).fetchall())
```

Replace it with:

```text
    ms = tuple(EXECUTOR_MODELS)
    ex = keep(con.execute("SELECT * FROM usage_event WHERE source='hermes' AND model IN (%s) AND t <= ? AND t_end >= ?"
                          % ",".join("?" * len(ms)), (*ms, t, f)).fetchall()) if ms else []
```

Edit 1e. Find this text (it occurs exactly once):

```text
            "sources": status, "partial": partial, "generated_at": iso(time.time())}
```

Replace it with:

```text
            "sources": status, "partial": partial, "generated_at": iso(time.time()),
            "executor_models": list(EXECUTOR_MODELS)}   # additive (M78-H5): what counts as executor usage
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 -c "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf8').read());print('parse ok')" llm-monitor/usage_ledger.py
(Select-String -Path llm-monitor/usage_ledger.py -SimpleMatch 'ms = tuple(EXECUTOR_MODELS)').Count
(Select-String -Path llm-monitor/usage_ledger.py -SimpleMatch '"executor_models": list(EXECUTOR_MODELS)}').Count
(Select-String -Path llm-monitor/usage_ledger.py -SimpleMatch 'startswith(want + "/")').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path llm-monitor/usage_ledger.py)) -eq 13).Count
```

Expected:

```text
parse ok
1
1
1
CR 0
```

If not: record FAIL with the full output and stop this step (R6).

2. `tests/usage/test_usage_ledger.py` — 4 contract cases for H5. 2 edits (2a-2b). Expected: the Check output below.

Edit 2a. Find this text (it occurs exactly once):

```text
import sqlite3
import sys
import tempfile
```

Replace it with:

```text
import sqlite3
import subprocess
import sys
import tempfile
```

Edit 2b. Find this text (it occurs exactly once):

```text
print("ALL PASSED (simulated)" if not fails else f"{len(fails)} FAILED")
```

Replace it with:

```text
# M78-H5: the executor model list can be set (a new quant must not read as 0), and the repo filter stops at a path boundary
tmp5 = tempfile.mkdtemp(prefix="m78-h5-")
try:
    con5 = ul.connect(os.path.join(tmp5, "u.sqlite3"))
    row = ("INSERT INTO usage_event (source, msg_key, session, t, t_end, model, repo, sidechain, task, input, output, cache_write,"
           " cache_write_5m, cache_write_1h, cache_read, reasoning) VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, 0, 0, 0, 0, 0, 0)")
    con5.execute(row, ("hermes", "h5a", "e1", T0 + 10, T0 + 20, "strata-q4", "C:\\Project\\llm-monitor", 7))
    con5.execute(row, ("claude_code", "c5a", "o1", T0 + 10, None, "claude-opus-5-5", "C:\\Project\\llm-monitor-old", 11))
    con5.execute(row, ("claude_code", "c5b", "o2", T0 + 11, None, "claude-opus-5-5", "C:\\Project\\llm-monitor\\sub", 13))
    con5.commit()
    ok5 = {"claude_code": "ok", "hermes": "ok"}
    s5 = ul.summary(con5, iso(T0), iso(T0 + 60), repo="C:\\Project\\llm-monitor", status=ok5)
    expect("a model outside the executor list is not executor usage; the answer names the list (executor_models)",
           s5["executor"]["input"] == 0 and s5.get("executor_models") == list(ul.EXECUTOR_MODELS), s5)
    saved5 = ul.EXECUTOR_MODELS
    ul.EXECUTOR_MODELS = ("strata-q4",)
    try:
        s5 = ul.summary(con5, iso(T0), iso(T0 + 60), repo="C:\\Project\\llm-monitor", status=ok5)
    finally:
        ul.EXECUTOR_MODELS = saved5
    expect("a configured executor model counts (a new quant is not a silent 0)", s5["executor"]["input"] == 7 and s5.get("executor_models") == ["strata-q4"], s5)
    expect("the repo filter stops at a path boundary: a sibling '-old' folder is out, a subfolder is in", s5["orchestrator"]["input"] == 13, s5["orchestrator"])
    con5.close()
    env5 = dict(os.environ, LLM_MONITOR_EXECUTOR_MODELS=" a-model , b-model ")
    r5 = subprocess.run([sys.executable, "-c", "import usage_ledger as u; print(u.EXECUTOR_MODELS)"],
                        cwd=os.path.join(HERE, "..", "..", "llm-monitor"), env=env5, capture_output=True, text=True)
    expect("LLM_MONITOR_EXECUTOR_MODELS sets the list (comma-separated, trimmed)", r5.stdout.strip() == "('a-model', 'b-model')", r5.stdout + r5.stderr)
finally:
    shutil.rmtree(tmp5, ignore_errors=True)

print("ALL PASSED (simulated)" if not fails else f"{len(fails)} FAILED")
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 -c "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf8').read());print('parse ok')" tests/usage/test_usage_ledger.py
(Select-String -Path tests/usage/test_usage_ledger.py -SimpleMatch '# M78-H5: the executor model list can be set').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path tests/usage/test_usage_ledger.py)) -eq 13).Count
```

Expected:

```text
parse ok
1
CR 0
```

If not: record FAIL with the full output and stop this step (R6).

3. `tests/usage/test_usage_api.py` — the API test takes a free port and checks the server came up. 5 edits (3a-3e). Expected: the Check output below.

Edit 3a. Find this text (it occurs exactly once):

```text
"""usage API tests (llm-monitor M78-H3, Homelab B-89 T14) — SIMULATED: the real server.py on a spare port (18099) with synthetic
```

Replace it with:

```text
"""usage API tests (llm-monitor M78-H3/H5, Homelab B-89 T14) — SIMULATED: the real server.py on a free port the OS gives with synthetic
```

Edit 3b. Find this text (it occurs exactly once):

```text
import shutil
import sqlite3
```

Replace it with:

```text
import shutil
import socket
import sqlite3
```

Edit 3c. Find this text (it occurs exactly once):

```text
PORT = 18099
```

Replace it with:

```text


def free_port():
    """A port nothing holds now (a fixed one can sit in TIME_WAIT after a run a minute ago: M78-H5)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()
```

Edit 3d. Find this text (it occurs exactly once):

```text
proc = subprocess.Popen([sys.executable, SERVER, str(PORT)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
```

Replace it with:

```text
errf = os.path.join(tmp, "server.err")
proc = subprocess.Popen([sys.executable, SERVER, str(PORT)], env=env, stdout=subprocess.DEVNULL, stderr=open(errf, "w"))
```

Edit 3e. Find this text (it occurs exactly once):

```text
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/index.html", timeout=2)
            break
        except OSError:
            time.sleep(0.5)
```

Replace it with:

```text
    up = False
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/index.html", timeout=2)
            up = True
            break
        except OSError:
            time.sleep(0.5)
    expect("the server under test answers within 30 s (else its stderr is shown)", up,
           open(errf, encoding="utf8", errors="replace").read()[-600:])
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 -c "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf8').read());print('parse ok')" tests/usage/test_usage_api.py
(Select-String -Path tests/usage/test_usage_api.py -SimpleMatch 'PORT = free_port()').Count
(Select-String -Path tests/usage/test_usage_api.py -SimpleMatch 'PORT = 18099').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path tests/usage/test_usage_api.py)) -eq 13).Count
```

Expected:

```text
parse ok
1
0
CR 0
```

If not: record FAIL with the full output and stop this step (R6).

4. `tests/usage/expected.txt` — the two suites' counts. 1 edit (4a). Expected: the Check output below.

Edit 4a. Find this text (it occurs exactly once):

```text
test_usage_ledger.py 29
test_usage_api.py 4
```

Replace it with:

```text
test_usage_ledger.py 33
test_usage_api.py 5
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
Get-Content tests/usage/expected.txt | Select-Object -Last 2
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path tests/usage/expected.txt)) -eq 13).Count
```

Expected:

```text
test_usage_ledger.py 33
test_usage_api.py 5
CR 0
```

If not: record FAIL with the full output and stop this step (R6).

5. `.github/workflows/usage-tests.yml` (new) — llm-monitor's CI: the usage suites and the e2e gates on every push. Expected: the Check output below.

Create the file with exactly this content (LF line endings):

```text
# usage-tests — llm-monitor's own regression net (M78-H5; Homelab audit #95 F-02: the meter every B-89 number comes from had
# no CI). Runs the usage suites (counts enforced by tests/usage/run-tests.py) and the e2e gates on every push. SIMULATED only:
# synthetic transcripts and a synthetic Hermes DB; nothing real is read, nothing leaves the runner.
name: usage-tests
on:
  push:
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  tests:
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Usage suites, counts enforced
        run: python3 tests/usage/run-tests.py
      - name: Shell scripts with LF line ends (this runner's checkout only)
        # the repo stores its .sh files with CRLF (Git Bash on Windows accepts that, bash on Linux does not); the files in
        # the repo are not changed
        run: git ls-files -z '*.sh' | xargs -0 sed -i 's/\r$//'
      - name: The e2e gates (integrity v1 and v2, usage)
        run: bash run-e2e-tests.sh
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 -c "import yaml,sys;d=yaml.safe_load(open(sys.argv[1],encoding='utf8'));j=d['jobs']['tests'];print(j['runs-on']);[print(s.get('name') or s.get('uses')) for s in j['steps']]" .github/workflows/usage-tests.yml
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path .github/workflows/usage-tests.yml)) -eq 13).Count
```

Expected:

```text
ubuntu-24.04
actions/checkout@v4
actions/setup-python@v5
Usage suites, counts enforced
Shell scripts with LF line ends (this runner's checkout only)
The e2e gates (integrity v1 and v2, usage)
CR 0
```

If not: record FAIL with the full output and stop this step (R6).

6. `llm-monitor/README.md` — the executor-model setting and the CI. 1 edit (6a). This file is stored with CRLF line endings: do NOT use your patch tool. Apply the block with the helper (it converts it to CRLF, needs the Find text exactly once, and writes nothing otherwise); the helper's run is the first line of the Check. Expected: the Check output below.

Edit 6a. Find this text (it occurs exactly once):

```text
- **Tests:** `py -3.12 tests/usage/run-tests.py` (synthetic data only; `run-e2e-tests.sh` runs it).
```

Replace it with:

```text
- **Executor models:** Hermes rows count as executor usage only for the models in `LLM_MONITOR_EXECUTOR_MODELS`
  (comma-separated; default `strata-iq3_s,qwen3.8-flash-next-iq3_s`); `/api/usage` names them in `executor_models`.
- **Tests:** `py -3.12 tests/usage/run-tests.py` (synthetic data only; `run-e2e-tests.sh` runs it; CI: `usage-tests.yml`).
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 D:\Project\Homelab\agent\delegation\tools\apply_edits.py --handover agent/handover/m78/H5-models-ci.md --step 6
(Select-String -Path llm-monitor/README.md -SimpleMatch 'LLM_MONITOR_EXECUTOR_MODELS').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path llm-monitor/README.md)) -eq 13).Count
```

Expected:

```text
applied 1 edit(s) to llm-monitor/README.md (CRLF kept)
1
CR 261
```

If not: record FAIL with the output and STOP (never edit the file by hand; never run the helper twice).

7. `CHANGELOG.md` — version 0.1.15. 1 edit (7a). This file is stored with CRLF line endings: do NOT use your patch tool. Apply the block with the helper (it converts it to CRLF, needs the Find text exactly once, and writes nothing otherwise); the helper's run is the first line of the Check. Expected: the Check output below.

Edit 7a. Find this text (it occurs exactly once):

```text
## [0.1.14] - 2026-10-25
```

Replace it with:

```text
## [0.1.15] - 2026-10-25

### Fixed
- Usage ledger (M78-H5): the executor models are set by `LLM_MONITOR_EXECUTOR_MODELS` and named in `/api/usage` (`executor_models`), so a new quant no longer reads as executor 0; the repo filter stops at a path boundary (`llm-monitor-old` no longer matches `llm-monitor`). 4 new cases, 33 in all. The API test takes a free port (a fixed one failed a second run within a minute on Linux: TIME_WAIT) and checks the server came up.

### Added
- CI: `usage-tests.yml` runs the usage suites and the e2e gates on every push.

## [0.1.14] - 2026-10-25
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 D:\Project\Homelab\agent\delegation\tools\apply_edits.py --handover agent/handover/m78/H5-models-ci.md --step 7
(Select-String -Path CHANGELOG.md -Pattern '^## \[0\.1\.15\]').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path CHANGELOG.md)) -eq 13).Count
```

Expected:

```text
applied 1 edit(s) to CHANGELOG.md (CRLF kept)
1
CR 270
```

If not: record FAIL with the output and STOP (never edit the file by hand; never run the helper twice).

8. `D:\Project\Homelab\agent\delegation\tools\mutation_proof.py` — read only: the new cases must fail on the base code by assert, catch 4 planted faults, and pass on the final tree (local bench). Paste the whole output with the freeze line. Expected: the Check output below.

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 D:\Project\Homelab\agent\delegation\tools\mutation_proof.py --repo . --base 825e6f14c613929d77349ec962b893027bce7dd0 --tests tests/usage/test_usage_ledger.py --mutants agent/handover/m78/src/files/h5-mutants.tsv --run m78-H5 --bench local --paths llm-monitor tests
"exit=$LASTEXITCODE"
```

Expected:

```text
base: test_usage_ledger.py FAIL(1 cases) OK
mutant 1 killed (assert) by test_usage_ledger.py
mutant 2 killed (assert) by test_usage_ledger.py
mutant 3 killed (assert) by test_usage_ledger.py
mutant 4 killed (assert) by test_usage_ledger.py
mutants: 4/4 killed
final: test_usage_ledger.py PASS 33
freeze: tests/usage/test_usage_ledger.py sha256=7d2a7a397c8fbf1d0c0883aec4789ffb9c37fe8735fef528967facde5e2c6d67
MUTATION PROOF OK
exit=0
```

If not: record FAIL with the whole output and STOP (never change the test, the module or a mutant).

9. `tests/usage/run-tests.py` — read only: both usage suites, twice (a second run right after the first is what failed before). Expected: the Check output below.

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 tests/usage/run-tests.py
"rc=$LASTEXITCODE"
py -3.12 tests/usage/run-tests.py
"rc=$LASTEXITCODE"
```

Expected:

```text
test_usage_api.py            rc=0 pass=5  ALL PASSED (simulated)
test_usage_ledger.py         rc=0 pass=33  ALL PASSED (simulated)
RESULT rc_all=0
rc=0
test_usage_api.py            rc=0 pass=5  ALL PASSED (simulated)
test_usage_ledger.py         rc=0 pass=33  ALL PASSED (simulated)
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
- Receipts: `agent/handover/m78/H5-receipts.md` (new). Write after every step.
- Each step: a heading "### Step N - file - verdict", then the check.ps1 content and its real output in a fenced block.
- At the end: git status --short (expected: the 6 modified files and 1 new file of steps 1-7, plus the receipts file) and a table step / file / verdict.

## Return handoff (when you finish or block)
Append "Return to Claude" to the receipts: every FAIL and NOT RUN, what you noticed but did not change, and questions.
