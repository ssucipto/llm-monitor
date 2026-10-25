"""Generate M78 handover H4 (tier T0, exact text): usage_ledger parses millisecond timestamps, skips a record with no usable time
and repairs the rows 1.0 stored without one; 5 contract cases and 5 mutants. CHANGELOG is CRLF: apply_edits.py for that step.
The e2e run is not a step: the executor's shell breaks acp.taint-scan.sh (Homelab CARRY-HOM-089); the orchestrator runs it.
    py -3.12 agent/handover/m78/src/gen_h4.py [EXPECTED_MUTATION_FILE]     (from C:\\Project\\llm-monitor)"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, "D:/Project/Homelab/agent/delegation/tools")
import hgen  # noqa: E402
import mutation_proof as mp  # noqa: E402
from hgen import CR, PARSE, check, doc, edits, head_commit  # noqa: E402
sys.path.insert(0, HERE)
import h4spec as H  # noqa: E402

hgen.ROOT_LABEL = "C:" + hgen.BS + "Project" + hgen.BS + "llm-monitor"
head, short = head_commit(REPO)
RUN, HO = "m78-H4", "agent/handover/m78/H4-ms-timestamps.md"
MUTF = "agent/handover/m78/src/files/h4-mutants.tsv"
BS = hgen.BS
TOOLS = "D:" + BS + "Project" + BS + "Homelab" + BS + "agent" + BS + "delegation" + BS + "tools" + BS
grep = lambda f, s: f"(Select-String -Path {f} -SimpleMatch '{s}').Count"
MUT_EXP = open(sys.argv[1], encoding="utf8").read().strip() if len(sys.argv) > 1 else "(filled from the preflight)"

steps = [
    f"1. `{H.LEDGER}` — millisecond timestamps, skip a record with no usable time, the one-time repair. 4 edits (1a-1d). Expected: the Check output below.\n\n" +
    edits(1, H.LEDGER_EDITS) +
    check(PARSE(H.LEDGER) + "\n" + grep(H.LEDGER, "dt = datetime.fromisoformat(") + "\n" + grep(H.LEDGER, 'stats["skipped"] += 1') + "\n" +
          grep(H.LEDGER, 'con.execute("DELETE FROM usage_cursor")') + "\n" + CR(H.LEDGER), "parse ok\n1\n2\n1\nCR 0"),
    f"2. `{H.TEST}` — 5 contract cases for H4. 1 edit (2a). Expected: the Check output below.\n\n" +
    edits(2, H.TEST_EDITS) + check(PARSE(H.TEST) + "\n" + grep(H.TEST, "# M78-H4: real Claude Code timestamps") + "\n" + CR(H.TEST), "parse ok\n1\nCR 0"),
    f"3. `{H.EXP}` — the ledger suite's count. 1 edit (3a). Expected: the Check output below.\n\n" +
    edits(3, H.EXP_EDITS) + check(f"Get-Content {H.EXP} | Select-Object -Last 2\n{CR(H.EXP)}", "test_usage_ledger.py 29\ntest_usage_api.py 4\nCR 0"),
    f"4. `{H.CL}` — version 0.1.14. 1 edit (4a). This file is stored with CRLF line endings: do NOT use your patch tool. Apply the block "
    "with the helper (it converts it to CRLF, needs the Find text exactly once, and writes nothing otherwise); the helper's run is the first "
    "line of the Check. Expected: the Check output below.\n\n" + edits(4, H.CL_EDITS) +
    check(f"py -3.12 {TOOLS}apply_edits.py --handover {HO} --step 4\n(Select-String -Path {H.CL} -Pattern '^## \\[0\\.1\\.14\\]').Count\n{CR(H.CL)}",
          f"applied 1 edit(s) to {H.CL} (CRLF kept)\n1\nCR 262",
          "record FAIL with the output and STOP (never edit the file by hand; never run the helper twice)."),
    f"5. `{TOOLS}mutation_proof.py` — read only: the mutation proof (local bench). The new cases must fail on the base code by assert, "
    "each of the 5 mutants must be caught, and the final tree must pass. Paste the whole output with the freeze line. Expected: the Check output below.\n\n" +
    check(f"py -3.12 {TOOLS}mutation_proof.py --repo . --base {head} --tests {H.TEST} --mutants {MUTF} --run {RUN} --bench local --paths llm-monitor tests\n\"exit=$LASTEXITCODE\"",
          MUT_EXP, "record FAIL with the whole output and STOP (never change the test, the module or a mutant)."),
    "6. `tests/usage/run-tests.py` — read only: both usage suites. Expected: the Check output below.\n\n" +
    check("py -3.12 tests/usage/run-tests.py\n\"rc=$LASTEXITCODE\"",
          "test_usage_api.py            rc=0 pass=4  ALL PASSED (simulated)\ntest_usage_ledger.py         rc=0 pass=29  ALL PASSED (simulated)\nRESULT rc_all=0\nrc=0",
          "record FAIL with the whole output and STOP."),
]
start_extra = (f"4. This repo is C:\\Project\\llm-monitor. Run every Check block through\n"
               f"   `powershell -NoProfile -ExecutionPolicy Bypass -File {TOOLS}run-check.ps1 -Run {RUN} -Step N -Check agent/scratch-m78/check.ps1`\n"
               "   (captures go to D:\\Project\\Homelab\\agent\\delegation\\runs\\m78-H4). Receipts format v2 (D:\\Project\\Homelab\\agent\\delegation\\EXECUTOR.md).\n"
               "5. Steps 1-3 are LF files: apply their blocks exactly. Step 4 is CRLF: only the helper named in its Check applies it.\n")
env = ("- `python` typed in PowerShell is a silent no-op shim on this PC: use `py -3.12` exactly as the Check blocks do.\n"
       "- No e2e run in this handover (run-e2e-tests.sh): the orchestrator runs it after verification.\n"
       "- The live dashboard on 8090 is NOT restarted here: the orchestrator restarts and checks it after verification.\n")
allowed = ("- Allowed: edit only the files named in steps 1-4 (step 4 only through the helper); the receipts file; run the Check commands as "
           "written (the mutation proof builds its own temp trees and removes them); delete agent/scratch-m78.\n")
denied = ("- Not allowed: the gateway on 8080 and Strata on 8081; the dashboard on 8090, restart-llm-monitor.ps1 and the scheduled tasks "
          "LLMMonitor / LLMMonitorBoot; llm-monitor/usage.sqlite3; reading ~/.claude or the Hermes state.db; sudo or elevation; commit or push; "
          "editing any other file.\n")
text = doc("Handover M78-H4: millisecond timestamps in the usage ledger (llm-monitor M78, Homelab B-89 T14; tier T0)", head, short, start_extra,
           "Live after H3, /api/usage read 0 for Claude Code in every window: Claude Code writes timestamps with milliseconds "
           "(2026-10-25T09:42:25.123Z), usage_ledger 1.0 parsed only whole seconds, and stored each row with no time instead of skipping it. "
           "H4 parses any ISO 8601 time with a zone, skips and counts a record with no usable time, and on connect removes the rows stored "
           "without a time once (and resets the cursors so the next pass reads them again). The orchestrator pre-tested every edit on an "
           "exported copy: 29/29, the new cases fail on the base by assert, 5/5 mutants caught.",
           "- Exact text only (tier T0).\n- Numbers only: no change reads message text.",
           "the files named in steps 1-4", steps, "", "- Never run the helper twice on the same step (it would refuse; nothing is written then).",
           "agent/handover/m78/H4-receipts.md", "the 4 modified files of steps 1-4, plus the receipts file",
           executor="strata-iq3s (qwen3.8-flash-next-iq3_s, headless Hermes on 192.168.0.75)", series="m78",
           executor_md="D:\\Project\\Homelab\\agent\\commands\\local.execute.md", env_notes=env, allowed=allowed, denied=denied)
if __name__ == "__main__":
    open(os.path.join(REPO, MUTF), "w", encoding="utf8", newline="\n").write("".join(f"{f}\t{mp.escape(a)}\t{mp.escape(b)}\n" for f, a, b in H.MUTANTS))
    open(os.path.join(REPO, HO), "w", encoding="utf8", newline="\n").write(text)
    print("written", HO, len(text), "HEAD", short)
