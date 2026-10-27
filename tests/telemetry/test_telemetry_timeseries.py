"""telemetry timeseries tests (llm-monitor M81-T4, audit-33 a33-19/a33-20/a33-21) — SIMULATED.

A temp sqlite file created by the real db_init() and synthetic poll/day rows: no real engine,
no real telemetry.sqlite3, nothing leaves the runner. One PASS line per case.

Run: py -3.12 tests/telemetry/run-tests.py   (python3 on Linux)
"""
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# Must be set before server is imported: DB_PATH reads it at import time (M81-T8 step 1).
_tmp = tempfile.mkdtemp(prefix="m81-timeseries-")
os.environ["LLM_MONITOR_DB"] = os.path.join(_tmp, "poll.sqlite3")

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


def row(t, *, tok_s=None, prefill=None, reqs=0, prompt=0, reused=0, output=0, busy=1):
    return (t, 10.0, 1000.0, tok_s, prefill, 100.0, 1.0, None, None, reqs,
            prompt, reused, output, 100.0, "modelled", None, None, busy, 100.0, 24576.0,
            0, 0, None, None)


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


NOW = server.datetime.now(server.timezone.utc).timestamp()
# Anchor an ended day two days back so the 7d window covers it and it counts as frozen.
DAY = (int(NOW // 86400) - 2) * 86400

# ---------- a33-21: every bucket states whether it was observed ----------
con = fresh()
# Polls only in the last two minutes of a 15-minute window: most buckets are gaps.
rows = []
for i in range(8):
    t = NOW - 100 + i * 10
    rows.append(row(t, tok_s=40.0, prefill=300.0, reqs=1 + i, prompt=1000 + i * 100,
                    output=100 + i * 10))
insert(con, rows)
ts = server.db_timeseries(con, "15m")
expect("every bucket carries a sample count so a gap is distinguishable from zero activity",
       all("samples" in b for b in ts["buckets"]), sorted(ts["buckets"][0])[:8])
empty = sum(1 for b in ts["buckets"] if not b["samples"])
expect("the unobserved buckets are counted, not silently drawn as zero",
       empty > 0 and ts["empty_buckets"] == empty, (empty, ts.get("empty_buckets")))
expect("the observed buckets report their real sample counts",
       sum(b["samples"] for b in ts["buckets"]) == 8,
       sum(b["samples"] for b in ts["buckets"]))
expect("the payload states how many buckets the range has",
       ts["n_buckets"] == len(ts["buckets"]) == 30, ts.get("n_buckets"))

# ---------- a33-19: the chart path bounds impossible prefill like every other path ----------
con = fresh()
rows = [row(NOW - 200 + i * 40, tok_s=40.0, reqs=1 + i, prompt=1000 + i * 100,
            output=100 + i * 10, prefill=p)
        for i, p in enumerate([300.0, 400.0, 1_905_830.0, 200.0])]
insert(con, rows)
ts = server.db_timeseries(con, "15m")
filled = [b for b in ts["buckets"] if b["samples"]]
peaks = [b["prefill_max"] for b in filled if b["prefill_max"] is not None]
expect("the chart path still yields peaks to check (guards the next two from a vacuous pass)",
       bool(filled) and bool(peaks), (len(filled), peaks))
expect("no 1.9M tok/s prefill sample reaches a chart bucket",
       peaks and max(peaks) <= server.PREFILL_CEILING_TOK_S, peaks)
expect("the bucket says a bound fired so the front end can tag it",
       any(b.get("prefill_bounded") for b in filled), [b.get("prefill_bounded") for b in filled])
expect("the summary carries the bound flag too",
       ts["summary"]["prefill_bounded"] is True, ts["summary"].get("prefill_bounded"))

# ---------- a33-19: the bound flag is stored, so day ranges can still say "· bounded" ----------
con = fresh()
insert(con, [row(DAY + i * 120, tok_s=40.0, reqs=1 + i, prompt=1000 + i * 100,
                 reused=200 + i * 20, output=50 + i * 5, prefill=p)
             for i, p in enumerate([300.0, 400.0, 1_210_150.0, 200.0])])
insert(con, [row(DAY + 86400 + 60, reqs=1, prompt=10, output=1)])
server.db_finalize_days(con)
expect("the frozen day row stores that a bound fired",
       con.execute("SELECT prefill_bounded FROM day WHERE d = ?",
                   (int(DAY // 86400),)).fetchone()[0] == 1, "flag not stored")
expect("db_daily reports the stored bound flag",
       next(d for d in server.db_daily(con) if d["d"] == int(DAY // 86400))["prefill_bounded"] is True,
       [d.get("prefill_bounded") for d in server.db_daily(con)])

# ---------- a33-19: day ranges get a real prefill peak ----------
con = fresh()
insert(con, [row(DAY + i * 120, tok_s=40.0, reqs=1 + i, prompt=1000 + i * 100,
                 reused=200 + i * 20, output=50 + i * 5, prefill=p)
             for i, p in enumerate([300.0, 400.0, 1_210_150.0, 200.0])])
# marker poll on a later day so DAY counts as ended and gets frozen
insert(con, [row(DAY + 86400 + 60, reqs=1, prompt=10, output=1)])
server.db_finalize_days(con)
stored = con.execute("SELECT prefill_mean, prefill_max FROM day WHERE d = ?",
                     (int(DAY // 86400),)).fetchone()
expect("the frozen day row stores a bounded prefill max (a33-19)",
       stored[1] is not None and stored[1] <= server.PREFILL_CEILING_TOK_S, stored)

ts = server.db_timeseries(con, "7d")
day_bucket = next(b for b in ts["buckets"] if b["t"] // 86400 == DAY // 86400)
expect("the 7d bucket carries that peak instead of a hard-coded None",
       day_bucket["prefill_max"] == stored[1], (day_bucket["prefill_max"], stored))
expect("the day bucket reports its poll count as samples",
       day_bucket["samples"] > 0, day_bucket["samples"])

# A day frozen BEFORE the column existed holds an unbounded mean that cannot be
# recomputed (its poll rows are pruned), so nothing about its prefill is published.
con = fresh()
con.execute(
    "INSERT INTO day (d, polls, span_s, reqs, prompt, reused, output, tok_mean, tok_max,"
    " prefill_mean, hit_mean, accept_mean, power_mean, energy_wh, idle_pct, hours)"
    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    (int(DAY // 86400), 10, 3600.0, 5, 1000, 200, 500, 40.0, 55.0, 310.0, 90.0, 70.0,
     120.0, 10.0, 20.0, "[]"))
con.commit()
ts = server.db_timeseries(con, "7d")
old_bucket = next(b for b in ts["buckets"] if b["t"] // 86400 == DAY // 86400)
expect("a prefill_max-less day row is treated as pre-bound: no mean, no peak, not a copied mean",
       old_bucket["prefill_max"] is None and old_bucket["prefill_mean"] is None,
       (old_bucket["prefill_max"], old_bucket["prefill_mean"]))
expect("the day panel says why rather than showing an impossible number",
       next(d for d in server.db_daily(con) if d["d"] == int(DAY // 86400)).get("prefill_note")
       == "pre-bound record",
       [d.get("prefill_note") for d in server.db_daily(con)])
# The raw stored value must survive for export/re-derivation even though it is not published.
expect("the raw stored mean is still readable by an exporter",
       con.execute("SELECT prefill_mean FROM day WHERE d = ?",
                   (int(DAY // 86400),)).fetchone()[0] == 310.0, "raw value lost")

# ---------- the day table migration itself ----------
old_db = os.path.join(_tmp, "old-schema.sqlite3")
legacy = sqlite3.connect(old_db)
legacy.execute(
    "CREATE TABLE poll (t REAL, cpu REAL, ram REAL, tok_s REAL, prefill REAL,"
    " ctx_used REAL, ctx_pct REAL, hit_pct REAL, accept_pct REAL, reqs INTEGER,"
    " prompt_tokens INTEGER, reused INTEGER, output_tokens INTEGER, power_w REAL,"
    " power_src TEXT, gpu_util REAL, gpu_power REAL, busy INTEGER)"
)
legacy.execute(
    "CREATE TABLE day (d INTEGER, polls INTEGER, span_s REAL, reqs INTEGER, prompt INTEGER,"
    " reused INTEGER, output INTEGER, tok_mean REAL, tok_max REAL, prefill_mean REAL,"
    " hit_mean REAL, accept_mean REAL, power_mean REAL, energy_wh REAL, idle_pct REAL,"
    " hours TEXT)"
)
legacy.execute(
    "INSERT INTO day (d, polls, span_s, reqs, prompt, reused, output, tok_mean, tok_max,"
    " prefill_mean, hit_mean, accept_mean, power_mean, energy_wh, idle_pct, hours)"
    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    (int(DAY // 86400), 10, 3600.0, 5, 1000, 200, 500, 40.0, 55.0, 310.0, 90.0, 70.0,
     120.0, 10.0, 20.0, "[]"))
legacy.commit()
legacy.close()

# Re-open the pre-migration file through the real db_init path by pointing DB_PATH at it.
prev_db = server.DB_PATH
server.DB_PATH = old_db
try:
    migrated = server.db_init()
    day_cols = [r[1] for r in migrated.execute("PRAGMA table_info(day)")]
    poll_cols = [r[1] for r in migrated.execute("PRAGMA table_info(poll)")]
    expect("db_init adds prefill_max to a day table written by the old build",
           "prefill_max" in day_cols, day_cols)
    expect("db_init adds prefill_bounded too, so the tag survives into the day ranges",
           "prefill_bounded" in day_cols, day_cols)
    expect("the old day row survives the migration with a NULL peak",
           migrated.execute("SELECT prefill_max FROM day").fetchone()[0] is None, "not null")
    expect("the poll table gains every column added since that build, including prompt_ms",
           {"vram_used", "drafts_offered", "pcie_share", "prompt_ms"} <= set(poll_cols),
           poll_cols)
    # And the exported history stays re-derivable: prompt_ms must travel with it.
    expect("db_export ships prompt_ms so a window's prefill rate is re-derivable offline",
           '"prompt_ms"' in server.db_export(migrated, "json"), "missing from export")
    migrated.close()
finally:
    server.DB_PATH = prev_db

# ---------- db_daily threads the peak through to the day panel ----------
# Polls on BOTH an ended day and today, so db_daily's live "today" entry exists. Without
# a today poll there is no today entry at all, and daily[-1] would be the frozen row —
# which made the second assertion below pass for the wrong reason when first written.
con = fresh()
TODAY = int(NOW // 86400) * 86400
# Today's polls sit at quarter-points of the elapsed day, so they are always strictly
# inside (TODAY, NOW) no matter when the suite runs — a fixed TODAY+n offset would
# fall outside today for the first seconds after midnight UTC.
insert(con, [row(DAY + i * 120, tok_s=40.0, reqs=1 + i, prompt=1000 + i * 100,
                 reused=200 + i * 20, output=50 + i * 5, prefill=p)
             for i, p in enumerate([300.0, 400.0, 900.0, 200.0])]
            + [row(TODAY + f * (NOW - TODAY), tok_s=35.0, reqs=100 + i,
                   prompt=5000 + i * 100, reused=1000 + i * 20, output=200 + i * 5,
                   prefill=q)
               for i, (f, q) in enumerate(zip((0.25, 0.5, 0.75), (500.0, 700.0, 800.0)))])
server.db_finalize_days(con)
daily = server.db_daily(con)
frozen = next(d for d in daily if d["d"] == int(DAY // 86400))
today = next(d for d in daily if d["d"] == int(TODAY // 86400))
expect("db_daily publishes prefill_max for a frozen day",
       frozen["prefill_max"] == 900.0, (frozen["prefill_mean"], frozen["prefill_max"]))
expect("a post-fix day carries no pre-bound note (the marker is structural, not a threshold)",
       "prefill_note" not in frozen, frozen.get("prefill_note"))
expect("today's live rollup carries a peak too (it was dropped before a33-19)",
       today.get("prefill_max") == 800.0, (today.get("prefill_mean"), today.get("prefill_max")))

# And the day-range chart must read that peak from the live aggregate, not None.
ts = server.db_timeseries(con, "7d")
today_bucket = next(b for b in ts["buckets"] if b["t"] // 86400 == TODAY // 86400)
expect("the 7d bucket for today carries the live peak rather than a hard-coded None",
       today_bucket["prefill_max"] == 800.0, today_bucket["prefill_max"])

con.close()
print("ALL PASSED (simulated)" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
