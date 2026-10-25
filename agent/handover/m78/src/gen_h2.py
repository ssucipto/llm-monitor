"""Generate M78 handover H2 (tier T1, class readonly-source probation): llm-monitor/usage_ledger.py written by the executor
from three specs, proven by the H1 contract (24 cases) and five '~' mutants (--no-base: the module is new).
    py -3.12 agent/handover/m78/src/gen_h2.py        (from C:\\Project\\llm-monitor)"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, "D:/Project/Homelab/agent/delegation/tools")
import hgen  # noqa: E402
from hgen import CR, PARSE, check, doc, fence, head_commit  # noqa: E402
import make_h2_mutants as MM  # noqa: E402

hgen.ROOT_LABEL = "C:" + hgen.BS + "Project" + hgen.BS + "llm-monitor"
head, short = head_commit(REPO)
RUN, MOD, TEST = "m78-H2", "llm-monitor/usage_ledger.py", "tests/usage/test_usage_ledger.py"
BS = hgen.BS
HL = "D:" + BS + "Project" + BS + "Homelab"
RUNCHECK = HL + BS + "agent" + BS + "delegation" + BS + "tools" + BS + "run-check.ps1"
MPROOF = HL + BS + "agent" + BS + "delegation" + BS + "tools" + BS + "mutation_proof.py"
D = MM.D
HEADER = '"""usage_ledger.py v1.0 — the usage ledger: numbers-only token usage of Claude Code and Hermes (M78; Homelab B-89 T14, ADR-022).'

SPEC_A = f"""Create the module (Python 3.12, standard library only: json, os, sqlite3, time, datetime; the style of server.py: a module
docstring, short comments on the why). Its FIRST line is exactly:
    {HEADER}
followed by 2-4 docstring lines: what is read (numbers only), what is never read (message text, titles, prompts), where it is stored.
Module constants: EXECUTOR_MODELS = ("strata-iq3_s", "qwen3.8-flash-next-iq3_s") and
WEIGHTS = {{"input": 1.0, "cache_write_5m": 1.25, "cache_write_1h": 2.0, "cache_read": 0.1, "output": 5.0}}.
• iso(t: float) -> str: UTC, "%Y-%m-%dT%H:%M:%SZ".
• parse_window(frm: str, to: str) -> (float, float): ISO 8601 with a trailing Z; raise ValueError when either does not parse or frm > to.
• connect(path) -> sqlite3.Connection: PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; create if missing:
  usage_event(source TEXT, msg_key TEXT, session TEXT, t REAL, t_end REAL, model TEXT, repo TEXT, sidechain INTEGER, task TEXT,
  input INTEGER, output INTEGER, cache_write INTEGER, cache_write_5m INTEGER, cache_write_1h INTEGER, cache_read INTEGER, reasoning INTEGER),
  usage_cursor(file TEXT PRIMARY KEY, offset INTEGER, mtime REAL), and the index with this EXACT line (any indentation):
    {D["D1"]}
• ingest_hermes(con, db_path) -> {{"status": str, "rows": int}}:
  - db_path does not exist -> {{"status": "missing", "rows": 0}};
  - open read-only: sqlite3.connect(f"file:{{db_path}}?mode=ro", uri=True, timeout=2);
  - read session_model_usage JOIN sessions ON sessions.id = session_model_usage.session_id: session_id, model, task, first_seen,
    last_seen, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens and coalesce(git_repo_root, cwd).
    Never select title, system_prompt or any other text column;
  - upsert one usage_event row each: source "hermes", msg_key f"{{session_id}}:{{model}}:{{task}}", session = session_id, t = first_seen,
    t_end = last_seen, the counts (cache_write_5m and cache_write_1h = 0); on conflict replace t_end and the counts; commit;
  - sqlite3.OperationalError: "locked" in the message -> {{"status": "error: locked", "rows": 0}}, otherwise {{"status": "error: schema", "rows": 0}};
    never raise. Success -> {{"status": "ok", "rows": number of rows read}}."""
SPEC_B = f"""Add ingest_claude(con, root, budget_s=5.0) -> {{"files", "lines", "added", "skipped", "partial"}} (all counts, partial a bool):
• Walk root recursively (os.walk) for files ending in .jsonl; sub-folders hold subagent transcripts.
• Stop starting new files once budget_s seconds (time.monotonic) are used: return with partial True (the cursors keep the place).
• Per file: offset = its usage_cursor row (0 if none); size = os.path.getsize. Use these EXACT lines (any indentation):
    {D["D2"]}
  (and set offset to 0 in its body), read the bytes from offset to the end, then
    {D["D3"]}
  and only data[:end] is consumed (split into lines; each counts in "lines"). Save offset + end and the mtime as the file's cursor.
• Per line: not JSON -> skipped += 1. JSON with type == "assistant" and a dict message with a usage dict -> INSERT OR IGNORE one
  usage_event row: source "claude_code", msg_key f"{{message.id}}:{{requestId}}", session = sessionId, t = the timestamp as epoch
  seconds (parse_window's ISO rule), t_end None, model = message.model, repo = cwd, sidechain = 1 if isSidechain else 0, task None,
  input/output/cache_write/cache_read from input_tokens / output_tokens / cache_creation_input_tokens / cache_read_input_tokens,
  cache_write_5m / cache_write_1h from usage.cache_creation.ephemeral_5m_input_tokens / ephemeral_1h_input_tokens (0 when absent),
  reasoning 0; added += rows actually inserted. Every other line type is ignored (not skipped). Never store any text field.
• Commit at the end."""
SPEC_C = f"""Add norm_repo, summary and sessions:
• norm_repo(p) is exactly (any indentation for the body line):
    def norm_repo(p):
        {D["D4"]}
• summary(con, frm, to, repo=None, session=None, status=None, partial=False) -> dict (status None = {{}}):
  - window = parse_window(frm, to). Orchestrator rows: source "claude_code" with frm <= t <= to. Executor rows: source "hermes",
    model in EXECUTOR_MODELS, t <= to and t_end >= frm. Then, when given: keep rows whose norm_repo(repo) starts with norm_repo(repo
    argument); keep rows whose session equals session.
  - orchestrator block: sums of input, output, cache_write, cache_write_5m, cache_write_1h, cache_read; messages = row count;
    sessions = distinct sessions; models = {{model: rows}}. Executor block: sums of input, output, cache_write, cache_read, reasoning;
    sessions; models.
  - A block is None when its source's status is not "ok"; for the orchestrator use this EXACT line (any indentation):
        {D["D5"]}
    and the same form for the executor with "hermes".
  - weighted: orchestrator = input + 1.25*cache_write_5m + 2.0*cache_write_1h + 1.25*(cache_write - cache_write_5m - cache_write_1h)
    + 0.1*cache_read + 5*output; executor = input + 1.25*cache_write + 0.1*cache_read + 5*output; None for a None block; "weights": WEIGHTS.
  - return {{"window": {{"from": frm, "to": to}}, "orchestrator", "executor", "weighted", "sources": status, "partial": partial,
    "generated_at": iso(time.time())}}.
• sessions(con, frm, to, repo=None, session=None) -> list: the same rows and filters, one dict per (role, session): source,
  role ("orchestrator" or "executor"), id, start (iso of the smallest t), end (iso of the largest t_end, else t), model, repo,
  input, output, cache_write, cache_read (sums)."""

grep = lambda s: f"(Select-String -Path {MOD} -SimpleMatch '{s}').Count"
RT = "test_usage_ledger.py         rc=0 pass=24  ALL PASSED (simulated)\nRESULT rc_all=0"
sha_test = __import__("hashlib").sha256(open(os.path.join(REPO, TEST), "rb").read()).hexdigest()
MUT = ("base: test_usage_ledger.py skipped (--no-base: new code, only the mutants prove the tests)\n" +
       "".join(f"mutant {i} killed (assert) by test_usage_ledger.py\n" for i in range(1, 6)) +
       "mutants: 5/5 killed\nfinal: test_usage_ledger.py PASS 24\n" + f"freeze: {TEST} sha256={sha_test}\nMUTATION PROOF OK")
steps = [
    f"1. `{MOD}` (new) — CODE TASK (you write it, from this spec): part A, the module, its storage and the Hermes ingest. Expected: the Check output below.\n\n" +
    fence(SPEC_A) + "\n" + check(PARSE(MOD) + "\n" + grep(D["D1"]) + "\n" + grep(HEADER) + "\n" + CR(MOD), "parse ok\n1\n1\nCR 0",
                                  "fix the code (at most 3 rounds), then NOT RUN with the output."),
    f"2. `{MOD}` (new) — CODE TASK (you write it, from this spec): part B, the Claude Code ingest. Expected: the Check output below.\n\n" +
    fence(SPEC_B) + "\n" + check(PARSE(MOD) + "\n" + grep(D["D2"]) + "\n" + grep(D["D3"]) + "\n" + CR(MOD), "parse ok\n1\n1\nCR 0",
                                  "fix the code (at most 3 rounds), then NOT RUN with the output."),
    f"3. `{MOD}` (new) — CODE TASK (you write it, from this spec): part C, the contract queries; then the contract suite. Expected: the Check output below.\n\n" +
    fence(SPEC_C) + "\n" + check(PARSE(MOD) + "\n" + grep(D["D4"]) + "\n" + grep(D["D5"]) + "\npy -3.12 tests/usage/run-tests.py\n\"rc=$LASTEXITCODE\"\n" + CR(MOD),
                                  "parse ok\n1\n1\n" + RT + "\nrc=0\nCR 0", "fix the CODE (at most 3 rounds; never the test), then NOT RUN with the output."),
    f"4. `{MPROOF}` — read only: the mutation proof (local bench; --no-base because the module is new, so the five mutants carry the proof). "
    "Paste the whole output with the freeze line. Expected: the Check output below.\n\n" +
    check(f"py -3.12 {MPROOF} --repo . --base {head} --tests {TEST} --mutants agent/handover/m78/src/files/h2-mutants.tsv --run {RUN} "
          "--bench local --paths llm-monitor tests --no-base\n\"exit=$LASTEXITCODE\"", MUT + "\nexit=0", "record FAIL with the whole output and STOP (never change the test or a mutant)."),
    "5. `tests/usage/run-tests.py` — read only: the contract suite twice (a difference is a flake, never a PASS). Expected: the Check output below.\n\n" +
    check("py -3.12 tests/usage/run-tests.py\n\"run1 rc=$LASTEXITCODE\"\npy -3.12 tests/usage/run-tests.py\n\"run2 rc=$LASTEXITCODE\"", RT + "\nrun1 rc=0\n" + RT + "\nrun2 rc=0"),
]
start_extra = (f"4. This repo is C:\\Project\\llm-monitor. Run every Check block through\n"
               f"   `powershell -NoProfile -ExecutionPolicy Bypass -File {RUNCHECK} -Run {RUN} -Step N -Check agent/scratch-m78/check.ps1`\n"
               "   (captures go to D:\\Project\\Homelab\\agent\\delegation\\runs\\m78-H2). Receipts format v2 (D:\\Project\\Homelab\\agent\\delegation\\EXECUTOR.md).\n"
               "5. Steps 1-3 are CODE TASKS in one new file: you write the code from the specs. Copy the EXACT lines verbatim (indentation is yours).\n")
env = ("- `python` typed in PowerShell is a silent no-op shim on this PC: use `py -3.12` exactly as the Check blocks do.\n"
       "- The tests are local (no bastion). This handover changes no running service: the dashboard on 8090 is not touched (that is H3).\n")
allowed = ("- Allowed: create and edit only llm-monitor/usage_ledger.py; the receipts file; run the Check commands as written; read any file in this "
           "repo and the Homelab files named in Start here; delete agent/scratch-m78.\n")
denied = ("- Not allowed: the gateway on 8080 and Strata on 8081 (never stop, restart or kill them); the dashboard on 8090 and the scheduled tasks "
          "LLMMonitor / LLMMonitorBoot; reading anything under ~/.claude or the Hermes state.db (the tests build their own synthetic data); "
          "sudo or elevation; commit or push; editing any other file, above all the test, expected.txt or the mutants.\n")
text = doc("Handover M78-H2: usage_ledger.py from three specs (llm-monitor M78, Homelab B-89 T14; tier T1)", head, short, start_extra,
           "H1 committed the usage ledger's contract (tests/usage/test_usage_ledger.py, 24 cases, synthetic fixtures). H2 writes the module "
           "that meets it: storage in its own SQLite file, the Hermes ingest (read-only, numbers only), the Claude Code ingest (byte cursors, "
           "dedupe on message id + request id, partial lines wait), and the contract queries. Then the mutation proof shows the tests catch "
           "five planted faults in your exact decision lines.",
           "- Numbers only: no message text, title or prompt is ever read into the database (the contract's privacy case checks it).\n"
           "- A read problem is a status, never zeros: a missing or broken Hermes DB is 'missing' or 'error: ...'.",
           "llm-monitor/usage_ledger.py", steps, "- A risk flag (Q1 or Q2 yes) means STOP.\n",
           "- Never change the test, expected.txt or the mutants file.", "agent/handover/m78/H2-receipts.md",
           "the 1 new file llm-monitor/usage_ledger.py, plus the receipts file",
           executor="strata-iq3s (qwen3.8-flash-next-iq3_s, headless Hermes on 192.168.0.75)", series="m78",
           executor_md="D:\\Project\\Homelab\\agent\\commands\\local.execute.md", tier="T1", versions=[f"{MOD}: {HEADER}"],
           env_notes=env, allowed=allowed, denied=denied)
open(os.path.join(REPO, "agent", "handover", "m78", "H2-usage-ledger.md"), "w", encoding="utf8", newline="\n").write(text)
print("written H2-usage-ledger.md", len(text), "HEAD", short)
