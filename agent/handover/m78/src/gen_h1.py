"""Generate M78 handover H1 (records + the usage contract; tier T0) with the Homelab delegation tools (B-89 T14).
    py -3.12 agent/handover/m78/src/gen_h1.py        (from C:\\Project\\llm-monitor)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
HOMELAB = "D:/Project/Homelab"
sys.path.insert(0, HOMELAB + "/agent/delegation/tools")
import hgen  # noqa: E402
from hgen import CR, PARSE, check, doc, edits, head_commit, newfile  # noqa: E402

hgen.ROOT_LABEL = "C:" + hgen.BS + "Project" + hgen.BS + "llm-monitor"
FILES = os.path.join(HERE, "files")
rd = lambda f: open(os.path.join(FILES, f), encoding="utf8").read()
head, short = head_commit(REPO)
RUN = "m78-H1"
RUNCHECK = "D:" + hgen.BS + "Project" + hgen.BS + "Homelab" + hgen.BS + "agent" + hgen.BS + "delegation" + hgen.BS + "tools" + hgen.BS + "run-check.ps1"

MS, GI, TEST, EXP, RT, PROG = ("agent/milestones/milestone-78-usage-ledger.md", ".gitignore", "tests/usage/test_usage_ledger.py",
                                "tests/usage/expected.txt", "tests/usage/run-tests.py", "agent/progress.yaml")
GI_EDIT = [("llm-monitor/telemetry.sqlite3-shm\n",
            "llm-monitor/telemetry.sqlite3-shm\n# M78 usage ledger (numbers only, machine-local data)\nllm-monitor/usage.sqlite3\nllm-monitor/usage.sqlite3-journal\n"
            "llm-monitor/usage.sqlite3-wal\nllm-monitor/usage.sqlite3-shm\n")]
M78_MS = """  - id: M78
    name: Usage ledger (orchestrator and executor tokens)
    priority: 1
    file: agent/milestones/milestone-78-usage-ledger.md
    status: in_progress
    progress: 10
    started: 2026-10-25
    estimated_weeks: 1
    tasks_completed: 0
    tasks_total: 3
    notes: |
      Homelab B-89 T14 (ADR-022 D-89-1 A'): numbers-only token usage of Claude Code and Hermes, served as /api/usage on :8090.
      Executed through the Homelab delegation pipeline (Strata IQ3_S): H1 records + contract, H2 the module (T1), H3 server + panel.

"""
M78_TASKS = """  milestone_78:
    - id: task-78-h1
      name: Records and the usage contract (24 cases)
      priority: 1
      status: in_progress
      started: 2026-10-25
      file: agent/milestones/milestone-78-usage-ledger.md
    - id: task-78-h2
      name: usage_ledger.py (ingest, storage, contract queries)
      priority: 1
      status: pending
      file: agent/milestones/milestone-78-usage-ledger.md
    - id: task-78-h3
      name: server routes, ingest thread, Usage panel, docs, live checks
      priority: 1
      status: pending
      file: agent/milestones/milestone-78-usage-ledger.md

"""
# progress.yaml is CRLF in the index: the orchestrator records M78 there itself (an LF Find block cannot match).
PROG_EDITS = [("active_handoff:\n  path: agent/reports/handoff-zed-audit27-verification-2026-10-17.md\n",
               M78_MS + "active_handoff:\n  path: agent/reports/handoff-zed-audit27-verification-2026-10-17.md\n"),
              ("# Documentation tracking\n", M78_TASKS + "# Documentation tracking\n")]

steps = [
    f"1. `{MS}` (new) — the M78 milestone. Expected: the Check output below.\n\n" + newfile(rd("milestone-78-usage-ledger.md")) +
    check(f"(Select-String -Path {MS} -Pattern '^\\| H[123] \\|').Count\n{CR(MS)}", "3\nCR 0"),
    f"2. `{GI}` — ignore the usage ledger's SQLite files. 1 edit (2a). Expected: the Check output below.\n\n" + edits(2, GI_EDIT) +
    check(f"git check-ignore llm-monitor/usage.sqlite3 llm-monitor/usage.sqlite3-wal\n{CR(GI)}", "llm-monitor/usage.sqlite3\nllm-monitor/usage.sqlite3-wal\nCR 0"),
    f"3. `{TEST}` (new) — the usage contract: 24 cases, synthetic fixtures only. It cannot pass yet (usage_ledger.py is H2). Expected: the Check output below.\n\n" +
    newfile(rd("test_usage_ledger.py")) + check(PARSE(TEST) + "\n" + CR(TEST), "parse ok\nCR 0"),
    f"4. `{EXP}` (new) — the suite's PASS count. Expected: the Check output below.\n\n" + newfile(rd("expected.txt")) +
    check(f"Get-Content {EXP} | Select-Object -Last 1\n{CR(EXP)}", "test_usage_ledger.py 24\nCR 0"),
    f"5. `{RT}` (new) — the runner that enforces the count. Expected: the Check output below.\n\n" + newfile(rd("run-tests.py")) +
    check(PARSE(RT) + f"\npy -3.12 {RT} --list\n{CR(RT)}", "parse ok\ntest_usage_ledger.py expected=24\nCR 0"),
]
start_extra = (f"4. This repo is C:\\Project\\llm-monitor. The executor files are in the Homelab repo: run every Check block through\n"
               f"   `powershell -NoProfile -ExecutionPolicy Bypass -File {RUNCHECK} -Run {RUN} -Step N -Check agent/scratch-m78/check.ps1`\n"
               "   (captures go to D:\\Project\\Homelab\\agent\\delegation\\runs\\m78-H1). Receipts format v2 (D:\\Project\\Homelab\\agent\\delegation\\EXECUTOR.md).\n")
env = ("- `python` typed in PowerShell is a silent no-op shim on this PC: use `py -3.12` exactly as the Check blocks do.\n"
       "- This handover changes no running service: the dashboard on 8090 is not restarted (that is H3).\n")
allowed = ("- Allowed: edit only the files named in steps 1-5; the receipts file; run the Check commands as written; read any file in this repo "
           "and the Homelab files named in Start here; delete agent/scratch-m78.\n")
denied = ("- Not allowed: the gateway on 8080 and Strata on 8081 (never stop, restart or kill them); the dashboard on 8090 and the scheduled tasks "
          "LLMMonitor / LLMMonitorBoot; sudo or elevation; commit or push; editing files no step names; any file in the Homelab repo.\n")
text = doc("Handover M78-H1: the usage ledger's records and its contract (llm-monitor M78, Homelab B-89 T14; tier T0)", head, short, start_extra,
           "Milestone M78 adds a usage ledger to this dashboard: token usage of Claude Code and of Hermes (Strata), numbers only, served on "
           ":8090 for the Homelab delegation protocol (ADR-022). H1 lays down the records and the contract: 24 test cases the module in H2 "
           "must pass, with synthetic fixtures only (this repo is public). The orchestrator validated the contract against a throwaway "
           "reference and checked that each planned mutant is killed.",
           "- Exact text only: apply every Find/Replace and Create block verbatim (tier T0).\n- The test is the contract: never change it.",
           "the files named in steps 1-5", steps, "", "", "agent/handover/m78/H1-receipts.md",
           "the 1 modified file and 4 new files of steps 1-5, plus the receipts file",
           executor="strata-iq3s (qwen3.8-flash-next-iq3_s, headless Hermes on 192.168.0.75)", series="m78",
           executor_md="D:\\Project\\Homelab\\agent\\commands\\local.execute.md", env_notes=env, allowed=allowed, denied=denied)
open(os.path.join(REPO, "agent", "handover", "m78", "H1-records-contract.md"), "w", encoding="utf8", newline="\n").write(text)
print("written H1-records-contract.md", len(text), "HEAD", short)
