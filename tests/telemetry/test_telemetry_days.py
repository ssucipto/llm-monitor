"""telemetry day rollup tests (llm-monitor M81-T3, audit-33 a33-13 + audit-34 G-34-03) — SIMULATED.

A temp sqlite file created by the real db_init() and synthetic poll rows: no real engine,
no real telemetry.sqlite3, nothing leaves the runner. One PASS line per case.

Run: py -3.12 tests/telemetry/run-tests.py   (or python3 on Linux)
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
_tmp = tempfile.mkdtemp(prefix="m81-days-")
os.environ["LLM_MONITOR_DB"] = os.path.join(_tmp, "days.sqlite3")

sys.path.insert(0, os.path.join(HERE, "..", "..", "llm-monitor"))
import server  # noqa: E402

fails = []


def expect(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -- {str(detail)[:300]}"))
    if not ok:
        fails.append(name)


INSERT_COLS = ["t", "cpu", "ram", "tok_s", "prefill", "ctx_used", "ctx_pct", "hit_pct",
               "accept_pct", "reqs", "prompt_tokens", "reused", "output_tokens", "power_w",
               "power_src", "gpu_util", "gpu_power", "busy", "vram_used", "vram_total",
               "drafts_offered", "drafts_accepted", "pcie_share", "prompt_ms"]


def row(t, *, tok_s=None, prefill=None, reqs=0, prompt=0, reused=0, output=0,
        power_w=100.0, busy=0, offered=0, accepted=0, prompt_ms=None,
        hit_pct=None, accept_pct=None):
    # hit_pct/accept_pct default to None because most day tests do not care about them;
    # the a33-08 case sets them to session-cumulative values, which is what makes the
    # mean-of-ratios wrong in production.
    return (t, 10.0, 1000.0, tok_s, prefill, 100.0, 1.0, hit_pct, accept_pct, reqs,
            prompt, reused, output, power_w, "modelled", None, None, busy, 100.0, 24576.0,
            offered, accepted, None, prompt_ms)


def fresh():
    con = server.db_init()
    con.execute("DELETE FROM poll")
    con.execute("DELETE FROM day")
    con.commit()
    return con


def insert(con, rows):
    ph = ",".join("?" * len(INSERT_COLS))
    con.executemany(f"INSERT INTO poll ({', '.join(INSERT_COLS)}) VALUES ({ph})", rows)
    con.commit()


# Anchor a day to UTC midnight so the 24-hour bucketing is deterministic.
DAY = 1792512000  # 2026-10-22T00:00:00Z

# ---------- a33-13: a 0-request day must not roll up a stale rate ----------
con = fresh()
rows = [row(DAY + i * 60, tok_s=48.9, prefill=173582.0, reqs=0, prompt=0, reused=0,
            output=0, busy=0) for i in range(20)]
insert(con, rows)
agg = server.day_aggregates(con, DAY, DAY + 86400)
expect("a day with 0 requests and 0 tokens rolls up no tok/s mean (was a stale 48.9)",
       agg["tok_s_mean"] is None, agg["tok_s_mean"])
expect("the same day rolls up no tok/s max", agg["tok_s_max"] is None, agg["tok_s_max"])
expect("and no prefill mean, so week/month weighted means stop inheriting it",
       agg["prefill_mean"] is None, agg["prefill_mean"])
expect("the day is still recorded (polls and idle are true even with no work)",
       agg["polls"] == 20 and agg["idle_pct"] == 100.0, (agg["polls"], agg["idle_pct"]))

con = fresh()
rows = [row(DAY + i * 60, tok_s=40.0, prefill=300.0, reqs=1 + i, prompt=1000 + i * 100,
            reused=500 + i * 50, output=20 + i * 5, busy=1) for i in range(20)]
insert(con, rows)
agg = server.day_aggregates(con, DAY, DAY + 86400)
expect("a working day still gets its tok/s mean (the guard is not a blanket null)",
       agg["tok_s_mean"] == 40.0, agg["tok_s_mean"])

# ---------- G-34-03: movement across the day boundary used to land in no day ----------
# Exactly the shape recorded in audit-34: rows (DAY-300,5) (DAY+600,8) (DAY+4000,12).
con = fresh()
insert(con, [row(DAY - 300, reqs=5), row(DAY + 600, reqs=8), row(DAY + 4000, reqs=12)])
agg = server.day_aggregates(con, DAY, DAY + 86400)
expect("the day carries the previous day's last row as its delta baseline (7, not 4)",
       agg["requests"] == 7, agg["requests"])
expect("the baseline row is not counted in the day's own polls",
       agg["polls"] == 2, agg["polls"])
expect("hour buckets still sum to the day's requests (the invariant holds, do not 'fix' it)",
       sum(agg["hours"]) == agg["requests"], (agg["hours"], agg["requests"]))

# The old code lost the first hour entirely; prove the movement is now attributed.
con = fresh()
insert(con, [row(DAY - 10, reqs=3), row(DAY + 60, reqs=9)])
agg = server.day_aggregates(con, DAY, DAY + 86400)
expect("a single row in the first hour still reports its movement (6)",
       agg["requests"] == 6 and agg["hours"][0] == 6, (agg["requests"], agg["hours"][:2]))

# A day sampled once used to produce no rollup at all.
con = fresh()
insert(con, [row(DAY - 10, reqs=4), row(DAY + 60, reqs=9)])
agg = server.day_aggregates(con, DAY, DAY + 86400)
expect("a day sampled once now yields a rollup instead of None", agg is not None, agg)

# With no earlier row there is no baseline: the first segment contributes only its own
# movement (cumulative_delta's documented behaviour), which must not invent requests.
con = fresh()
insert(con, [row(DAY + 100, reqs=4), row(DAY + 600, reqs=9)])
agg = server.day_aggregates(con, DAY, DAY + 86400)
expect("with no baseline at all, the day reports its own movement (5)",
       agg["requests"] == 5, agg["requests"])

# M81-review S3: the G-34-03 fix carried ANY earlier row as the baseline, so after an
# outage a whole gap's counter movement was charged to one day. Two days of inactivity
# followed by one busy day must not give that day the outage's tokens.
con = fresh()
insert(con, [row(DAY - 2 * 86400, reqs=3, prompt=1000, reused=0, output=0),
             row(DAY + 600, reqs=5, prompt=1600, reused=0, output=10, busy=1),
             row(DAY + 4000, reqs=8, prompt=2400, reused=0, output=20, busy=1)])
agg = server.day_aggregates(con, DAY, DAY + 86400)
expect("a baseline older than a day is not this day's context (3 requests, not 5)",
       agg["requests"] == 3, agg["requests"])
expect("the same outage does not charge two days of prompt tokens to one day (800, not 1400)",
       agg["prompt_tokens"] == 800, agg.get("prompt_tokens"))
# A baseline inside the window still works — the bound must not undo G-34-03.
con = fresh()
insert(con, [row(DAY - 7200, reqs=3, prompt=1000, reused=0, output=0),
             row(DAY + 600, reqs=5, prompt=1600, reused=0, output=10, busy=1)])
agg = server.day_aggregates(con, DAY, DAY + 86400)
expect("a baseline two hours old is still used (2 requests attributed across the boundary)",
       agg["requests"] == 2, agg["requests"])

# ---------- a33-10: the rollup bounds impossible prefill too ----------
con = fresh()
rows = [row(DAY + i * 60, tok_s=40.0, prefill=p, reqs=1 + i, prompt=1000 + i * 100,
            output=50 + i * 10, busy=1)
        for i, p in enumerate([300.0, 400.0, 1_210_150.0, 200.0])]
insert(con, rows)
agg = server.day_aggregates(con, DAY, DAY + 86400)
expect("a day's prefill mean excludes the impossible samples",
       abs(agg["prefill_mean"] - 300.0) < 0.01, agg["prefill_mean"])
expect("the rollup records that a bound fired, so history stays explainable",
       agg["prefill_bounded"] is True, agg["prefill_bounded"])

# ---------- a33-08: the day's hit rate is its own ratio ----------
con = fresh()
rows = [row(DAY + i * 60, reqs=1 + i, prompt=1000 + i * 1000, reused=900 + i * 100,
            output=10, busy=1, offered=100 + i * 100, accepted=90 + i * 10,
            hit_pct=95.0, accept_pct=80.0)
        for i in range(5)]
insert(con, rows)
agg = server.day_aggregates(con, DAY, DAY + 86400)
# reused delta 400 over prompt delta 4000 -> 10 %; accepted 40 over offered 400 -> 10 %
expect("the day's hit_mean is the day's own ratio (10%), not a mean of session ratios (95%)",
       abs(agg["hit_mean"] - 10.0) < 0.01, agg["hit_mean"])
expect("the day's accept_mean uses the draft counters (10%), not the per-poll ratio",
       abs(agg["accept_mean"] - 10.0) < 0.01, agg["accept_mean"])

# ---------- db_finalize_days writes what day_aggregates computed ----------
con = fresh()
insert(con, [row(DAY + i * 60, tok_s=40.0, prefill=300.0, reqs=1 + i, prompt=1000 + i * 100,
                 reused=500 + i * 50, output=20 + i * 5, busy=1) for i in range(20)])
# latest poll must be on a later day for DAY to count as "ended"
insert(con, [row(DAY + 86400 + 60, reqs=1, prompt=10, output=1)])
server.db_finalize_days(con)
stored = con.execute(
    "SELECT reqs, tok_mean, prefill_mean, hit_mean, accept_mean FROM day WHERE d = ?",
    (int(DAY // 86400),)).fetchone()
# reqs is the day's counter movement (1..20 -> 19), not a sum of the stored counters.
expect("the frozen day row carries the corrected numbers",
       stored == (19, 40.0, 300.0, 50.0, None), stored)

# ---------- a33-17: hourly path with duplicate timestamps ----------
con = fresh()
insert(con, [row(DAY + 60, tok_s=40.0, reqs=5, prompt=100, output=20, busy=1) for _ in range(6)])
h = server.db_hour_aggregates(con, DAY, DAY + 3600)
expect("an hourly span of duplicate timestamps yields no req_per_min (no 1e-9 division)",
       h["req_per_min"] is None, h["req_per_min"])
expect("the hourly span is reported as 0 rather than a sentinel",
       h["span_s"] == 0.0, h["span_s"])
con = fresh()
insert(con, [row(DAY + i * 60, tok_s=40.0, reqs=1 + i, prompt=100 + i * 10, reused=50 + i * 5,
                 output=20 + i * 2, busy=1, prefill=p)
             for i, p in enumerate([300.0, 400.0, 1_210_150.0, 200.0, 250.0, 350.0])])
h = server.db_hour_aggregates(con, DAY, DAY + 3600)
expect("the hourly path gains the same window ratios", h["hit_pct_window"] == 50.0,
       h["hit_pct_window"])
# The bound must be applied by db_hour_aggregates itself, not just by the helper: assert
# on the record it returns, or a hour path that stopped calling bounded_prefill would pass.
expect("and the same bounded prefill (a 1.2M sample cannot reach an hourly peak)",
       h["prefill_max"] == 400.0 and h["prefill_bounded"] is True,
       (h["prefill_max"], h["prefill_bounded"]))

# ---------- db_periods must not inherit ghost rates across days ----------
# Two rollup days plus a marker poll on a third day, so both are "ended" and get frozen.
con = fresh()
quiet = [row(DAY + i * 60, tok_s=48.9, reqs=0, prompt=0, output=0, busy=0) for i in range(10)]
busy_rows = [row(DAY + 86400 + i * 60, tok_s=40.0, reqs=1 + i, prompt=1000 + i * 100,
                 reused=500 + i * 50, output=20 + i * 5, busy=1) for i in range(10)]
insert(con, quiet + busy_rows + [row(DAY + 2 * 86400 + 60, reqs=1, prompt=10, output=1)])
server.db_finalize_days(con)
dlist = server.db_daily(con)
expect("both ended days were frozen (the quiet one included)", len(dlist) == 2,
       [d.get("d") for d in dlist])
# Both days fall in the current calendar month, so the month block spans them.
cur = (server.db_periods(dlist).get("month") or {}).get("current") or {}
expect("a quiet day contributes no ghost tok/s to the month's weighted mean",
       cur.get("tok_s_mean") == 40.0, (cur.get("tok_s_mean"),
                                       [d.get("tok_mean") for d in dlist]))

con.close()
print("ALL PASSED (simulated)" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
