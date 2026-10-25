"""Generate M78 handover H5 (tier T0, exact text): configurable executor models named in /api/usage (Homelab review-043 CR-009),
the repo filter at a path boundary (CR-011), the API test on a free port (a fixed one failed a second Linux run: TIME_WAIT),
and CI for llm-monitor (audit #95 F-02). README and CHANGELOG are CRLF: apply_edits.py for those steps. No e2e step for the
executor (Homelab CARRY-HOM-089); the orchestrator runs it, and the CI file was pre-tested on Ubuntu (the bastion).
    py -3.12 agent/handover/m78/src/gen_h5.py [EXPECTED_MUTATION_FILE]     (from C:\\Project\\llm-monitor)"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, "D:/Project/Homelab/agent/delegation/tools")
import hgen  # noqa: E402
import mutation_proof as mp  # noqa: E402
from hgen import CR, PARSE, check, doc, edits, head_commit, newfile  # noqa: E402
sys.path.insert(0, HERE)
import h5spec as H  # noqa: E402

hgen.ROOT_LABEL = "C:" + hgen.BS + "Project" + hgen.BS + "llm-monitor"
head, short = head_commit(REPO)
RUN, HO = "m78-H5", "agent/handover/m78/H5-models-ci.md"
MUTF = "agent/handover/m78/src/files/h5-mutants.tsv"
BS = hgen.BS
TOOLS = "D:" + BS + "Project" + BS + "Homelab" + BS + "agent" + BS + "delegation" + BS + "tools" + BS
APPLY = lambda n: f"py -3.12 {TOOLS}apply_edits.py --handover {HO} --step {n}"
grep = lambda f, s: f"(Select-String -Path {f} -SimpleMatch '{s}').Count"
MUT_EXP = open(sys.argv[1], encoding="utf8").read().strip() if len(sys.argv) > 1 else "(filled from the preflight)"
CRLF_NOTE = ("This file is stored with CRLF line endings: do NOT use your patch tool. Apply the block with the helper (it converts it "
             "to CRLF, needs the Find text exactly once, and writes nothing otherwise); the helper's run is the first line of the Check.")
YAMLCHK = ("py -3.12 -c \"import yaml,sys;d=yaml.safe_load(open(sys.argv[1],encoding='utf8'));j=d['jobs']['tests'];"
           "print(j['runs-on']);[print(s.get('name') or s.get('uses')) for s in j['steps']]\" " + H.CI)

steps = [
    f"1. `{H.LEDGER}` — executor models from LLM_MONITOR_EXECUTOR_MODELS and named in the answer; the repo filter at a path boundary. "
    "5 edits (1a-1e). Expected: the Check output below.\n\n" + edits(1, H.LEDGER_EDITS) +
    check(PARSE(H.LEDGER) + "\n" + grep(H.LEDGER, "ms = tuple(EXECUTOR_MODELS)") + "\n" + grep(H.LEDGER, '"executor_models": list(EXECUTOR_MODELS)}') + "\n"
          + grep(H.LEDGER, 'startswith(want + "/")') + "\n" + CR(H.LEDGER), "parse ok\n1\n1\n1\nCR 0"),
    f"2. `{H.TEST}` — 4 contract cases for H5. 2 edits (2a-2b). Expected: the Check output below.\n\n" + edits(2, H.TEST_EDITS) +
    check(PARSE(H.TEST) + "\n" + grep(H.TEST, "# M78-H5: the executor model list can be set") + "\n" + CR(H.TEST), "parse ok\n1\nCR 0"),
    f"3. `{H.API}` — the API test takes a free port and checks the server came up. 5 edits (3a-3e). Expected: the Check output below.\n\n" +
    edits(3, H.API_EDITS) + check(PARSE(H.API) + "\n" + grep(H.API, "PORT = free_port()") + "\n" + grep(H.API, "PORT = 18099") + "\n" + CR(H.API),
                                  "parse ok\n1\n0\nCR 0"),
    f"4. `{H.EXP}` — the two suites' counts. 1 edit (4a). Expected: the Check output below.\n\n" + edits(4, H.EXP_EDITS) +
    check(f"Get-Content {H.EXP} | Select-Object -Last 2\n{CR(H.EXP)}", "test_usage_ledger.py 33\ntest_usage_api.py 5\nCR 0"),
    f"5. `{H.CI}` (new) — llm-monitor's CI: the usage suites and the e2e gates on every push. Expected: the Check output below.\n\n" +
    newfile(H.CI_TEXT) + check(YAMLCHK + "\n" + CR(H.CI),
                               "ubuntu-24.04\nactions/checkout@v4\nactions/setup-python@v5\nUsage suites, counts enforced\n"
                               "Shell scripts with LF line ends (this runner's checkout only)\nThe e2e gates (integrity v1 and v2, usage)\nCR 0"),
    f"6. `{H.README}` — the executor-model setting and the CI. 1 edit (6a). {CRLF_NOTE} Expected: the Check output below.\n\n" +
    edits(6, H.README_EDITS) + check(APPLY(6) + "\n" + grep(H.README, "LLM_MONITOR_EXECUTOR_MODELS") + "\n" + CR(H.README),
                                     f"applied 1 edit(s) to {H.README} (CRLF kept)\n1\nCR 261",
                                     "record FAIL with the output and STOP (never edit the file by hand; never run the helper twice)."),
    f"7. `{H.CL}` — version 0.1.15. 1 edit (7a). {CRLF_NOTE} Expected: the Check output below.\n\n" +
    edits(7, H.CL_EDITS) + check(APPLY(7) + f"\n(Select-String -Path {H.CL} -Pattern '^## \\[0\\.1\\.15\\]').Count\n{CR(H.CL)}",
                                 f"applied 1 edit(s) to {H.CL} (CRLF kept)\n1\nCR 270",
                                 "record FAIL with the output and STOP (never edit the file by hand; never run the helper twice)."),
    f"8. `{TOOLS}mutation_proof.py` — read only: the new cases must fail on the base code by assert, catch 4 planted faults, and pass "
    "on the final tree (local bench). Paste the whole output with the freeze line. Expected: the Check output below.\n\n" +
    check(f"py -3.12 {TOOLS}mutation_proof.py --repo . --base {head} --tests {H.TEST} --mutants {MUTF} --run {RUN} --bench local --paths llm-monitor tests\n\"exit=$LASTEXITCODE\"",
          MUT_EXP, "record FAIL with the whole output and STOP (never change the test, the module or a mutant)."),
    "9. `tests/usage/run-tests.py` — read only: both usage suites, twice (a second run right after the first is what failed before). "
    "Expected: the Check output below.\n\n" +
    check("py -3.12 tests/usage/run-tests.py\n\"rc=$LASTEXITCODE\"\npy -3.12 tests/usage/run-tests.py\n\"rc=$LASTEXITCODE\"",
          "test_usage_api.py            rc=0 pass=5  ALL PASSED (simulated)\ntest_usage_ledger.py         rc=0 pass=33  ALL PASSED (simulated)\n"
          "RESULT rc_all=0\nrc=0\ntest_usage_api.py            rc=0 pass=5  ALL PASSED (simulated)\ntest_usage_ledger.py         rc=0 pass=33  ALL PASSED (simulated)\n"
          "RESULT rc_all=0\nrc=0", "record FAIL with the whole output and STOP."),
]
start_extra = (f"4. This repo is C:\\Project\\llm-monitor. Run every Check block through\n"
               f"   `powershell -NoProfile -ExecutionPolicy Bypass -File {TOOLS}run-check.ps1 -Run {RUN} -Step N -Check agent/scratch-m78/check.ps1`\n"
               "   (captures go to D:\\Project\\Homelab\\agent\\delegation\\runs\\m78-H5). Receipts format v2 (D:\\Project\\Homelab\\agent\\delegation\\EXECUTOR.md).\n"
               "5. Steps 1-4 are LF files: apply their blocks exactly. Step 5 is a new file. Steps 6-7 are CRLF: only the helper named in each Check applies them.\n")
env = ("- `python` typed in PowerShell is a silent no-op shim on this PC: use `py -3.12` exactly as the Check blocks do.\n"
       "- No e2e run in this handover (run-e2e-tests.sh): the orchestrator runs it after verification.\n"
       "- The live dashboard on 8090 is NOT restarted here: the orchestrator restarts and checks it after verification.\n")
allowed = ("- Allowed: edit only the files named in steps 1-7 (steps 6-7 only through the helper); create the file of step 5; the receipts "
           "file; run the Check commands as written (the API test starts its own server on a free port and stops it; the mutation proof "
           "builds its own temp trees); delete agent/scratch-m78.\n")
denied = ("- Not allowed: the gateway on 8080 and Strata on 8081; the dashboard on 8090, restart-llm-monitor.ps1 and the scheduled tasks "
          "LLMMonitor / LLMMonitorBoot; llm-monitor/usage.sqlite3; reading ~/.claude or the Hermes state.db; sudo or elevation; commit or push; "
          "editing any other file.\n")
text = doc("Handover M78-H5: executor models, repo boundary, a stable API test, and CI (llm-monitor M78, Homelab B-89 T13; tier T0)", head, short,
           start_extra,
           "Homelab's post-implementation review found three things in the usage ledger: the executor was recognised by two hard-coded "
           "model names (a new quant would read as executor 0 with Hermes 'ok'); the repo filter was a bare prefix (llm-monitor-old matched "
           "llm-monitor); and llm-monitor had no CI. While pre-testing the CI on Ubuntu, the API test failed every second run: it bound the "
           "fixed port 18099, and Linux keeps the last run's sockets in TIME_WAIT for about a minute (the server turns address reuse off on "
           "purpose). H5 fixes all four exactly as given; the orchestrator pre-tested every edit on an exported copy (33 + 5 cases, the new "
           "cases fail on the base by assert, 4/4 mutants caught) and the CI steps twice in a row on Ubuntu.",
           "- Exact text only (tier T0). Steps 6-7 go through apply_edits.py because those files are CRLF.\n"
           "- Numbers only: no change reads message text.",
           "the files named in steps 1-7", steps, "", "- Never run the helper twice on the same step (it would refuse; nothing is written then).",
           "agent/handover/m78/H5-receipts.md", "the 6 modified files and 1 new file of steps 1-7, plus the receipts file",
           executor="strata-iq3s (qwen3.8-flash-next-iq3_s, headless Hermes on 192.168.0.75)", series="m78",
           executor_md="D:\\Project\\Homelab\\agent\\commands\\local.execute.md", env_notes=env, allowed=allowed, denied=denied)
if __name__ == "__main__":
    open(os.path.join(REPO, MUTF), "w", encoding="utf8", newline="\n").write("".join(f"{f}\t{mp.escape(a)}\t{mp.escape(b)}\n" for f, a, b in H.MUTANTS))
    open(os.path.join(REPO, HO), "w", encoding="utf8", newline="\n").write(text)
    print("written", HO, len(text), "HEAD", short)
