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

# M78-H4: real Claude Code timestamps carry milliseconds; a record whose time does not parse is skipped, never stored with no time
MS = "2026-10-25T09:42:25.123Z"
expect("iso_epoch: a millisecond Z timestamp (Claude Code) parses", abs((ul.iso_epoch(MS) or 0) - 1792921345.123) < 1e-6, ul.iso_epoch(MS))
expect("iso_epoch: an offset timestamp parses; a naive one or junk does not",
       ul.iso_epoch("2026-10-25T09:42:25+00:00") == 1792921345.0 and ul.iso_epoch("2026-10-25T09:42:25") is None and ul.iso_epoch("x") is None)
tmp4 = tempfile.mkdtemp(prefix="m78-h4-")
try:
    proj = os.path.join(tmp4, "projects")
    os.makedirs(os.path.join(proj, "D--Project-Homelab"))
    good, bad = json.loads(msg("m9", "r9", T0)), json.loads(msg("m8", "r8", T0))
    good["timestamp"], bad["timestamp"] = MS, "not a time"
    with open(os.path.join(proj, "D--Project-Homelab", "s4.jsonl"), "w", encoding="utf8", newline="\n") as f:
        f.write(json.dumps(good) + "\n" + json.dumps(bad) + "\n")
    db4 = os.path.join(tmp4, "u.sqlite3")
    con4 = ul.connect(db4)
    st4 = ul.ingest_claude(con4, proj)
    ts4 = [r[0] for r in con4.execute("SELECT t FROM usage_event WHERE source = 'claude_code'")]
    expect("ingest_claude: the millisecond record keeps its time; the one with no usable time is skipped",
           len(ts4) == 1 and abs((ts4[0] or 0) - 1792921345.123) < 1e-6 and st4["skipped"] == 1, (ts4, st4))
    con4.execute("INSERT INTO usage_event (source, msg_key, t) VALUES ('claude_code', 'old:1', NULL)")
    con4.commit()
    con4.close()
    con4 = ul.connect(db4)
    left = con4.execute("SELECT COUNT(*) FROM usage_event WHERE t IS NULL").fetchone()[0]
    curs = con4.execute("SELECT COUNT(*) FROM usage_cursor").fetchone()[0]
    expect("connect: rows stored with no time are removed and the cursors reset", left == 0 and curs == 0, (left, curs))
    st5 = ul.ingest_claude(con4, proj)
    con4.close()
    con4 = ul.connect(db4)
    n4 = con4.execute("SELECT COUNT(*) FROM usage_event WHERE source = 'claude_code'").fetchone()[0]
    curs = con4.execute("SELECT COUNT(*) FROM usage_cursor").fetchone()[0]
    expect("after the repair: the file is read again once (no double count) and a clean connect keeps the cursors",
           n4 == 1 and st5["added"] == 0 and curs == 1, (n4, st5, curs))
    con4.close()
finally:
    shutil.rmtree(tmp4, ignore_errors=True)

print("ALL PASSED (simulated)" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
