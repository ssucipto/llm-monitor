"""M78-H5 spec (tier T0, exact text): Homelab review-043 CR-009 (the executor model list is configurable and named in the answer;
a new quant must not read as 0), CR-011 (the repo filter stops at a path boundary), audit #95 F-02 (llm-monitor gets CI)."""
LEDGER, TEST, EXP = "llm-monitor/usage_ledger.py", "tests/usage/test_usage_ledger.py", "tests/usage/expected.txt"
CI, README, CL = ".github/workflows/usage-tests.yml", "llm-monitor/README.md", "CHANGELOG.md"

LEDGER_EDITS = [
    ('Storage: its own SQLite file (usage_event rows + usage_cursor byte cursors), WAL so the dashboard can read while we write."""\n',
     'Storage: its own SQLite file (usage_event rows + usage_cursor byte cursors), WAL so the dashboard can read while we write.\n'
     'v1.1 (M78-H5, Homelab review-043 CR-009/CR-011): LLM_MONITOR_EXECUTOR_MODELS sets the executor models and /api/usage names\n'
     'them (executor_models); the repo filter stops at a path boundary."""\n'),
    ('# the models that run executors: their Hermes rows are executor usage, not orchestrator usage\n'
     'EXECUTOR_MODELS = ("strata-iq3_s", "qwen3.8-flash-next-iq3_s")\n',
     '# the models that run executors: their Hermes rows are executor usage, not orchestrator usage. A new quant or model name\n'
     '# goes in LLM_MONITOR_EXECUTOR_MODELS (comma-separated); otherwise it would read as executor 0 with Hermes "ok" (M78-H5)\n'
     'EXECUTOR_MODELS = tuple(m.strip() for m in (os.environ.get("LLM_MONITOR_EXECUTOR_MODELS")\n'
     '                                            or "strata-iq3_s,qwen3.8-flash-next-iq3_s").split(",") if m.strip())\n'),
    ('            if repo is not None and not norm_repo(r[6]).startswith(norm_repo(repo)):  # repo column\n',
     '            want = norm_repo(repo) if repo is not None else None\n'
     '            if want is not None and not (norm_repo(r[6]) == want or norm_repo(r[6]).startswith(want + "/")):  # a path boundary (M78-H5)\n'),
    ('    ex = keep(con.execute("SELECT * FROM usage_event WHERE source=\'hermes\' AND model IN (?,?) AND t <= ? AND t_end >= ?",\n'
     '                          (EXECUTOR_MODELS[0], EXECUTOR_MODELS[1], t, f)).fetchall())\n',
     '    ms = tuple(EXECUTOR_MODELS)\n'
     '    ex = keep(con.execute("SELECT * FROM usage_event WHERE source=\'hermes\' AND model IN (%s) AND t <= ? AND t_end >= ?"\n'
     '                          % ",".join("?" * len(ms)), (*ms, t, f)).fetchall()) if ms else []\n'),
    ('            "sources": status, "partial": partial, "generated_at": iso(time.time())}\n',
     '            "sources": status, "partial": partial, "generated_at": iso(time.time()),\n'
     '            "executor_models": list(EXECUTOR_MODELS)}   # additive (M78-H5): what counts as executor usage\n'),
]

TEST_BLOCK = r'''# M78-H5: the executor model list can be set (a new quant must not read as 0), and the repo filter stops at a path boundary
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

'''
TEST_EDITS = [
    ("import sqlite3\nimport sys\nimport tempfile\n", "import sqlite3\nimport subprocess\nimport sys\nimport tempfile\n"),
    ('print("ALL PASSED (simulated)" if not fails else f"{len(fails)} FAILED")\n',
     TEST_BLOCK + 'print("ALL PASSED (simulated)" if not fails else f"{len(fails)} FAILED")\n'),
]
EXP_EDITS = [("test_usage_ledger.py 29\ntest_usage_api.py 4\n", "test_usage_ledger.py 33\ntest_usage_api.py 5\n")]

# The API test bound the fixed port 18099: on Linux a second run within ~60 s hits the first run's TIME_WAIT sockets and the
# server (SO_REUSEADDR off by design, server.py _Server) cannot bind, so the test read 'connection refused' (found on the
# bastion while pre-testing CI; CI runs the suites twice in a row). Now: a free port from the OS, an explicit 'server up' case,
# and the server's stderr kept for that case instead of DEVNULL.
API = "tests/usage/test_usage_api.py"
API_EDITS = [
    ('"""usage API tests (llm-monitor M78-H3, Homelab B-89 T14) — SIMULATED: the real server.py on a spare port (18099) with synthetic\n',
     '"""usage API tests (llm-monitor M78-H3/H5, Homelab B-89 T14) — SIMULATED: the real server.py on a free port the OS gives with synthetic\n'),
    ("import shutil\nimport sqlite3\n", "import shutil\nimport socket\nimport sqlite3\n"),
    ("PORT = 18099\n",
     "\n\ndef free_port():\n"
     "    \"\"\"A port nothing holds now (a fixed one can sit in TIME_WAIT after a run a minute ago: M78-H5).\"\"\"\n"
     "    with socket.socket() as s:\n"
     "        s.bind((\"127.0.0.1\", 0))\n"
     "        return s.getsockname()[1]\n\n\n"
     "PORT = free_port()\n"),
    ("proc = subprocess.Popen([sys.executable, SERVER, str(PORT)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n",
     "errf = os.path.join(tmp, \"server.err\")\n"
     "proc = subprocess.Popen([sys.executable, SERVER, str(PORT)], env=env, stdout=subprocess.DEVNULL, stderr=open(errf, \"w\"))\n"),
    ("    for _ in range(60):\n"
     "        try:\n"
     "            urllib.request.urlopen(f\"http://127.0.0.1:{PORT}/index.html\", timeout=2)\n"
     "            break\n"
     "        except OSError:\n"
     "            time.sleep(0.5)\n",
     "    up = False\n"
     "    for _ in range(60):\n"
     "        try:\n"
     "            urllib.request.urlopen(f\"http://127.0.0.1:{PORT}/index.html\", timeout=2)\n"
     "            up = True\n"
     "            break\n"
     "        except OSError:\n"
     "            time.sleep(0.5)\n"
     "    expect(\"the server under test answers within 30 s (else its stderr is shown)\", up,\n"
     "           open(errf, encoding=\"utf8\", errors=\"replace\").read()[-600:])\n"),
]

CI_TEXT = """# usage-tests — llm-monitor's own regression net (M78-H5; Homelab audit #95 F-02: the meter every B-89 number comes from had
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
        run: git ls-files -z '*.sh' | xargs -0 sed -i 's/\\r$//'
      - name: The e2e gates (integrity v1 and v2, usage)
        run: bash run-e2e-tests.sh
"""

README_EDITS = [
    ("- **Tests:** `py -3.12 tests/usage/run-tests.py` (synthetic data only; `run-e2e-tests.sh` runs it).\n",
     "- **Executor models:** Hermes rows count as executor usage only for the models in `LLM_MONITOR_EXECUTOR_MODELS`\n"
     "  (comma-separated; default `strata-iq3_s,qwen3.8-flash-next-iq3_s`); `/api/usage` names them in `executor_models`.\n"
     "- **Tests:** `py -3.12 tests/usage/run-tests.py` (synthetic data only; `run-e2e-tests.sh` runs it; CI: `usage-tests.yml`).\n"),
]
CL_EDITS = [("## [0.1.14] - 2026-10-25\n",
             "## [0.1.15] - 2026-10-25\n\n### Fixed\n"
             "- Usage ledger (M78-H5): the executor models are set by `LLM_MONITOR_EXECUTOR_MODELS` and named in `/api/usage` "
             "(`executor_models`), so a new quant no longer reads as executor 0; the repo filter stops at a path boundary "
             "(`llm-monitor-old` no longer matches `llm-monitor`). 4 new cases, 33 in all. The API test takes a free port "
             "(a fixed one failed a second run within a minute on Linux: TIME_WAIT) and checks the server came up.\n\n### Added\n"
             "- CI: `usage-tests.yml` runs the usage suites and the e2e gates on every push.\n\n## [0.1.14] - 2026-10-25\n")]

MUTANTS = [
    (LEDGER, '~if want is not None and not (norm_repo(r[6]) == want or norm_repo(r[6]).startswith(want + "/")):  # a path boundary (M78-H5)',
     'if want is not None and not norm_repo(r[6]).startswith(want):'),
    (LEDGER, "~ms = tuple(EXECUTOR_MODELS)", 'ms = ("strata-iq3_s", "qwen3.8-flash-next-iq3_s")'),
    (LEDGER, '~or "strata-iq3_s,qwen3.8-flash-next-iq3_s").split(",") if m.strip())', 'or "strata-iq3_s,qwen3.8-flash-next-iq3_s").split(",") if False)'),
    (LEDGER, '~"executor_models": list(EXECUTOR_MODELS)}   # additive (M78-H5): what counts as executor usage', '"executor_models": []}'),
]
