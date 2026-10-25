---
handover_version: 1
handoff_mode: executor
from_executor: claude-opus-5.5
to_executor: strata-iq3s (qwen3.8-flash-next-iq3_s, headless Hermes on 192.168.0.75)
date: 2026-10-25
status: active
git_commit: 1f74fd4e4d39298fc5b4743cfb16863a72262b03
drift: HEAD is one commit after git_commit; that commit only adds this handover file (check with git diff --stat 1f74fd4 HEAD). git status --short must be empty before step 1.
---

# Handover M78-H1: the usage ledger's records and its contract (llm-monitor M78, Homelab B-89 T14; tier T0)

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
2. Run git diff --stat 1f74fd4 HEAD (must list only this handover file) and git status --short (must be empty). If not, stop and ask.
3. Create the receipts file agent/handover/m78/H1-receipts.md with a header: handover path, date, HEAD.
4. This repo is C:\Project\llm-monitor. The executor files are in the Homelab repo: run every Check block through
   `powershell -NoProfile -ExecutionPolicy Bypass -File D:\Project\Homelab\agent\delegation\tools\run-check.ps1 -Run m78-H1 -Step N -Check agent/scratch-m78/check.ps1`
   (captures go to D:\Project\Homelab\agent\delegation\runs\m78-H1). Receipts format v2 (D:\Project\Homelab\agent\delegation\EXECUTOR.md).

## Problem / context
Milestone M78 adds a usage ledger to this dashboard: token usage of Claude Code and of Hermes (Strata), numbers only, served on :8090 for the Homelab delegation protocol (ADR-022). H1 lays down the records and the contract: 24 test cases the module in H2 must pass, with synthetic fixtures only (this repo is public). The orchestrator validated the contract against a throwaway reference and checked that each planned mutant is killed.

## Locked decisions (do not re-litigate)
- Exact text only: apply every Find/Replace and Create block verbatim (tier T0).
- The test is the contract: never change it.
- `python` typed in PowerShell is a silent no-op shim on this PC: use `py -3.12` exactly as the Check blocks do.
- This handover changes no running service: the dashboard on 8090 is not restarted (that is H3).

## Permission
- Allowed: edit only the files named in steps 1-5; the receipts file; run the Check commands as written; read any file in this repo and the Homelab files named in Start here; delete agent/scratch-m78.
- Not allowed: the gateway on 8080 and Strata on 8081 (never stop, restart or kill them); the dashboard on 8090 and the scheduled tasks LLMMonitor / LLMMonitorBoot; sudo or elevation; commit or push; editing files no step names; any file in the Homelab repo.

## Steps

1. `agent/milestones/milestone-78-usage-ledger.md` (new) — the M78 milestone. Expected: the Check output below.

Create the file with exactly this content (LF line endings):

```text
# Milestone 78: Usage ledger (token usage of the orchestrator and the local executor)

**Milestone ID**: M78  
**Status**: in progress  
**Priority**: 1  
**Basis**:
- Homelab B-89 T14 (`D:\Project\Homelab\agent\tasks\b89-delegation-protocol\t14-llm-monitor-usage-ledger.md`);
- ADR-022 D-89-1 A' (Homelab `agent/memory/decisions.md`): the monitor measures and the agent reads only the API;
- audits #93/#94 (Homelab, local).

**Executor**: Strata IQ3_S via the Homelab delegation pipeline (`agent/delegation/`), class `readonly-source` (T1 probation); the orchestrator (Claude) writes the specs and contract tests

## Overview

The monitor gains a **usage ledger**: the token usage of the orchestrator (Claude Code) and of the local executor (Hermes running
Strata) per time window, repo and session. It is served on `127.0.0.1:8090` under the Homelab delegation protocol's usage contract
(`agent/design/local.delegated-execution.md` § Metering, in the Homelab repo). The agent never reads transcripts itself; this
dashboard does, and it keeps **numbers only**.

## Objectives

1. `llm-monitor/usage_ledger.py` (new) holds:
   - ingest of Claude Code usage (`~/.claude/projects/**/*.jsonl`, byte cursor, dedupe on message id + request id);
   - ingest of Hermes usage (`%LOCALAPPDATA%\hermes\state.db`, read-only);
   - storage in its own `usage.sqlite3` (WAL, busy timeout);
   - the contract queries `summary()` and `sessions()`.
2. `server.py`:
   - a daemon ingest thread (60 s, ≤ 5 s of work per tick);
   - `GET /api/usage` (a catch-up ingest of ≤ 10 s first, `partial` when it ran out) and `GET /api/usage/sessions`;
   - HTTP 400 on a bad window.
3. A "Usage" panel in the dashboard: today, 7 days, per repo, orchestrator vs executor, and the weighted unit. A missing source shows "unavailable".
4. Tests:
   - `tests/usage/` (stdlib), run by `run-e2e-tests.sh` through `py -3.12`, else `python3`;
   - synthetic fixtures only (public repo);
   - a content-leak test.
5. Lint: M78 handovers are linted with the Homelab vendored lint (`D:/Project/Homelab/agent/delegation/tools/vendor/handover-write/scripts/lint-handover.ps1 -Repo C:/Project/llm-monitor`). This repo's own `agent/scripts/lint-handover.ps1` (M77) checks against the local skill and stays as it is; the Homelab audit #94 PB-04 idea of replacing it would have broken it (it looks for `..\SKILL.md` beside itself).
6. README "Usage ledger" section (what is read, what is never read, where it is stored), CHANGELOG, `.gitignore` for `usage.sqlite3*`.

## Contract (the summary)

    GET /api/usage?from=ISO&to=ISO[&repo=PATH][&session=ID]
    -> {window:{from,to}, orchestrator:{input,output,cache_write,cache_write_5m,cache_write_1h,cache_read,messages,sessions,models}|null,
        executor:{input,output,cache_write,cache_read,reasoning,sessions,models}|null,
        weighted:{orchestrator|null, executor|null, weights:{input:1, cache_write_5m:1.25, cache_write_1h:2.0, cache_read:0.1, output:5}},
        sources:{claude_code:"ok"|"missing"|"error: ...", hermes:...}, partial:bool, generated_at:ISO}
    GET /api/usage/sessions?from&to[&repo][&session] -> [{source, role:"orchestrator"|"executor", id, start, end, model, repo, input, output, cache_write, cache_read}]

## Handovers (`agent/handover/m78/`; generated with the Homelab tools, captures in Homelab `agent/delegation/runs/`)

| # | Steps | Tier |
|---|---|---|
| H1 | records: this milestone, progress.yaml, `.gitignore`; the contract `tests/usage/test_usage_ledger.py` (24 cases), `expected.txt`, `run-tests.py` | T0 (exact text) |
| H2 | `llm-monitor/usage_ledger.py` as 3 CODE TASK steps (A: iso/parse_window/connect/ingest_hermes; B: ingest_claude; C: norm_repo/summary/sessions); mutation proof with 5 mutants (local bench); `run-tests.py` twice | T1 (readonly-source, probation) |
| H3 | `server.py`: ingest thread, `/api/usage`, `/api/usage/sessions` (exact); the Usage panel (exact); `run-e2e-tests.sh` line; README, CHANGELOG; live checks on 8090 after `restart-llm-monitor.ps1` | T0 |

## Acceptance

- The contract suite passes (one PASS per case), and every mutant is killed.
- Live: `/api/usage` for the H19 window gives executor 39576/9461/741458 (the Homelab audit #91 constants).
- Live: one finished Claude session's orchestrator sum equals that session's `/cost` within 2 % (the owner runs `/cost`).
- `/api/stats` p95 latency (20 calls) is unchanged within 20 %.
- The B-88 transcripts (24–25 Oct) are ingested before Claude Code's cleanup removes them (by 2026-11-20).
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
(Select-String -Path agent/milestones/milestone-78-usage-ledger.md -Pattern '^\| H[123] \|').Count
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path agent/milestones/milestone-78-usage-ledger.md)) -eq 13).Count
```

Expected:

```text
3
CR 0
```

If not: record FAIL with the full output and stop this step (R6).

2. `.gitignore` — ignore the usage ledger's SQLite files. 1 edit (2a). Expected: the Check output below.

Edit 2a. Find this text (it occurs exactly once):

```text
llm-monitor/telemetry.sqlite3-shm
```

Replace it with:

```text
llm-monitor/telemetry.sqlite3-shm
# M78 usage ledger (numbers only, machine-local data)
llm-monitor/usage.sqlite3
llm-monitor/usage.sqlite3-journal
llm-monitor/usage.sqlite3-wal
llm-monitor/usage.sqlite3-shm
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
git check-ignore llm-monitor/usage.sqlite3 llm-monitor/usage.sqlite3-wal
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path .gitignore)) -eq 13).Count
```

Expected:

```text
llm-monitor/usage.sqlite3
llm-monitor/usage.sqlite3-wal
CR 0
```

If not: record FAIL with the full output and stop this step (R6).

3. `tests/usage/test_usage_ledger.py` (new) — the usage contract: 24 cases, synthetic fixtures only. It cannot pass yet (usage_ledger.py is H2). Expected: the Check output below.

Create the file with exactly this content (LF line endings):

```text
"""usage_ledger tests (llm-monitor M78, B-89 T14) — SIMULATED: synthetic Claude Code transcripts and a synthetic Hermes
state.db built here with the real column names; no real transcript or DB is read. One PASS line per case.
Run: py -3.12 tests/usage/run-tests.py   (or python3 on Linux)"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "llm-monitor"))
import usage_ledger as ul  # noqa: E402

fails = []


def expect(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -- {str(detail)[:300]}"))
    if not ok:
        fails.append(name)


T0 = 1792890000.0                      # 2026-10-25T00:20:00Z


def iso(t):
    return ul.iso(t)


def msg(mid, rid, t, sess="s1", cwd="D:\\Project\\Homelab", usage=None, model="claude-opus-5-5", text="msg-1", side=False):
    u = usage or {"input_tokens": 10, "output_tokens": 20, "cache_creation_input_tokens": 30, "cache_read_input_tokens": 40,
                  "cache_creation": {"ephemeral_5m_input_tokens": 10, "ephemeral_1h_input_tokens": 20}}
    return json.dumps({"type": "assistant", "timestamp": iso(t), "sessionId": sess, "requestId": rid, "cwd": cwd, "isSidechain": side,
                       "message": {"id": mid, "model": model, "role": "assistant", "content": [{"type": "text", "text": text}], "usage": u}})


def tree():
    root = tempfile.mkdtemp(prefix="m78-claude-")
    p = os.path.join(root, "D--Project-Homelab")
    os.makedirs(os.path.join(p, "s1", "subagents"))
    with open(os.path.join(p, "s1.jsonl"), "w", encoding="utf8", newline="\n") as f:
        f.write(json.dumps({"type": "user", "timestamp": iso(T0), "message": {"role": "user", "content": "msg-0"}}) + "\n")
        for _ in range(3):                                   # one API message written as 3 lines (content blocks)
            f.write(msg("m1", "r1", T0 + 60) + "\n")
        f.write(msg("m2", "r2", T0 + 120) + "\n")
        f.write("not json\n")
        f.write(msg("m3", "r3", T0 + 180, cwd="C:\\Project\\llm-monitor") + "\n")
    with open(os.path.join(p, "s1", "subagents", "a.jsonl"), "w", encoding="utf8", newline="\n") as f:
        f.write(msg("m4", "r4", T0 + 240, side=True) + "\n")
    return root, os.path.join(p, "s1.jsonl")


def hermes_db():
    d = tempfile.mkdtemp(prefix="m78-hermes-")
    p = os.path.join(d, "state.db")
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at REAL, ended_at REAL, cwd TEXT, git_repo_root TEXT, model TEXT,"
              " input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER, title TEXT, system_prompt TEXT)")
    c.execute("CREATE TABLE session_model_usage (session_id TEXT, model TEXT, billing_provider TEXT, billing_base_url TEXT, billing_mode TEXT,"
              " task TEXT, api_call_count INTEGER, input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER,"
              " cache_write_tokens INTEGER, reasoning_tokens INTEGER, estimated_cost_usd REAL, actual_cost_usd REAL, cost_status TEXT,"
              " cost_source TEXT, first_seen REAL, last_seen REAL)")
    c.execute("INSERT INTO sessions VALUES ('20261025_091812_bf2f9d', ?, ?, 'D:\\Project\\Homelab', 'D:\\Project\\Homelab', 'strata-iq3_s', 0, 0, 0, 'secret title', 'secret prompt')", (T0 + 3000, T0 + 3500))
    c.execute("INSERT INTO session_model_usage VALUES ('20261025_091812_bf2f9d', 'strata-iq3_s', 'custom', '', '', '', 27, 39576, 9461, 741458, 0, 0, 0, 0, 'unknown', 'none', ?, ?)", (T0 + 3010, T0 + 3420))
    c.execute("INSERT INTO session_model_usage VALUES ('20261025_091812_bf2f9d', 'qwen3.8-flash-next-iq3_s', 'main', '', '', 'title_generation', 1, 385, 14, 0, 0, 0, 0, 0, NULL, NULL, ?, ?)", (T0 + 3005, T0 + 3005))
    c.execute("INSERT INTO sessions VALUES ('20261025_120000_aaaaaa', ?, ?, 'C:\\Project\\other', NULL, 'strata-iq3_s', 0, 0, 0, 't', 'p')", (T0 + 3100, T0 + 3200))
    c.execute("INSERT INTO session_model_usage VALUES ('20261025_120000_aaaaaa', 'strata-iq3_s', 'custom', '', '', '', 1, 5, 5, 5, 0, 0, 0, 0, NULL, NULL, ?, ?)", (T0 + 3100, T0 + 3200))
    c.commit(); c.close()
    return d, p


tmp = tempfile.mkdtemp(prefix="m78-db-")
db = os.path.join(tmp, "usage.sqlite3")
root, main_file = tree()
hd, hp = hermes_db()
try:
    con = ul.connect(db)
    expect("connect: WAL journal and a busy timeout", con.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal" and con.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000)
    st = ul.ingest_claude(con, root)
    n = con.execute("SELECT COUNT(*) FROM usage_event WHERE source='claude_code'").fetchone()[0]
    expect("Claude: one API message written as 3 lines is counted once (dedupe on message.id + requestId)", n == 4, n)
    expect("Claude: a non-JSON line is skipped and counted", st["skipped"] == 1, st)
    expect("Claude: subagent transcripts in sub-folders are read (sidechain flagged)",
           con.execute("SELECT sidechain FROM usage_event WHERE msg_key LIKE 'm4%'").fetchone() == (1,))
    st2 = ul.ingest_claude(con, root)
    expect("Claude: a second pass reads nothing new (byte cursor)", st2["lines"] == 0 and con.execute("SELECT COUNT(*) FROM usage_event").fetchone()[0] == 4, st2)
    with open(main_file, "a", encoding="utf8", newline="\n") as f:
        f.write(msg("m5", "r5", T0 + 300)[:40])                   # a line still being written (no newline yet)
    ul.ingest_claude(con, root)
    expect("Claude: a partial last line is not consumed", con.execute("SELECT COUNT(*) FROM usage_event").fetchone()[0] == 4)
    with open(main_file, "a", encoding="utf8", newline="\n") as f:
        f.write(msg("m5", "r5", T0 + 300)[40:] + "\n")
    ul.ingest_claude(con, root)
    expect("Claude: the finished line is read on the next pass", con.execute("SELECT COUNT(*) FROM usage_event WHERE msg_key LIKE 'm5%'").fetchone()[0] == 1)
    with open(main_file, "w", encoding="utf8", newline="\n") as f:  # rotated / rewritten shorter than the cursor: an old + a NEW message
        f.write(msg("m2", "r2", T0 + 120) + "\n" + msg("m6", "r6", T0 + 360) + "\n")
    ul.ingest_claude(con, root)
    expect("Claude: a file shorter than its cursor is re-read from 0 (the new message counted, the old one not twice)",
           con.execute("SELECT COUNT(*) FROM usage_event WHERE msg_key LIKE 'm6%'").fetchone()[0] == 1
           and con.execute("SELECT COUNT(*) FROM usage_event WHERE msg_key LIKE 'm2%'").fetchone()[0] == 1)

    hs = ul.ingest_hermes(con, hp)
    expect("Hermes: rows read through a read-only connection; status ok", hs["status"] == "ok" and hs["rows"] == 3, hs)
    hs = ul.ingest_hermes(con, hp)
    expect("Hermes: a second pass upserts (no duplicate rows)", con.execute("SELECT COUNT(*) FROM usage_event WHERE source='hermes'").fetchone()[0] == 3)
    expect("Hermes: a missing state.db -> status missing (never zeros invented)", ul.ingest_hermes(con, os.path.join(hd, "nope.db"))["status"] == "missing")
    bad = os.path.join(hd, "bad.db")
    c = sqlite3.connect(bad); c.execute("CREATE TABLE sessions (id TEXT)"); c.commit(); c.close()
    expect("Hermes: a changed schema -> status 'error: schema', no crash", ul.ingest_hermes(con, bad)["status"].startswith("error: schema"))

    status = {"claude_code": "ok", "hermes": "ok"}
    s = ul.summary(con, iso(T0), iso(T0 + 4000), repo="D:\\Project\\Homelab", status=status)
    for k in ("window", "orchestrator", "executor", "weighted", "sources", "partial", "generated_at"):
        if k not in s:
            break
    expect("summary: every contract key present", all(k in s for k in ("window", "orchestrator", "executor", "weighted", "sources", "partial", "generated_at")), list(s))
    o = s["orchestrator"]
    expect("summary: orchestrator = Claude events of this repo only (llm-monitor's m3 excluded), dedupe kept",
           (o["input"], o["output"], o["sessions"]) == (50, 100, 1), o)
    w = 50 * 1 + 50 * 1.25 + 100 * 2.0 + 200 * 0.1 + 100 * 5
    expect("summary: weighted unit = in + 1.25 cw5m + 2.0 cw1h + 0.1 cr + 5 out", abs(s["weighted"]["orchestrator"] - w) < 1e-6, (s["weighted"], w))
    e = s["executor"]
    expect("summary: executor = Hermes rows of executor models for this repo (H19's numbers, other repo excluded)",
           (e["input"], e["output"], e["cache_read"]) == (39576 + 385, 9461 + 14, 741458), e)
    s2 = ul.summary(con, iso(T0), iso(T0 + 4000), repo="d:/project/homelab", status=status)
    expect("summary: the repo filter is case- and slash-insensitive", s2["orchestrator"]["input"] == 50, s2["orchestrator"])
    s3 = ul.summary(con, iso(T0), iso(T0 + 4000), session="20261025_091812_bf2f9d", status=status)
    expect("summary: ?session= selects that session exactly", s3["executor"]["sessions"] == 1 and s3["executor"]["input"] == 39961, s3["executor"])
    s4 = ul.summary(con, iso(T0 + 9000), iso(T0 + 9999), status=status)
    expect("summary: an empty window gives zeros with sources ok", s4["orchestrator"]["sessions"] == 0 and s4["executor"]["input"] == 0 and s4["sources"] == status, s4)
    s5 = ul.summary(con, iso(T0), iso(T0 + 4000), status={"claude_code": "missing", "hermes": "ok"})
    expect("summary: a missing source gives a null block, not zeros", s5["orchestrator"] is None and s5["weighted"]["orchestrator"] is None, s5)
    rows = ul.sessions(con, iso(T0), iso(T0 + 4000), repo="D:\\Project\\Homelab")
    roles = sorted((r["role"], r["id"]) for r in rows)
    expect("sessions: one row per session with its role", roles == [("executor", "20261025_091812_bf2f9d"), ("orchestrator", "s1")], roles)
    for bad_args in (("2026-10-25T01:00:00Z", "2026-10-25T00:00:00Z"), ("yesterday", "2026-10-25T00:00:00Z")):
        try:
            ul.parse_window(*bad_args)
            expect(f"parse_window refuses {bad_args}", False)
        except ValueError:
            expect(f"parse_window refuses {bad_args}", True)
    dump = "\n".join(str(r) for t in ("usage_event", "usage_cursor") for r in con.execute(f"SELECT * FROM {t}"))
    expect("privacy: no stored value holds message text, a title or a prompt", not any(x in dump for x in ("msg-0", "msg-1", "secret title", "secret prompt", "content")), dump[:300])
    con.close()
finally:
    for d in (tmp, root, hd):
        shutil.rmtree(d, ignore_errors=True)

print("ALL PASSED (simulated)" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 -c "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf8').read());print('parse ok')" tests/usage/test_usage_ledger.py
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path tests/usage/test_usage_ledger.py)) -eq 13).Count
```

Expected:

```text
parse ok
CR 0
```

If not: record FAIL with the full output and stop this step (R6).

4. `tests/usage/expected.txt` (new) — the suite's PASS count. Expected: the Check output below.

Create the file with exactly this content (LF line endings):

```text
# tests/usage suites and their PASS counts (M78). A change in count changes this file in the same commit.
test_usage_ledger.py 24
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
Get-Content tests/usage/expected.txt | Select-Object -Last 1
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path tests/usage/expected.txt)) -eq 13).Count
```

Expected:

```text
test_usage_ledger.py 24
CR 0
```

If not: record FAIL with the full output and stop this step (R6).

5. `tests/usage/run-tests.py` (new) — the runner that enforces the count. Expected: the Check output below.

Create the file with exactly this content (LF line endings):

```text
"""run-tests.py — run every tests/usage suite and enforce its PASS count (M78).

    py -3.12 tests/usage/run-tests.py          (python3 on Linux)
    py -3.12 tests/usage/run-tests.py --list   the suites and their expected counts, nothing run

Each test_*.py in this folder runs with this Python. Its number of lines starting "PASS" must equal tests/usage/expected.txt
(NAME COUNT). A different count, a suite not in expected.txt, a listed suite that did not run, or a non-zero exit fails the
run, and a failing suite prints its last 20 lines. All suites are SIMULATED (synthetic fixtures only; no real transcript).
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def expected():
    out = {}
    for i, ln in enumerate(open(os.path.join(HERE, "expected.txt"), encoding="utf8").read().splitlines(), 1):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        p = s.split()
        if len(p) != 2 or not p[1].isdigit():
            print(f"expected.txt: bad line {i}: {ln!r}")
            sys.exit(1)
        out[p[0]] = int(p[1])
    return out


def main(argv):
    want = expected()
    suites = sorted(f for f in os.listdir(HERE) if re.fullmatch(r"test_\w+\.py", f))
    if argv == ["--list"]:
        for f in suites:
            print(f"{f} expected={want.get(f, 'not listed')}")
        return 0
    rc_all, ran = 0, set()
    for f in suites:
        r = subprocess.run([sys.executable, os.path.join(HERE, f)], capture_output=True, text=True, timeout=600)
        out = (r.stdout + r.stderr).strip().splitlines()
        n = sum(1 for ln in out if ln.startswith("PASS"))
        note = "" if want.get(f) == n else (f"  COUNT got={n} want={want[f]}" if f in want else "  COUNT not in expected.txt")
        print(f"{f:28} rc={r.returncode} pass={n}  {(out or [''])[-1]}{note}")
        if r.returncode != 0 or note:
            rc_all = 1
            for ln in out[-20:]:
                print("    | " + ln)
        ran.add(f)
    for k in want:
        if k not in ran:
            print(f"ABSENT {k}")
            rc_all = 1
    print(f"RESULT rc_all={rc_all}")
    return rc_all


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Check (PowerShell, from the repo root C:\Project\llm-monitor):

```powershell
py -3.12 -c "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf8').read());print('parse ok')" tests/usage/run-tests.py
py -3.12 tests/usage/run-tests.py --list
"CR " + @([IO.File]::ReadAllBytes((Resolve-Path tests/usage/run-tests.py)) -eq 13).Count
```

Expected:

```text
parse ok
test_usage_ledger.py expected=24
CR 0
```

If not: record FAIL with the full output and stop this step (R6).


## Stop rules
- An anchor is not found, or is found more than once: stop that step, NOT RUN with the count, ask in one line.
- Two identical failures: stop that step, NOT RUN with the reason.
- The last step shows any rc other than 0, any FAIL line, or a lower pass count than Expected: stop (no fixes), run the cleanup line, report.

## Do NOT
- Do not commit or push. Do not deploy anything. Do not stop any process by name. Do not touch 8080 or 8081.
- Do not edit files that no step names. Never weaken, skip or delete an existing test or assertion.

## What to send back
- Receipts: `agent/handover/m78/H1-receipts.md` (new). Write after every step.
- Each step: a heading "### Step N - file - verdict", then the check.ps1 content and its real output in a fenced block.
- At the end: git status --short (expected: the 1 modified file and 4 new files of steps 1-5, plus the receipts file) and a table step / file / verdict.

## Return handoff (when you finish or block)
Append "Return to Claude" to the receipts: every FAIL and NOT RUN, what you noticed but did not change, and questions.
