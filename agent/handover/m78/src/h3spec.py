# M78-H3 (tier T0, exact text): server routes + ingest thread, the Usage panel, the e2e line, README, CHANGELOG.
# Every target is CRLF in the index, so the executor applies the pairs with Homelab's apply_edits.py (LF blocks, CRLF kept).
SRV = "llm-monitor/server.py"
SRV_EDITS = [
("""import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
""",
"""import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import usage_ledger
"""),
("""DB_PATH = str(Path(__file__).resolve().with_name("telemetry.sqlite3"))
""",
"""DB_PATH = str(Path(__file__).resolve().with_name("telemetry.sqlite3"))

# M78 usage ledger (numbers only; README "Usage ledger"): its own SQLite file beside server.py and the two sources it reads.
# The LLM_MONITOR_* overrides exist for the tests (tests/usage/test_usage_api.py builds synthetic sources).
USAGE_DB = os.environ.get("LLM_MONITOR_USAGE_DB") or str(Path(__file__).resolve().with_name("usage.sqlite3"))
CLAUDE_ROOT = os.environ.get("LLM_MONITOR_CLAUDE_ROOT") or str(Path.home() / ".claude" / "projects")
HERMES_DB = os.environ.get("LLM_MONITOR_HERMES_DB") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "hermes", "state.db")
USAGE_STATUS = {"claude_code": "missing", "hermes": "missing"}
_USAGE_LOCK = threading.Lock()


def usage_ingest(budget_s=5.0):
    \"\"\"One ingest pass (the thread every 60 s, and a catch-up before each /api/usage answer); one writer at a time.
    Returns partial: True when the time budget ran out or the pass failed (the answer then says so).\"\"\"
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
    \"\"\"Daemon: ingest every 60 s, so the ledger fills with no dashboard tab open (audit #93 PA-01).\"\"\"
    while True:
        usage_ingest(5.0)
        time.sleep(60)
"""),
("""            else:
                super().do_GET()
                return
            self.send_response(200)
""",
"""            elif path in ("/api/usage", "/api/usage/sessions"):
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
"""),
("""    httpd = _Server(("127.0.0.1", port), handler)
""",
"""    threading.Thread(target=usage_thread, name="usage-ingest", daemon=True).start()
    httpd = _Server(("127.0.0.1", port), handler)
"""),
]

HTML = "llm-monitor/index.html"
HTML_EDITS = [
("""    <section class="panel context" id="context" aria-labelledby="context-h">
""",
"""    <section class="panel usage" id="usage" aria-labelledby="usage-h">
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
"""),
]

JS = "llm-monitor/app.js"
JS_EDITS = [
("""async function init() {
""",
"""// M78 usage ledger: today and the last 7 days, every 60 s. A missing source says "unavailable", never 0 (honest labels).
const fmtTok = (n) => (n == null ? "unavailable" : n >= 1e6 ? `${(n / 1e6).toFixed(2)} M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)} k` : String(Math.round(n)));
async function fetchUsage() {
  const now = new Date();
  const iso = (d) => d.toISOString().replace(/\\.\\d{3}Z$/, "Z");
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
"""),
("""  fetchTimeseries("1h");
  setInterval(tickClock, 1000);
  setInterval(refresh, REFRESH_MS);
""",
"""  fetchTimeseries("1h");
  fetchUsage();
  setInterval(tickClock, 1000);
  setInterval(refresh, REFRESH_MS);
  setInterval(fetchUsage, 60000);
"""),
]

E2E = "run-e2e-tests.sh"
E2E_EDITS = [
("""echo "run-e2e-tests.sh: ${pass} e2e tests passed"
""",
"""# M78: the usage ledger suites (stdlib; counts enforced by tests/usage/run-tests.py). py on this PC (a bare python is a shim).
if command -v py >/dev/null 2>&1; then PY=(py -3.12); elif command -v python3 >/dev/null 2>&1; then PY=(python3); else
  echo "run-e2e-tests.sh: neither py nor python3 found for tests/usage" >&2; exit 1; fi
"${PY[@]}" "${PROJECT_ROOT}/tests/usage/run-tests.py"
pass=$((pass + 1))

echo "run-e2e-tests.sh: ${pass} e2e tests passed"
"""),
]

README = "llm-monitor/README.md"
README_EDITS = [
("""## Configuration
""",
"""## Usage ledger

Token usage of the orchestrator (Claude Code) and of the local executor (Hermes running Strata), per time window, repo and
session, for the Homelab delegation protocol (milestone M78; Homelab ADR-022).

- **What is read:** `%USERPROFILE%\\.claude\\projects\\**\\*.jsonl` (only the `assistant` lines' ids, timestamps, model, working
  folder and the four token counts) and `%LOCALAPPDATA%\\hermes\\state.db` (read-only: per-session model usage and the repo folder).
- **What is never read or stored:** message text, titles, prompts, tool output.
- **Where:** `llm-monitor/usage.sqlite3` (gitignored, its own file beside the telemetry DB). A thread ingests every 60 s, and
  every `/api/usage` call catches up first (at most 10 s; `partial: true` if it ran out).
- **API:** `GET /api/usage?from=ISO&to=ISO[&repo=PATH][&session=ID]` (totals, a cost-weighted unit, source status) and
  `GET /api/usage/sessions?...` (one row per session and role). A bad window is HTTP 400; a missing source is `null`, never 0.
- **Tests:** `py -3.12 tests/usage/run-tests.py` (synthetic data only; `run-e2e-tests.sh` runs it).

## Configuration
"""),
]

CL = "CHANGELOG.md"
CL_EDITS = [
("""## [0.1.12] - 2026-10-17
""",
"""## [0.1.13] - 2026-10-25

### Added
- Usage ledger (M78): `usage_ledger.py` ingests numbers-only token usage of Claude Code and Hermes into `usage.sqlite3`; `/api/usage` and `/api/usage/sessions` serve it; a background thread ingests every 60 s; a "Usage ledger" panel shows today and 7 days. Built through the Homelab delegation pipeline (Strata IQ3_S writing from specs; contract 24 + API 4 cases, mutation proof 5/5).

## [0.1.12] - 2026-10-17
"""),
]
