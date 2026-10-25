"""M78-H4 spec (tier T0, exact text): Claude Code timestamps carry milliseconds; usage_ledger 1.0 stored every orchestrator row
with t = NULL (a fail-open read: the orchestrator side of every window was 0). Found live after H3 (Homelab LEDGER M78-H3)."""
LEDGER, TEST, EXP, CL = "llm-monitor/usage_ledger.py", "tests/usage/test_usage_ledger.py", "tests/usage/expected.txt", "CHANGELOG.md"

LEDGER_EDITS = [
    ('''def iso_epoch(s):
    """ISO 8601 Z timestamp -> epoch seconds (parse_window's rule); None when it does not parse."""
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None
''', '''def iso_epoch(s):
    """ISO 8601 timestamp with a zone (Z or +hh:mm) -> epoch seconds; None when it does not parse or has no zone.
    Claude Code writes milliseconds (2026-10-25T09:42:25.123Z): 1.0 parsed only whole seconds (M78-H4)."""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None
    return dt.timestamp() if dt.tzinfo else None
'''),
    ('''            cc = u.get("cache_creation") or {}
''', '''            ts = iso_epoch(j.get("timestamp"))
            if ts is None:  # no usable time: a row with no time falls in no window, so it is skipped, never stored (M78-H4)
                stats["skipped"] += 1
                continue
            cc = u.get("cache_creation") or {}
'''),
    ('''                (f"{m.get('id')}:{j.get('requestId')}", j.get("sessionId"), iso_epoch(j.get("timestamp")),
''', '''                (f"{m.get('id')}:{j.get('requestId')}", j.get("sessionId"), ts,
'''),
    ('''    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_event ON usage_event(source, msg_key)")
    con.commit()
''', '''    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_event ON usage_event(source, msg_key)")
    # M78-H4 repair, once: rows stored with no time (before H4) are dropped and every cursor reset, so the next pass reads them again
    if con.execute("DELETE FROM usage_event WHERE source = 'claude_code' AND t IS NULL").rowcount:
        con.execute("DELETE FROM usage_cursor")
    con.commit()
'''),
]

TEST_BLOCK = '''# M78-H4: real Claude Code timestamps carry milliseconds; a record whose time does not parse is skipped, never stored with no time
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
    with open(os.path.join(proj, "D--Project-Homelab", "s4.jsonl"), "w", encoding="utf8", newline="\\n") as f:
        f.write(json.dumps(good) + "\\n" + json.dumps(bad) + "\\n")
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

'''
TEST_EDITS = [('print("ALL PASSED (simulated)" if not fails else f"{len(fails)} FAILED")\n',
               TEST_BLOCK + 'print("ALL PASSED (simulated)" if not fails else f"{len(fails)} FAILED")\n')]
EXP_EDITS = [("test_usage_ledger.py 24\n", "test_usage_ledger.py 29\n")]
CL_EDITS = [("## [0.1.13] - 2026-10-25\n", "## [0.1.14] - 2026-10-25\n\n### Fixed\n"
             "- Usage ledger (M78-H4): Claude Code timestamps with milliseconds were not parsed, so every orchestrator row was stored "
             "with no time and every window read 0 for Claude Code. They now parse; a record with no usable time is skipped and counted; "
             "the rows stored without a time are removed once and re-read (5 new cases, 29 in all).\n\n## [0.1.13] - 2026-10-25\n")]

# exact decision lines of the spec (the '~' form matches the stripped line); each must be caught by the new cases
MUTANTS = [
    (LEDGER, "~dt = datetime.fromisoformat(s.replace(\"Z\", \"+00:00\"))", "dt = datetime.strptime(s, \"%Y-%m-%dT%H:%M:%SZ\").replace(tzinfo=timezone.utc)"),
    (LEDGER, "~return dt.timestamp() if dt.tzinfo else None", "return dt.timestamp()"),
    (LEDGER, "~if ts is None:  # no usable time: a row with no time falls in no window, so it is skipped, never stored (M78-H4)", "if False:"),
    (LEDGER, "~con.execute(\"DELETE FROM usage_cursor\")", "pass"),
    (LEDGER, "~if con.execute(\"DELETE FROM usage_event WHERE source = 'claude_code' AND t IS NULL\").rowcount:", "if True:"),
]
