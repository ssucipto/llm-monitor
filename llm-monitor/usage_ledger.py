"""usage_ledger.py v1.0 — the usage ledger: numbers-only token usage of Claude Code and Hermes (M78; Homelab B-89 T14, ADR-022).
Reads numbers only: token counts, timestamps, models, session ids, repo paths.
Never reads message text, titles or prompts: those columns are never selected and nothing is ever stored from them.
Storage: its own SQLite file (usage_event rows + usage_cursor byte cursors), WAL so the dashboard can read while we write.
v1.1 (M78-H5, Homelab review-043 CR-009/CR-011): LLM_MONITOR_EXECUTOR_MODELS sets the executor models and /api/usage names
them (executor_models); the repo filter stops at a path boundary."""
import json
import os
import sqlite3
import time
from datetime import datetime, timezone

# the models that run executors: their Hermes rows are executor usage, not orchestrator usage. A new quant or model name
# goes in LLM_MONITOR_EXECUTOR_MODELS (comma-separated); otherwise it would read as executor 0 with Hermes "ok" (M78-H5)
EXECUTOR_MODELS = tuple(m.strip() for m in (os.environ.get("LLM_MONITOR_EXECUTOR_MODELS")
                                            or "strata-iq3_s,qwen3.8-flash-next-iq3_s").split(",") if m.strip())
WEIGHTS = {"input": 1.0, "cache_write_5m": 1.25, "cache_write_1h": 2.0, "cache_read": 0.1, "output": 5.0}


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_window(frm: str, to: str):
    """ISO 8601 with a trailing Z -> (epoch, epoch); ValueError when either does not parse or frm > to."""
    def one(s):
        try:
            dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError):
            raise ValueError(f"not an ISO 8601 Z timestamp: {s!r}")
        return dt.replace(tzinfo=timezone.utc).timestamp()

    f, t = one(frm), one(to)
    if f > t:
        raise ValueError(f"frm {frm} is after to {to}")
    return f, t


def connect(path):
    """Open (create if missing) the ledger DB; WAL plus a busy timeout so readers and this writer coexist."""
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    con.execute(
        "CREATE TABLE IF NOT EXISTS usage_event (source TEXT, msg_key TEXT, session TEXT, t REAL, t_end REAL,"
        " model TEXT, repo TEXT, sidechain INTEGER, task TEXT,"
        " input INTEGER, output INTEGER, cache_write INTEGER, cache_write_5m INTEGER, cache_write_1h INTEGER,"
        " cache_read INTEGER, reasoning INTEGER)")
    con.execute("CREATE TABLE IF NOT EXISTS usage_cursor (file TEXT PRIMARY KEY, offset INTEGER, mtime REAL)")
    # the unique key is what makes every ingest idempotent: re-reading a source never double counts
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_event ON usage_event(source, msg_key)")
    # M78-H4 repair, once: rows stored with no time (before H4) are dropped and every cursor reset, so the next pass reads them again
    if con.execute("DELETE FROM usage_event WHERE source = 'claude_code' AND t IS NULL").rowcount:
        con.execute("DELETE FROM usage_cursor")
    con.commit()
    return con


def ingest_hermes(con, db_path):
    """Pull per-session model usage from a Hermes state.db, read-only; a read problem is a status, never zeros."""
    if not os.path.exists(db_path):
        return {"status": "missing", "rows": 0}
    try:
        src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2)
    except sqlite3.Error as e:
        return {"status": f"error: {e}", "rows": 0}
    try:
        # numbers and paths only: title and system_prompt are never selected; the count columns are qualified
        # because both joined tables have input_tokens / output_tokens / cache_read_tokens
        rows = src.execute(
            "SELECT u.session_id, u.model, u.task, u.first_seen, u.last_seen, u.input_tokens, u.output_tokens,"
            " u.cache_read_tokens, u.cache_write_tokens, u.reasoning_tokens, coalesce(s.git_repo_root, s.cwd)"
            " FROM session_model_usage u JOIN sessions s ON s.id = u.session_id").fetchall()
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        if "locked" in msg:
            return {"status": "error: locked", "rows": 0}
        return {"status": "error: schema", "rows": 0}
    finally:
        try:
            src.close()
        except sqlite3.Error as e:
            print(f"[usage] closing the Hermes DB failed: {e}")
    for session_id, model, task, first_seen, last_seen, i_t, o_t, cr, cw, reason, repo in rows:
        key = f"{session_id}:{model}:{task}"
        con.execute(
            "INSERT INTO usage_event (source, msg_key, session, t, t_end, model, repo, sidechain, task,"
            " input, output, cache_write, cache_write_5m, cache_write_1h, cache_read, reasoning)"
            " VALUES ('hermes', ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 0, 0, ?, ?)"
            " ON CONFLICT(source, msg_key) DO UPDATE SET t_end = excluded.t_end, input = excluded.input,"
            " output = excluded.output, cache_write = excluded.cache_write, cache_read = excluded.cache_read,"
            " reasoning = excluded.reasoning",
            (key, session_id, first_seen, last_seen, model, repo, task,
             i_t, o_t, cw, cr, reason))
    con.commit()
    return {"status": "ok", "rows": len(rows)}


def iso_epoch(s):
    """ISO 8601 timestamp with a zone (Z or +hh:mm) -> epoch seconds; None when it does not parse or has no zone.
    Claude Code writes milliseconds (2026-10-25T09:42:25.123Z): 1.0 parsed only whole seconds (M78-H4)."""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None
    return dt.timestamp() if dt.tzinfo else None


def ingest_claude(con, root, budget_s=5.0):
    """Read Claude Code transcripts under root (sub-folders hold subagent transcripts) from saved byte cursors.
    Only numbers go into the DB: never message content."""
    stats = {"files": 0, "lines": 0, "added": 0, "skipped": 0, "partial": False}
    deadline = time.monotonic() + budget_s
    files = []
    for dirpath, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(".jsonl"):
                files.append(os.path.join(dirpath, f))
    for path in sorted(files):
        if time.monotonic() >= deadline:  # budget used: stop starting new files; the cursors keep the place
            stats["partial"] = True
            break
        stats["files"] += 1
        row = con.execute("SELECT offset FROM usage_cursor WHERE file = ?", (path,)).fetchone()
        offset = row[0] if row else 0
        size = os.path.getsize(path)
        if size < offset:  # rotated or rewritten: read again from 0 (the unique key prevents double counting)
            offset = 0
        with open(path, "rb") as fh:
            fh.seek(offset)
            data = fh.read()
        end = data.rfind(b"\n") + 1  # only complete lines; a line still being written waits for the next pass
        for ln in data[:end].split(b"\n"):
            if not ln.strip():
                continue
            stats["lines"] += 1
            try:
                j = json.loads(ln)
            except (ValueError, UnicodeDecodeError):
                stats["skipped"] += 1
                continue
            m = j.get("message")
            u = m.get("usage") if isinstance(m, dict) else None
            if j.get("type") != "assistant" or not isinstance(u, dict):
                continue  # every other line type is ignored, not skipped
            ts = iso_epoch(j.get("timestamp"))
            if ts is None:  # no usable time: a row with no time falls in no window, so it is skipped, never stored (M78-H4)
                stats["skipped"] += 1
                continue
            cc = u.get("cache_creation") or {}
            cur = con.execute(
                "INSERT OR IGNORE INTO usage_event (source, msg_key, session, t, t_end, model, repo, sidechain, task,"
                " input, output, cache_write, cache_write_5m, cache_write_1h, cache_read, reasoning)"
                " VALUES ('claude_code', ?, ?, ?, NULL, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, 0)",
                (f"{m.get('id')}:{j.get('requestId')}", j.get("sessionId"), ts,
                 m.get("model"), j.get("cwd"), 1 if j.get("isSidechain") else 0,
                 u.get("input_tokens", 0), u.get("output_tokens", 0), u.get("cache_creation_input_tokens", 0),
                 cc.get("ephemeral_5m_input_tokens", 0), cc.get("ephemeral_1h_input_tokens", 0),
                 u.get("cache_read_input_tokens", 0)))
            stats["added"] += cur.rowcount
        con.execute("INSERT INTO usage_cursor (file, offset, mtime) VALUES (?, ?, ?)"
                    " ON CONFLICT(file) DO UPDATE SET offset = excluded.offset, mtime = excluded.mtime",
                    (path, offset + end, os.path.getmtime(path)))
    con.commit()
    return stats


def norm_repo(p):
    return (p or "").replace("\\", "/").rstrip("/").lower()


def _rows(con, f, t, repo, session):
    """The window's orchestrator (Claude Code) and executor (Hermes) rows, after the repo/session filters."""
    def keep(rows):
        out = []
        for r in rows:
            want = norm_repo(repo) if repo is not None else None
            if want is not None and not (norm_repo(r[6]) == want or norm_repo(r[6]).startswith(want + "/")):  # a path boundary (M78-H5)
                continue
            if session is not None and r[2] != session:  # session column
                continue
            out.append(r)
        return out

    orch = keep(con.execute("SELECT * FROM usage_event WHERE source='claude_code' AND t >= ? AND t <= ?", (f, t)).fetchall())
    ms = tuple(EXECUTOR_MODELS)
    ex = keep(con.execute("SELECT * FROM usage_event WHERE source='hermes' AND model IN (%s) AND t <= ? AND t_end >= ?"
                          % ",".join("?" * len(ms)), (*ms, t, f)).fetchall()) if ms else []
    return orch, ex


def _block(rows, keys):
    """Sums plus messages/sessions/models for a set of usage_event rows."""
    cols = {"input": 9, "output": 10, "cache_write": 11, "cache_write_5m": 12, "cache_write_1h": 13,
            "cache_read": 14, "reasoning": 15}
    b = {k: sum(r[cols[k]] or 0 for r in rows) for k in keys}
    if "messages" not in b:
        b["messages"] = len(rows)
    b["sessions"] = len({r[2] for r in rows})
    models = {}
    for r in rows:
        models[r[5]] = models.get(r[5], 0) + 1
    b["models"] = models
    return b


def summary(con, frm, to, repo=None, session=None, status=None, partial=False):
    """The contract's usage summary: orchestrator (Claude Code) and executor (Hermes) blocks for a window."""
    f, t = parse_window(frm, to)
    status = status if status is not None else {}
    orch_rows, ex_rows = _rows(con, f, t, repo, session)
    orch = _block(orch_rows, ("input", "output", "cache_write", "cache_write_5m", "cache_write_1h", "cache_read"))
    ex = _block(ex_rows, ("input", "output", "cache_write", "cache_read", "reasoning"))
    orch = None if status.get("claude_code") != "ok" else orch
    ex = None if status.get("hermes") != "ok" else ex
    if orch is None:
        w_orch = None
    else:
        w_orch = (orch["input"] + 1.25 * orch["cache_write_5m"] + 2.0 * orch["cache_write_1h"]
                  + 1.25 * (orch["cache_write"] - orch["cache_write_5m"] - orch["cache_write_1h"])
                  + 0.1 * orch["cache_read"] + 5 * orch["output"])
    if ex is None:
        w_ex = None
    else:
        w_ex = ex["input"] + 1.25 * ex["cache_write"] + 0.1 * ex["cache_read"] + 5 * ex["output"]
    return {"window": {"from": frm, "to": to}, "orchestrator": orch, "executor": ex,
            "weighted": {"orchestrator": w_orch, "executor": w_ex, "weights": WEIGHTS},
            "sources": status, "partial": partial, "generated_at": iso(time.time()),
            "executor_models": list(EXECUTOR_MODELS)}   # additive (M78-H5): what counts as executor usage


def sessions(con, frm, to, repo=None, session=None):
    """One row per (role, session) in the window: id, span, model, repo and token sums."""
    f, t = parse_window(frm, to)
    orch_rows, ex_rows = _rows(con, f, t, repo, session)
    out = []
    for role, rows in (("orchestrator", orch_rows), ("executor", ex_rows)):
        groups = {}
        for r in rows:
            groups.setdefault(r[2], []).append(r)
        for sid, g in groups.items():
            starts = [r[3] for r in g if r[3] is not None]
            ends = [r[4] for r in g if r[4] is not None] or starts
            models = [r[5] for r in g]
            out.append({"source": g[0][0], "role": role, "id": sid,
                        "start": iso(min(starts)) if starts else None,
                        "end": iso(max(ends)) if ends else None,
                        "model": max(set(models), key=models.count), "repo": g[0][6],   # the most used (spec)
                        "input": sum(r[9] or 0 for r in g), "output": sum(r[10] or 0 for r in g),
                        "cache_write": sum(r[11] or 0 for r in g), "cache_read": sum(r[14] or 0 for r in g)})
    return out
