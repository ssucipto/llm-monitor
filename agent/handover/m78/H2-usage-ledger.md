---
handover_version: 1
handoff_mode: executor
from_executor: claude-opus-5.5
to_executor: strata-iq3s (qwen3.8-flash-next-iq3_s, headless Hermes on 192.168.0.75)
date: 2026-10-25
status: active
tier: T1
git_commit: 2f2aeb893ee2c5b7d6f682fec248b07ca4fb67ba
drift: HEAD is one commit after git_commit; that commit only adds this handover file (check with git diff --stat 2f2aeb8 HEAD). git status --short must be empty before step 1.
---

# Handover M78-H2: usage_ledger.py from three specs (llm-monitor M78, Homelab B-89 T14; tier T1)

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
2. Run git diff --stat 2f2aeb8 HEAD (must list only this handover file) and git status --short (must be empty). If not, stop and ask.
3. Create the receipts file agent/handover/m78/H2-receipts.md with a header: handover path, date, HEAD.
4. This repo is C:\Project\llm-monitor. Run every Check block through
   `powershell -NoProfile -ExecutionPolicy Bypass -File D:\Project\Homelab\agent\delegation\tools\run-check.ps1 -Run m78-H2 -Step N -Check agent/scratch-m78/check.ps1`
   (captures go to D:\Project\Homelab\agent\delegation\runs\m78-H2). Receipts format v2 (D:\Project\Homelab\agent\delegation\EXECUTOR.md).
5. Steps 1-3 are CODE TASKS in one new file: you write the code from the specs. Copy the EXACT lines verbatim (indentation is yours).
Self-review (tier T1): at the end of the receipts, answer each question on its own line, exactly in this form,
with a FILE:LINE reference: `- Q1: no (path/to/file:12)`, `- Q2: no (path/to/file:40)`, `- Q4: no (path/to/file:7)`.
A yes on Q1 or Q2 is a risk flag: write it at the top of the receipts and STOP (B-89 P1 lesson).

## Problem / context
H1 committed the usage ledger's contract (tests/usage/test_usage_ledger.py, 24 cases, synthetic fixtures). H2 writes the module that meets it: storage in its own SQLite file, the Hermes ingest (read-only, numbers only), the Claude Code ingest (byte cursors, dedupe on message id + request id, partial lines wait), and the contract queries. Then the mutation proof shows the tests catch five planted faults in your exact decision lines.

## Locked decisions (do not re-litigate)
- Numbers only: no message text, title or prompt is ever read into the database (the contract's privacy case checks it).
- A read problem is a status, never zeros: a missing or broken Hermes DB is 'missing' or 'error: ...'.
- `python` typed in PowerShell is a silent no-op shim on this PC: use `py -3.12` exactly as the Check blocks do.
- The tests are local (no bastion). This handover changes no running service: the dashboard on 8090 is not touched (that is H3).

## Permission
- Allowed: create and edit only llm-monitor/usage_ledger.py; the receipts file; run the Check commands as written; read any file in this repo and the Homelab files named in Start here; delete agent/scratch-m78.
- Not allowed: the gateway on 8080 and Strata on 8081 (never stop, restart or kill them); the dashboard on 8090 and the scheduled tasks LLMMonitor / LLMMonitorBoot; reading anything under ~/.claude or the Hermes state.db (the tests build their own synthetic data); sudo or elevation; commit or push; editing any other file, above all the test, expected.txt or the mutants.

## Versions
Every version string this handover changes, exactly (the checker refuses any other):
- llm-monitor/usage_ledger.py: """usage_ledger.py v1.0 — the usage ledger: numbers-only token usage of Claude Code and Hermes (M78; Homelab B-89 T14, ADR-022).

## Steps

1. `llm-monitor/usage_ledger.py` (new) — CODE TASK (you write it, from this spec): part A, the module, its storage and the Hermes ingest. Expected: the Check output below.

```text
Create the module (Python 3.12, standard library only: json, os, sqlite3, time, datetime; the style of server.py: a module
docstring, short comments on the why). Its FIRST line is exactly:
    """usage_ledger.py v1.0 — the usage ledger: numbers-only token usage of Claude Code and Hermes (M78; Homelab B-89 T14, ADR-022).
followed by 2-4 docstring lines: what is read (numbers only), what is never read (message text, titles, prompts), where it is stored.
Module constants: EXECUTOR_MODELS = ("strata-iq3_s", "qwen3.8-flash-next-iq3_s") and
WEIGHTS = {"input": 1.0, "cache_write_5m": 1.25, "cache_write_1h": 2.0, "cache_read": 0.1, "output": 5.0}.
• iso(t: float) -> str: UTC, "%Y-%m-%dT%H:%M:%SZ".
• parse_window(frm: str, to: str) -> (float, float): ISO 8601 with a trailing Z; raise ValueError when either does not parse or frm > to.
• connect(path) -> sqlite3.Connection: PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; create if missing:
  usage_event(source TEXT, msg_key TEXT, session TEXT, t REAL, t_end REAL, model TEXT, repo TEXT, sidechain INTEGER, task TEXT,
  input INTEGER, output INTEGER, cache_write INTEGER, cache_write_5m INTEGER, cache_write_1h INTEGER, cache_read INTEGER, reasoning INTEGER),
  usage_cursor(file TEXT PRIMARY KEY, offset INTEGER, mtime REAL), and the index with this EXACT line (any indentation):
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_event ON usage_event(source, msg_key)")
• ingest_hermes(con, db_path) -> {"status": str, "rows": int}:
  - db_path does not exist -> {"status": "missing", "rows": 0};
  - open read-only: sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2);
  - read session_model_usage JOIN sessions ON sessions.id = session_model_usage.session_id: session_id, model, task, first_seen,
    last_seen, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens and coalesce(git_repo_root, cwd).
    Never select title, system_prompt or any other text column;
  - upsert one usage_event row each: source "hermes", msg_key f"{session_id}:{model}:{task}", session = session_id, t = first_seen,
    t_end = last_seen, the counts (cache_write_5m and cache_write_1h = 0); on conflict replace t_end and the counts; commit;
  - sqlite3.OperationalError: "locked" in the message -> {"status": "error: locked", "rows": 0}, otherwise {"status": "error: schema", "rows": 0};
    never raise. Success -> {"status": "ok", "rows": number of rows read}.
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 -c "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf8').read());print('parse ok')" llm-monitor/usage_ledger.py
(Select-String -Path llm-monitor/usage_ledger.py -SimpleMatch 'con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_event ON usage_event(source, msg_key)")').Count
(Select-String -Path llm-monitor/usage_ledger.py -SimpleMatch '"""usage_ledger.py v1.0 — the usage ledger: numbers-only token usage of Claude Code and Hermes (M78; Homelab B-89 T14, ADR-022).').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path llm-monitor/usage_ledger.py)) -eq 13).Count
```

Expected:

```text
parse ok
1
1
CR 0
```

If not: fix the code (at most 3 rounds), then NOT RUN with the output.

2. `llm-monitor/usage_ledger.py` (new) — CODE TASK (you write it, from this spec): part B, the Claude Code ingest. Expected: the Check output below.

```text
Add ingest_claude(con, root, budget_s=5.0) -> {"files", "lines", "added", "skipped", "partial"} (all counts, partial a bool):
• Walk root recursively (os.walk) for files ending in .jsonl; sub-folders hold subagent transcripts.
• Stop starting new files once budget_s seconds (time.monotonic) are used: return with partial True (the cursors keep the place).
• Per file: offset = its usage_cursor row (0 if none); size = os.path.getsize. Use these EXACT lines (any indentation):
    if size < offset:  # rotated or rewritten: read again from 0 (the unique key prevents double counting)
  (and set offset to 0 in its body), read the bytes from offset to the end, then
    end = data.rfind(b"\n") + 1  # only complete lines; a line still being written waits for the next pass
  and only data[:end] is consumed (split into lines; each counts in "lines"). Save offset + end and the mtime as the file's cursor.
• Per line: not JSON -> skipped += 1. JSON with type == "assistant" and a dict message with a usage dict -> INSERT OR IGNORE one
  usage_event row: source "claude_code", msg_key f"{message.id}:{requestId}", session = sessionId, t = the timestamp as epoch
  seconds (parse_window's ISO rule), t_end None, model = message.model, repo = cwd, sidechain = 1 if isSidechain else 0, task None,
  input/output/cache_write/cache_read from input_tokens / output_tokens / cache_creation_input_tokens / cache_read_input_tokens,
  cache_write_5m / cache_write_1h from usage.cache_creation.ephemeral_5m_input_tokens / ephemeral_1h_input_tokens (0 when absent),
  reasoning 0; added += rows actually inserted. Every other line type is ignored (not skipped). Never store any text field.
• Commit at the end.
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 -c "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf8').read());print('parse ok')" llm-monitor/usage_ledger.py
(Select-String -Path llm-monitor/usage_ledger.py -SimpleMatch 'if size < offset:  # rotated or rewritten: read again from 0 (the unique key prevents double counting)').Count
(Select-String -Path llm-monitor/usage_ledger.py -SimpleMatch 'end = data.rfind(b"\n") + 1  # only complete lines; a line still being written waits for the next pass').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path llm-monitor/usage_ledger.py)) -eq 13).Count
```

Expected:

```text
parse ok
1
1
CR 0
```

If not: fix the code (at most 3 rounds), then NOT RUN with the output.

3. `llm-monitor/usage_ledger.py` (new) — CODE TASK (you write it, from this spec): part C, the contract queries; then the contract suite. Expected: the Check output below.

```text
Add norm_repo, summary and sessions:
• norm_repo(p) is exactly (any indentation for the body line):
    def norm_repo(p):
        return (p or "").replace("\\", "/").rstrip("/").lower()
• summary(con, frm, to, repo=None, session=None, status=None, partial=False) -> dict (status None = {}):
  - window = parse_window(frm, to). Orchestrator rows: source "claude_code" with frm <= t <= to. Executor rows: source "hermes",
    model in EXECUTOR_MODELS, t <= to and t_end >= frm. Then, when given: keep rows whose norm_repo(repo) starts with norm_repo(repo
    argument); keep rows whose session equals session.
  - orchestrator block: sums of input, output, cache_write, cache_write_5m, cache_write_1h, cache_read; messages = row count;
    sessions = distinct sessions; models = {model: rows}. Executor block: sums of input, output, cache_write, cache_read, reasoning;
    sessions; models.
  - A block is None when its source's status is not "ok"; for the orchestrator use this EXACT line (any indentation):
        orch = None if status.get("claude_code") != "ok" else orch
    and the same form for the executor with "hermes".
  - weighted: orchestrator = input + 1.25*cache_write_5m + 2.0*cache_write_1h + 1.25*(cache_write - cache_write_5m - cache_write_1h)
    + 0.1*cache_read + 5*output; executor = input + 1.25*cache_write + 0.1*cache_read + 5*output; None for a None block; "weights": WEIGHTS.
  - return {"window": {"from": frm, "to": to}, "orchestrator", "executor", "weighted", "sources": status, "partial": partial,
    "generated_at": iso(time.time())}.
• sessions(con, frm, to, repo=None, session=None) -> list: the same rows and filters, one dict per (role, session): source,
  role ("orchestrator" or "executor"), id, start (iso of the smallest t), end (iso of the largest t_end, else t), model, repo,
  input, output, cache_write, cache_read (sums).
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 -c "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf8').read());print('parse ok')" llm-monitor/usage_ledger.py
(Select-String -Path llm-monitor/usage_ledger.py -SimpleMatch 'return (p or "").replace("\\", "/").rstrip("/").lower()').Count
(Select-String -Path llm-monitor/usage_ledger.py -SimpleMatch 'orch = None if status.get("claude_code") != "ok" else orch').Count
py -3.12 tests/usage/run-tests.py
"rc=$LASTEXITCODE"
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path llm-monitor/usage_ledger.py)) -eq 13).Count
```

Expected:

```text
parse ok
1
1
test_usage_ledger.py         rc=0 pass=24  ALL PASSED (simulated)
RESULT rc_all=0
rc=0
CR 0
```

If not: fix the CODE (at most 3 rounds; never the test), then NOT RUN with the output.

4. `D:\Project\Homelab\agent\delegation\tools\mutation_proof.py` — read only: the mutation proof (local bench; --no-base because the module is new, so the five mutants carry the proof). Paste the whole output with the freeze line. Expected: the Check output below.

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 D:\Project\Homelab\agent\delegation\tools\mutation_proof.py --repo . --base 2f2aeb893ee2c5b7d6f682fec248b07ca4fb67ba --tests tests/usage/test_usage_ledger.py --mutants agent/handover/m78/src/files/h2-mutants.tsv --run m78-H2 --bench local --paths llm-monitor tests --no-base
"exit=$LASTEXITCODE"
```

Expected:

```text
base: test_usage_ledger.py skipped (--no-base: new code, only the mutants prove the tests)
mutant 1 killed (assert) by test_usage_ledger.py
mutant 2 killed (assert) by test_usage_ledger.py
mutant 3 killed (assert) by test_usage_ledger.py
mutant 4 killed (assert) by test_usage_ledger.py
mutant 5 killed (assert) by test_usage_ledger.py
mutants: 5/5 killed
final: test_usage_ledger.py PASS 24
freeze: tests/usage/test_usage_ledger.py sha256=70b40e72b0a5804da3c277f94fed6b5c59ef068fc519f5f76dfbb4027b6cfd93
MUTATION PROOF OK
exit=0
```

If not: record FAIL with the whole output and STOP (never change the test or a mutant).

5. `tests/usage/run-tests.py` — read only: the contract suite twice (a difference is a flake, never a PASS). Expected: the Check output below.

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 tests/usage/run-tests.py
"run1 rc=$LASTEXITCODE"
py -3.12 tests/usage/run-tests.py
"run2 rc=$LASTEXITCODE"
```

Expected:

```text
test_usage_ledger.py         rc=0 pass=24  ALL PASSED (simulated)
RESULT rc_all=0
run1 rc=0
test_usage_ledger.py         rc=0 pass=24  ALL PASSED (simulated)
RESULT rc_all=0
run2 rc=0
```

If not: record FAIL with the full output and stop this step (R6).


## Stop rules
- An anchor is not found, or is found more than once: stop that step, NOT RUN with the count, ask in one line.
- Two identical failures: stop that step, NOT RUN with the reason.
- The last step shows any rc other than 0, any FAIL line, or a lower pass count than Expected: stop (no fixes), run the cleanup line, report.
- A risk flag (Q1 or Q2 yes) means STOP.

## Do NOT
- Do not commit or push. Do not deploy anything. Do not stop any process by name. Do not touch 8080 or 8081.
- Do not edit files that no step names. Never weaken, skip or delete an existing test or assertion.
- Never change the test, expected.txt or the mutants file.
## What to send back
- Receipts: `agent/handover/m78/H2-receipts.md` (new). Write after every step.
- Each step: a heading "### Step N - file - verdict", then the check.ps1 content and its real output in a fenced block.
- At the end: git status --short (expected: the 1 new file llm-monitor/usage_ledger.py, plus the receipts file) and a table step / file / verdict.

## Return handoff (when you finish or block)
Append "Return to Claude" to the receipts: every FAIL and NOT RUN, what you noticed but did not change, and questions.
