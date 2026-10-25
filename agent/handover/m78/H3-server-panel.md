---
handover_version: 1
handoff_mode: executor
from_executor: claude-opus-5.5
to_executor: strata-iq3s (qwen3.8-flash-next-iq3_s, headless Hermes on 192.168.0.75)
date: 2026-10-25
status: active
git_commit: 5ae30bcd0f1c31ad42cfce0a1f8424d8c5fd4043
drift: HEAD is one commit after git_commit; that commit only adds this handover file (check with git diff --stat 5ae30bc HEAD). git status --short must be empty before step 1.
---

# Handover M78-H3: the usage API, the ingest thread and the Usage panel (llm-monitor M78, Homelab B-89 T14; tier T0)

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
2. Run git diff --stat 5ae30bc HEAD (must list only this handover file) and git status --short (must be empty). If not, stop and ask.
3. Create the receipts file agent/handover/m78/H3-receipts.md with a header: handover path, date, HEAD.
4. This repo is C:\Project\llm-monitor. Run every Check block through
   `powershell -NoProfile -ExecutionPolicy Bypass -File D:\Project\Homelab\agent\delegation\tools\run-check.ps1 -Run m78-H3 -Step N -Check agent/scratch-m78/check.ps1`
   (captures go to D:\Project\Homelab\agent\delegation\runs\m78-H3). Receipts format v2 (D:\Project\Homelab\agent\delegation\EXECUTOR.md).
5. Steps 3-8 edit CRLF files: their blocks are applied ONLY by the helper named in each Check (never your patch tool).

## Problem / context
H2 delivered llm-monitor/usage_ledger.py (contract 24/24, mutants 5/5). H3 wires it into the dashboard exactly as given: a daemon thread ingests every 60 s, /api/usage and /api/usage/sessions answer the Homelab usage contract (a catch-up ingest first; a bad window is HTTP 400), a Usage ledger panel shows today and 7 days, the e2e run includes the usage suites, and the README and CHANGELOG say what is read and what never is. The orchestrator pre-tested every edit on an exported copy.

## Locked decisions (do not re-litigate)
- Exact text only (tier T0). Steps 3-8 go through apply_edits.py because those files are CRLF.
- Numbers only: the usage API never returns message text, titles or prompts.
- `python` typed in PowerShell is a silent no-op shim on this PC: use `py -3.12` exactly as the Check blocks do.
- The live dashboard on 8090 is NOT restarted in this handover: the orchestrator restarts and checks it after verification.

## Permission
- Allowed: create and edit only the files named in steps 1-8 (steps 3-8 only through the helper); the receipts file; run the Check commands as written (the API test starts its own server on 18099 and stops it); delete agent/scratch-m78.
- Not allowed: the gateway on 8080 and Strata on 8081; the dashboard on 8090, restart-llm-monitor.ps1 and the scheduled tasks LLMMonitor / LLMMonitorBoot; reading ~/.claude or the Hermes state.db; sudo or elevation; commit or push; editing any other file.

## Steps

1. `tests/usage/test_usage_api.py` (new) — the API contract: the real server.py on a spare port (18099) with synthetic sources (4 cases). Expected: the Check output below.

Create the file with exactly this content (LF line endings):

```text
"""usage API tests (llm-monitor M78-H3, Homelab B-89 T14) — SIMULATED: the real server.py on a spare port (18099) with synthetic
sources (LLM_MONITOR_* overrides); never the live :8090 dashboard, never a real transcript or state.db. One PASS line per case.
The server is stopped through its own process handle (never by name)."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "..", "..", "llm-monitor", "server.py")
PORT = 18099
fails = []


def expect(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -- {str(detail)[:300]}"))
    if not ok:
        fails.append(name)


def get(path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, None


tmp = tempfile.mkdtemp(prefix="m78-api-")
root = os.path.join(tmp, "projects", "D--Project-Homelab")
os.makedirs(root)
with open(os.path.join(root, "s9.jsonl"), "w", encoding="utf8", newline="\n") as f:
    for i, t in enumerate(("2026-10-25T01:00:10Z", "2026-10-25T01:00:20Z")):
        f.write(json.dumps({"type": "assistant", "timestamp": t, "sessionId": "s9", "requestId": f"r{i}", "cwd": "D:\\Project\\Homelab",
                            "message": {"id": f"m{i}", "model": "claude-opus-5-5", "content": [{"type": "text", "text": "msg-x"}],
                                        "usage": {"input_tokens": 7, "output_tokens": 3, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}}) + "\n")
hdb = os.path.join(tmp, "state.db")
c = sqlite3.connect(hdb)
c.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, cwd TEXT, git_repo_root TEXT, title TEXT)")
c.execute("CREATE TABLE session_model_usage (session_id TEXT, model TEXT, task TEXT, input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER,"
          " cache_write_tokens INTEGER, reasoning_tokens INTEGER, first_seen REAL, last_seen REAL)")
c.execute("INSERT INTO sessions VALUES ('h1', 'D:\\Project\\Homelab', 'D:\\Project\\Homelab', 't')")
c.execute("INSERT INTO session_model_usage VALUES ('h1', 'strata-iq3_s', '', 100, 50, 1000, 0, 0, 1792890000, 1792890600)")
c.commit(); c.close()
env = dict(os.environ, LLM_MONITOR_USAGE_DB=os.path.join(tmp, "usage.sqlite3"), LLM_MONITOR_CLAUDE_ROOT=os.path.join(tmp, "projects"), LLM_MONITOR_HERMES_DB=hdb)
proc = subprocess.Popen([sys.executable, SERVER, str(PORT)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/index.html", timeout=2)
            break
        except OSError:
            time.sleep(0.5)
    W = "from=2026-10-25T00:00:00Z&to=2026-10-25T02:00:00Z&repo=D:/Project/Homelab"
    code, u = get(f"/api/usage?{W}")
    keys = ("window", "orchestrator", "executor", "weighted", "sources", "partial", "generated_at")
    expect("/api/usage: 200 with every contract key and both sources ok", code == 200 and all(k in u for k in keys) and u["sources"] == {"claude_code": "ok", "hermes": "ok"}, (code, u))
    expect("/api/usage: the synthetic numbers (orchestrator 14/6, executor 100/50/1000)",
           code == 200 and (u["orchestrator"]["input"], u["orchestrator"]["output"]) == (14, 6) and (u["executor"]["input"], u["executor"]["output"], u["executor"]["cache_read"]) == (100, 50, 1000), u)
    code, s = get(f"/api/usage/sessions?{W}")
    expect("/api/usage/sessions: one row per session with its role", code == 200 and sorted((r["role"], r["id"]) for r in s) == [("executor", "h1"), ("orchestrator", "s9")], (code, s))
    code, _ = get("/api/usage?from=2026-10-25T02:00:00Z&to=2026-10-25T01:00:00Z")
    expect("/api/usage: a bad window (from after to) is HTTP 400, not data", code == 400, code)
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    shutil.rmtree(tmp, ignore_errors=True)

print("ALL PASSED (simulated)" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 -c "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf8').read());print('parse ok')" tests/usage/test_usage_api.py
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path tests/usage/test_usage_api.py)) -eq 13).Count
```

Expected:

```text
parse ok
CR 0
```

If not: record FAIL with the full output and stop this step (R6).

2. `tests/usage/expected.txt` — the API suite's count. 1 edit (2a). Expected: the Check output below.

Edit 2a. Find this text (it occurs exactly once):

```text
test_usage_ledger.py 24
```

Replace it with:

```text
test_usage_ledger.py 24
test_usage_api.py 4
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
Get-Content tests/usage/expected.txt | Select-Object -Last 2
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path tests/usage/expected.txt)) -eq 13).Count
```

Expected:

```text
test_usage_ledger.py 24
test_usage_api.py 4
CR 0
```

If not: record FAIL with the full output and stop this step (R6).

3. `llm-monitor/server.py` — the ingest thread, the catch-up and the two /api/usage routes. 4 edit(s) (3a–3d). This file is stored with CRLF line endings: do NOT use your patch tool. Apply this step's blocks with the helper (it converts them to CRLF, needs each Find text exactly once, and writes nothing otherwise); the helper's run is the first line of the Check. Expected: the Check output below.

Edit 3a. Find this text (it occurs exactly once):

```text
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
```

Replace it with:

```text
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import usage_ledger
```

Edit 3b. Find this text (it occurs exactly once):

```text
DB_PATH = str(Path(__file__).resolve().with_name("telemetry.sqlite3"))
```

Replace it with:

```text
DB_PATH = str(Path(__file__).resolve().with_name("telemetry.sqlite3"))

# M78 usage ledger (numbers only; README "Usage ledger"): its own SQLite file beside server.py and the two sources it reads.
# The LLM_MONITOR_* overrides exist for the tests (tests/usage/test_usage_api.py builds synthetic sources).
USAGE_DB = os.environ.get("LLM_MONITOR_USAGE_DB") or str(Path(__file__).resolve().with_name("usage.sqlite3"))
CLAUDE_ROOT = os.environ.get("LLM_MONITOR_CLAUDE_ROOT") or str(Path.home() / ".claude" / "projects")
HERMES_DB = os.environ.get("LLM_MONITOR_HERMES_DB") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "hermes", "state.db")
USAGE_STATUS = {"claude_code": "missing", "hermes": "missing"}
_USAGE_LOCK = threading.Lock()


def usage_ingest(budget_s=5.0):
    """One ingest pass (the thread every 60 s, and a catch-up before each /api/usage answer); one writer at a time.
    Returns partial: True when the time budget ran out or the pass failed (the answer then says so)."""
    with _USAGE_LOCK:
        con = None
        try:
            con = usage_ledger.connect(USAGE_DB)
            partial = False
            if os.path.isdir(CLAUDE_ROOT):
                partial = bool(usage_ledger.ingest_claude(con, CLAUDE_ROOT, budget_s).get("partial"))
                USAGE_STATUS["claude_code"] = "ok"
            else:
                USAGE_STATUS["claude_code"] = "missing"
            USAGE_STATUS["hermes"] = usage_ledger.ingest_hermes(con, HERMES_DB)["status"]
            return partial
        except Exception as err:
            print(f"[usage] ingest failed: {err}")
            return True
        finally:
            if con is not None:
                con.close()


def usage_thread():
    """Daemon: ingest every 60 s, so the ledger fills with no dashboard tab open (audit #93 PA-01)."""
    while True:
        usage_ingest(5.0)
        time.sleep(60)
```

Edit 3c. Find this text (it occurs exactly once):

```text
            else:
                super().do_GET()
                return
            self.send_response(200)
```

Replace it with:

```text
            elif path in ("/api/usage", "/api/usage/sessions"):
                qs = urllib.parse.parse_qs(parsed.query)
                q = lambda k: qs.get(k, [None])[0]
                try:
                    usage_ledger.parse_window(q("from") or "", q("to") or "")
                except ValueError as err:
                    self.send_error(400, f"bad window: {err}")
                    return
                partial = usage_ingest(10.0)
                con = usage_ledger.connect(USAGE_DB)
                try:
                    if path == "/api/usage":
                        data = usage_ledger.summary(con, q("from"), q("to"), q("repo"), q("session"), dict(USAGE_STATUS), partial)
                    else:
                        data = usage_ledger.sessions(con, q("from"), q("to"), q("repo"), q("session"))
                finally:
                    con.close()
                body = json.dumps(data).encode()
                ctype = "application/json"
            else:
                super().do_GET()
                return
            self.send_response(200)
```

Edit 3d. Find this text (it occurs exactly once):

```text
    httpd = _Server(("127.0.0.1", port), handler)
```

Replace it with:

```text
    threading.Thread(target=usage_thread, name="usage-ingest", daemon=True).start()
    httpd = _Server(("127.0.0.1", port), handler)
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 D:\Project\Homelab\agent\delegation\tools\apply_edits.py --handover agent/handover/m78/H3-server-panel.md --step 3
py -3.12 -c "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf8').read());print('parse ok')" llm-monitor/server.py
(Select-String -Path llm-monitor/server.py -SimpleMatch 'elif path in ("/api/usage", "/api/usage/sessions"):').Count
(Select-String -Path llm-monitor/server.py -SimpleMatch 'threading.Thread(target=usage_thread').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path llm-monitor/server.py)) -eq 13).Count
```

Expected:

```text
applied 4 edit(s) to llm-monitor/server.py (CRLF kept)
parse ok
1
1
CR 1732
```

If not: record FAIL with the output and STOP (never edit the file by hand; never run the helper twice on a file it changed).

4. `llm-monitor/index.html` — the Usage ledger panel. 1 edit(s) (4a–4a). This file is stored with CRLF line endings: do NOT use your patch tool. Apply this step's blocks with the helper (it converts them to CRLF, needs each Find text exactly once, and writes nothing otherwise); the helper's run is the first line of the Check. Expected: the Check output below.

Edit 4a. Find this text (it occurs exactly once):

```text
    <section class="panel context" id="context" aria-labelledby="context-h">
```

Replace it with:

```text
    <section class="panel usage" id="usage" aria-labelledby="usage-h">
      <h2 id="usage-h">Usage ledger</h2>
      <p class="live__state" id="usage-note">orchestrator (Claude Code) and local executor (Hermes) tokens, numbers only</p>
      <dl class="live__facts">
        <div class="fact"><dt>Today, orchestrator</dt><dd id="usage-day-orch">--</dd></div>
        <div class="fact"><dt>Today, executor</dt><dd id="usage-day-exec">--</dd></div>
        <div class="fact"><dt>7 days, orchestrator</dt><dd id="usage-week-orch">--</dd></div>
        <div class="fact"><dt>7 days, executor</dt><dd id="usage-week-exec">--</dd></div>
        <div class="fact"><dt>Sources</dt><dd id="usage-sources">--</dd></div>
      </dl>
    </section>

    <section class="panel context" id="context" aria-labelledby="context-h">
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 D:\Project\Homelab\agent\delegation\tools\apply_edits.py --handover agent/handover/m78/H3-server-panel.md --step 4
(Select-String -Path llm-monitor/index.html -SimpleMatch 'id="usage-sources"').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path llm-monitor/index.html)) -eq 13).Count
```

Expected:

```text
applied 1 edit(s) to llm-monitor/index.html (CRLF kept)
1
CR 663
```

If not: record FAIL with the output and STOP (never edit the file by hand; never run the helper twice on a file it changed).

5. `llm-monitor/app.js` — fetchUsage and its 60 s timer. 2 edit(s) (5a–5b). This file is stored with CRLF line endings: do NOT use your patch tool. Apply this step's blocks with the helper (it converts them to CRLF, needs each Find text exactly once, and writes nothing otherwise); the helper's run is the first line of the Check. Expected: the Check output below.

Edit 5a. Find this text (it occurs exactly once):

```text
async function init() {
```

Replace it with:

```text
// M78 usage ledger: today and the last 7 days, every 60 s. A missing source says "unavailable", never 0 (honest labels).
const fmtTok = (n) => (n == null ? "unavailable" : n >= 1e6 ? `${(n / 1e6).toFixed(2)} M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)} k` : String(Math.round(n)));
async function fetchUsage() {
  const now = new Date();
  const iso = (d) => d.toISOString().replace(/\.\d{3}Z$/, "Z");
  const day = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const week = new Date(now.getTime() - 7 * 86400000);
  try {
    for (const [key, from] of [["day", day], ["week", week]]) {
      const r = await fetch(`/api/usage?from=${iso(from)}&to=${iso(now)}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const u = await r.json();
      $(`usage-${key}-orch`).textContent = u.weighted.orchestrator == null ? "unavailable" : `${fmtTok(u.weighted.orchestrator)} weighted`;
      $(`usage-${key}-exec`).textContent = u.executor ? `${fmtTok(u.executor.input + u.executor.output)} tokens` : "unavailable";
      $("usage-sources").textContent = `Claude Code ${u.sources.claude_code}, Hermes ${u.sources.hermes}${u.partial ? " (catching up)" : ""}`;
    }
  } catch (err) {
    console.error(err);
    $("usage-sources").textContent = `unavailable (${err.message})`;
  }
}

async function init() {
```

Edit 5b. Find this text (it occurs exactly once):

```text
  fetchTimeseries("1h");
  setInterval(tickClock, 1000);
  setInterval(refresh, REFRESH_MS);
```

Replace it with:

```text
  fetchTimeseries("1h");
  fetchUsage();
  setInterval(tickClock, 1000);
  setInterval(refresh, REFRESH_MS);
  setInterval(fetchUsage, 60000);
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 D:\Project\Homelab\agent\delegation\tools\apply_edits.py --handover agent/handover/m78/H3-server-panel.md --step 5
node --check llm-monitor/app.js; "node-check rc=$LASTEXITCODE"
(Select-String -Path llm-monitor/app.js -SimpleMatch 'setInterval(fetchUsage, 60000);').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path llm-monitor/app.js)) -eq 13).Count
```

Expected:

```text
applied 2 edit(s) to llm-monitor/app.js (CRLF kept)
node-check rc=0
1
CR 1827
```

If not: record FAIL with the output and STOP (never edit the file by hand; never run the helper twice on a file it changed).

6. `run-e2e-tests.sh` — the usage suites in the e2e run. 1 edit(s) (6a–6a). This file is stored with CRLF line endings: do NOT use your patch tool. Apply this step's blocks with the helper (it converts them to CRLF, needs each Find text exactly once, and writes nothing otherwise); the helper's run is the first line of the Check. Expected: the Check output below.

Edit 6a. Find this text (it occurs exactly once):

```text
echo "run-e2e-tests.sh: ${pass} e2e tests passed"
```

Replace it with:

```text
# M78: the usage ledger suites (stdlib; counts enforced by tests/usage/run-tests.py). py on this PC (a bare python is a shim).
if command -v py >/dev/null 2>&1; then PY=(py -3.12); elif command -v python3 >/dev/null 2>&1; then PY=(python3); else
  echo "run-e2e-tests.sh: neither py nor python3 found for tests/usage" >&2; exit 1; fi
"${PY[@]}" "${PROJECT_ROOT}/tests/usage/run-tests.py"
pass=$((pass + 1))

echo "run-e2e-tests.sh: ${pass} e2e tests passed"
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 D:\Project\Homelab\agent\delegation\tools\apply_edits.py --handover agent/handover/m78/H3-server-panel.md --step 6
(Select-String -Path run-e2e-tests.sh -SimpleMatch 'tests/usage/run-tests.py"').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path run-e2e-tests.sh)) -eq 13).Count
```

Expected:

```text
applied 1 edit(s) to run-e2e-tests.sh (CRLF kept)
1
CR 37
```

If not: record FAIL with the output and STOP (never edit the file by hand; never run the helper twice on a file it changed).

7. `llm-monitor/README.md` — the Usage ledger section. 1 edit(s) (7a–7a). This file is stored with CRLF line endings: do NOT use your patch tool. Apply this step's blocks with the helper (it converts them to CRLF, needs each Find text exactly once, and writes nothing otherwise); the helper's run is the first line of the Check. Expected: the Check output below.

Edit 7a. Find this text (it occurs exactly once):

```text
## Configuration
```

Replace it with:

```text
## Usage ledger

Token usage of the orchestrator (Claude Code) and of the local executor (Hermes running Strata), per time window, repo and
session, for the Homelab delegation protocol (milestone M78; Homelab ADR-022).

- **What is read:** `%USERPROFILE%\.claude\projects\**\*.jsonl` (only the `assistant` lines' ids, timestamps, model, working
  folder and the four token counts) and `%LOCALAPPDATA%\hermes\state.db` (read-only: per-session model usage and the repo folder).
- **What is never read or stored:** message text, titles, prompts, tool output.
- **Where:** `llm-monitor/usage.sqlite3` (gitignored, its own file beside the telemetry DB). A thread ingests every 60 s, and
  every `/api/usage` call catches up first (at most 10 s; `partial: true` if it ran out).
- **API:** `GET /api/usage?from=ISO&to=ISO[&repo=PATH][&session=ID]` (totals, a cost-weighted unit, source status) and
  `GET /api/usage/sessions?...` (one row per session and role). A bad window is HTTP 400; a missing source is `null`, never 0.
- **Tests:** `py -3.12 tests/usage/run-tests.py` (synthetic data only; `run-e2e-tests.sh` runs it).

## Configuration
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 D:\Project\Homelab\agent\delegation\tools\apply_edits.py --handover agent/handover/m78/H3-server-panel.md --step 7
(Select-String -Path llm-monitor/README.md -Pattern '^## Usage ledger').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path llm-monitor/README.md)) -eq 13).Count
```

Expected:

```text
applied 1 edit(s) to llm-monitor/README.md (CRLF kept)
1
CR 259
```

If not: record FAIL with the output and STOP (never edit the file by hand; never run the helper twice on a file it changed).

8. `CHANGELOG.md` — version 0.1.13. 1 edit(s) (8a–8a). This file is stored with CRLF line endings: do NOT use your patch tool. Apply this step's blocks with the helper (it converts them to CRLF, needs each Find text exactly once, and writes nothing otherwise); the helper's run is the first line of the Check. Expected: the Check output below.

Edit 8a. Find this text (it occurs exactly once):

```text
## [0.1.12] - 2026-10-17
```

Replace it with:

```text
## [0.1.13] - 2026-10-25

### Added
- Usage ledger (M78): `usage_ledger.py` ingests numbers-only token usage of Claude Code and Hermes into `usage.sqlite3`; `/api/usage` and `/api/usage/sessions` serve it; a background thread ingests every 60 s; a "Usage ledger" panel shows today and 7 days. Built through the Homelab delegation pipeline (Strata IQ3_S writing from specs; contract 24 + API 4 cases, mutation proof 5/5).

## [0.1.12] - 2026-10-17
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 D:\Project\Homelab\agent\delegation\tools\apply_edits.py --handover agent/handover/m78/H3-server-panel.md --step 8
(Select-String -Path CHANGELOG.md -Pattern '^## \[0\.1\.13\]').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path CHANGELOG.md)) -eq 13).Count
```

Expected:

```text
applied 1 edit(s) to CHANGELOG.md (CRLF kept)
1
CR 257
```

If not: record FAIL with the output and STOP (never edit the file by hand; never run the helper twice on a file it changed).

9. `run-e2e-tests.sh` — read only: the usage suites, then the whole e2e run. Expected: the Check output below.

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 tests/usage/run-tests.py
"rc=$LASTEXITCODE"
& "C:\Program Files\Git\bin\bash.exe" run-e2e-tests.sh 2>&1 | Select-Object -Last 1
"e2e rc=$LASTEXITCODE"
```

Expected:

```text
test_usage_api.py            rc=0 pass=4  ALL PASSED (simulated)
test_usage_ledger.py         rc=0 pass=24  ALL PASSED (simulated)
RESULT rc_all=0
rc=0
run-e2e-tests.sh: 3 e2e tests passed
e2e rc=0
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
- Receipts: `agent/handover/m78/H3-receipts.md` (new). Write after every step.
- Each step: a heading "### Step N - file - verdict", then the check.ps1 content and its real output in a fenced block.
- At the end: git status --short (expected: the 7 modified files and 1 new file of steps 1-8, plus the receipts file) and a table step / file / verdict.

## Return handoff (when you finish or block)
Append "Return to Claude" to the receipts: every FAIL and NOT RUN, what you noticed but did not change, and questions.
