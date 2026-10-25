"""Generate M78 handover H3 (tier T0, exact text): the API test, server routes + ingest thread, the Usage panel, the e2e line,
README and CHANGELOG. The targets are CRLF in the index: the executor applies each step's blocks with Homelab's apply_edits.py.
The live restart and the live check are the orchestrator's, after verification (a replayed step must never restart the dashboard).
    py -3.12 agent/handover/m78/src/gen_h3.py        (from C:\\Project\\llm-monitor)"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, "D:/Project/Homelab/agent/delegation/tools")
import hgen  # noqa: E402
from hgen import CR, PARSE, check, doc, edits, head_commit, newfile  # noqa: E402
sys.path.insert(0, HERE)
import h3spec as H  # noqa: E402

hgen.ROOT_LABEL = "C:" + hgen.BS + "Project" + hgen.BS + "llm-monitor"
head, short = head_commit(REPO)
RUN, HO = "m78-H3", "agent/handover/m78/H3-server-panel.md"
BS = hgen.BS
TOOLS = "D:" + BS + "Project" + BS + "Homelab" + BS + "agent" + BS + "delegation" + BS + "tools" + BS
APPLY = lambda n: f"py -3.12 {TOOLS}apply_edits.py --handover {HO} --step {n}"
API, EXP = "tests/usage/test_usage_api.py", "tests/usage/expected.txt"
rd = lambda f: open(os.path.join(HERE, "files", f), encoding="utf8").read()
grep = lambda f, s: f"(Select-String -Path {f} -SimpleMatch '{s}').Count"
CRLF_NOTE = ("This file is stored with CRLF line endings: do NOT use your patch tool. Apply this step's blocks with the helper (it converts "
             "them to CRLF, needs each Find text exactly once, and writes nothing otherwise); the helper's run is the first line of the Check.")


def crlf_step(n, f, eds, what, checks, exp):
    return (f"{n}. `{f}` — {what} {len(eds)} edit(s) ({n}a–{n}{'abcdefghij'[len(eds) - 1]}). {CRLF_NOTE} Expected: the Check output below.\n\n" +
            edits(n, eds) + check(APPLY(n) + "\n" + checks, f"applied {len(eds)} edit(s) to {f} (CRLF kept)\n" + exp,
                                  "record FAIL with the output and STOP (never edit the file by hand; never run the helper twice on a file it changed)."))


steps = [
    f"1. `{API}` (new) — the API contract: the real server.py on a spare port (18099) with synthetic sources (4 cases). Expected: the Check output below.\n\n" +
    newfile(rd("test_usage_api.py")) + check(PARSE(API) + "\n" + CR(API), "parse ok\nCR 0"),
    f"2. `{EXP}` — the API suite's count. 1 edit (2a). Expected: the Check output below.\n\n" +
    edits(2, [("test_usage_ledger.py 24\n", "test_usage_ledger.py 24\ntest_usage_api.py 4\n")]) +
    check(f"Get-Content {EXP} | Select-Object -Last 2\n{CR(EXP)}", "test_usage_ledger.py 24\ntest_usage_api.py 4\nCR 0"),
    crlf_step(3, H.SRV, H.SRV_EDITS, "the ingest thread, the catch-up and the two /api/usage routes.",
              PARSE(H.SRV) + "\n" + grep(H.SRV, 'elif path in ("/api/usage", "/api/usage/sessions"):') + "\n" + grep(H.SRV, "threading.Thread(target=usage_thread") + "\n" + CR(H.SRV),
              "parse ok\n1\n1\nCR 1732"),
    crlf_step(4, H.HTML, H.HTML_EDITS, "the Usage ledger panel.",
              grep(H.HTML, 'id="usage-sources"') + "\n" + CR(H.HTML), "1\nCR 663"),
    crlf_step(5, H.JS, H.JS_EDITS, "fetchUsage and its 60 s timer.",
              f"node --check {H.JS}; \"node-check rc=$LASTEXITCODE\"\n" + grep(H.JS, "setInterval(fetchUsage, 60000);") + "\n" + CR(H.JS), "node-check rc=0\n1\nCR 1827"),
    crlf_step(6, H.E2E, H.E2E_EDITS, "the usage suites in the e2e run.",
              grep(H.E2E, 'tests/usage/run-tests.py"') + "\n" + CR(H.E2E), "1\nCR 37"),
    crlf_step(7, H.README, H.README_EDITS, "the Usage ledger section.",
              f"(Select-String -Path {H.README} -Pattern '^## Usage ledger').Count\n{CR(H.README)}", "1\nCR 259"),
    crlf_step(8, H.CL, H.CL_EDITS, "version 0.1.13.",
              f"(Select-String -Path {H.CL} -Pattern '^## \\[0\\.1\\.13\\]').Count\n{CR(H.CL)}", "1\nCR 257"),
    "9. `run-e2e-tests.sh` — read only: the usage suites, then the whole e2e run. Expected: the Check output below.\n\n" +
    check("py -3.12 tests/usage/run-tests.py\n\"rc=$LASTEXITCODE\"\n& \"C:\\Program Files\\Git\\bin\\bash.exe\" run-e2e-tests.sh 2>&1 | Select-Object -Last 1\n\"e2e rc=$LASTEXITCODE\"",
          "test_usage_api.py            rc=0 pass=4  ALL PASSED (simulated)\ntest_usage_ledger.py         rc=0 pass=24  ALL PASSED (simulated)\nRESULT rc_all=0\nrc=0\n"
          "run-e2e-tests.sh: 3 e2e tests passed\ne2e rc=0", "record FAIL with the whole output and STOP."),
]
start_extra = (f"4. This repo is C:\\Project\\llm-monitor. Run every Check block through\n"
               f"   `powershell -NoProfile -ExecutionPolicy Bypass -File {TOOLS}run-check.ps1 -Run {RUN} -Step N -Check agent/scratch-m78/check.ps1`\n"
               "   (captures go to D:\\Project\\Homelab\\agent\\delegation\\runs\\m78-H3). Receipts format v2 (D:\\Project\\Homelab\\agent\\delegation\\EXECUTOR.md).\n"
               "5. Steps 3-8 edit CRLF files: their blocks are applied ONLY by the helper named in each Check (never your patch tool).\n")
env = ("- `python` typed in PowerShell is a silent no-op shim on this PC: use `py -3.12` exactly as the Check blocks do.\n"
       "- The live dashboard on 8090 is NOT restarted in this handover: the orchestrator restarts and checks it after verification.\n")
allowed = ("- Allowed: create and edit only the files named in steps 1-8 (steps 3-8 only through the helper); the receipts file; run the Check "
           "commands as written (the API test starts its own server on 18099 and stops it); delete agent/scratch-m78.\n")
denied = ("- Not allowed: the gateway on 8080 and Strata on 8081; the dashboard on 8090, restart-llm-monitor.ps1 and the scheduled tasks "
          "LLMMonitor / LLMMonitorBoot; reading ~/.claude or the Hermes state.db; sudo or elevation; commit or push; editing any other file.\n")
text = doc("Handover M78-H3: the usage API, the ingest thread and the Usage panel (llm-monitor M78, Homelab B-89 T14; tier T0)", head, short, start_extra,
           "H2 delivered llm-monitor/usage_ledger.py (contract 24/24, mutants 5/5). H3 wires it into the dashboard exactly as given: a daemon "
           "thread ingests every 60 s, /api/usage and /api/usage/sessions answer the Homelab usage contract (a catch-up ingest first; a bad "
           "window is HTTP 400), a Usage ledger panel shows today and 7 days, the e2e run includes the usage suites, and the README and "
           "CHANGELOG say what is read and what never is. The orchestrator pre-tested every edit on an exported copy.",
           "- Exact text only (tier T0). Steps 3-8 go through apply_edits.py because those files are CRLF.\n"
           "- Numbers only: the usage API never returns message text, titles or prompts.",
           "the files named in steps 1-8", steps, "", "- Never run the helper twice on the same step (it would refuse; nothing is written then).",
           "agent/handover/m78/H3-receipts.md", "the 7 modified files and 1 new file of steps 1-8, plus the receipts file",
           executor="strata-iq3s (qwen3.8-flash-next-iq3_s, headless Hermes on 192.168.0.75)", series="m78",
           executor_md="D:\\Project\\Homelab\\agent\\commands\\local.execute.md", env_notes=env, allowed=allowed, denied=denied)
open(os.path.join(REPO, HO), "w", encoding="utf8", newline="\n").write(text)
print("written", HO, len(text), "HEAD", short)
