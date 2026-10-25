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
