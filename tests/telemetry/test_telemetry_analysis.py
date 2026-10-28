"""telemetry analysis tests (llm-monitor M81-T3, audit-33 a33-08/09/10/11/17) — SIMULATED.

A temp sqlite file created by the real db_init() and synthetic poll rows: no real engine,
no real telemetry.sqlite3, nothing leaves the runner. One PASS line per case.

Run: py -3.12 tests/telemetry/run-tests.py   (or python3 on Linux)
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# Must be set before server is imported: DB_PATH reads it at import time (M81-T8 step 1).
_tmp = tempfile.mkdtemp(prefix="m81-telemetry-")
os.environ["LLM_MONITOR_DB"] = os.path.join(_tmp, "poll.sqlite3")

sys.path.insert(0, os.path.join(HERE, "..", "..", "llm-monitor"))
import server  # noqa: E402

fails = []


def expect(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -- {str(detail)[:300]}"))
    if not ok:
        fails.append(name)


# The real insert order, asserted against PRAGMA table_info below so a schema change
# cannot leave this suite quietly testing a shape the server no longer writes.
INSERT_COLS = ["t", "cpu", "ram", "tok_s", "prefill", "ctx_used", "ctx_pct", "hit_pct",
               "accept_pct", "reqs", "prompt_tokens", "reused", "output_tokens", "power_w",
               "power_src", "gpu_util", "gpu_power", "busy", "vram_used", "vram_total",
               "drafts_offered", "drafts_accepted", "pcie_share", "prompt_ms"]


def row(t, *, tok_s=None, prefill=None, hit_pct=None, accept_pct=None, reqs=0,
        prompt=0, reused=0, output=0, power_w=100.0, busy=0, offered=0, accepted=0,
        prompt_ms=None):
    """One poll row in the real column order."""
    return (t, 10.0, 1000.0, tok_s, prefill, 100.0, 1.0, hit_pct, accept_pct, reqs,
            prompt, reused, output, power_w, "modelled", None, None, busy, 100.0, 24576.0,
            offered, accepted, None, prompt_ms)


def fresh():
    con = server.db_init()
    con.execute("DELETE FROM poll")
    return con


def insert(con, rows):
    ph = ",".join("?" * len(INSERT_COLS))
    con.executemany(f"INSERT INTO poll ({', '.join(INSERT_COLS)}) VALUES ({ph})", rows)
    con.commit()


# The schema the tests assume must be the schema the server creates, or a green suite
# would be testing a shape that no longer exists.
con0 = server.db_init()
live_cols = [r[1] for r in con0.execute("PRAGMA table_info(poll)")]
expect("the poll schema matches what these tests insert (prompt_ms is additive, not a rename)",
       live_cols == INSERT_COLS, live_cols)
expect("db_record's INSERT names every column it binds (arity guard)",
       len(INSERT_COLS) == 24, len(INSERT_COLS))

# The real arity proof: write a poll through db_record itself and read the row back.
# If the column list, the placeholder count or the value tuple ever drift, this is the
# check that catches it (py_compile cannot — lesson from the M78 poll-schema migration).
con = fresh()
server.db_record(con, {
    "totals": {"requests": 7, "prompt_tokens": 1200, "reused": 900, "output_tokens": 300,
               "drafts_offered": 40, "drafts_accepted": 30, "prompt_ms": 8000.0},
    "context": {"used": 1000, "pct": 12.5},
    "cache": {"hit_pct": 75.0},
    "spec": {"accept_pct": 75.0},
    "hardware": {"cpu_pct": 11.0, "ram_used": 2048.0},
    "power": {"total_w": 123.4, "source": "modelled"},
    "live": {"state": "generating"},
    "throughput": {"now": 42.0, "prefill": 310.0},
    "gpu": {"util_pct": 55.0, "power_w": 90.0, "mem_used": 1000.0, "mem_total": 24576.0},
    "requests": [{"pcie_share": 1.5}],
})
back = con.execute("SELECT tok_s, prefill, reqs, prompt_ms, drafts_accepted FROM poll").fetchone()
expect("db_record writes the new prompt_ms column and keeps every other value aligned",
       back == (42.0, 310.0, 7, 8000.0, 30), back)

# ---------- a33-08: the window's own ratio, not a mean of cumulative ratios ----------
# Session-cumulative hit_pct sits at 95% while this window only reused half of what it read.
con = fresh()
NOW = server.datetime.now(server.timezone.utc).timestamp()
rows = []
for i in range(12):
    t = NOW - 600 + i * 50
    rows.append(row(t, hit_pct=95.0, accept_pct=80.0, reqs=10 + i,
                    prompt=1000 + i * 100, reused=950 + i * 50, output=50,
                    tok_s=40.0, prefill=300.0, busy=1,
                    offered=200 + i * 10, accepted=160 + i * 8, prompt_ms=5000 + i * 500))
insert(con, rows)
a = server.db_analysis(con)
rec = a["recent"]
# deltas over the window: prompt 1100, reused 550 -> 50.0 %; offered 110, accepted 88 -> 80.0 %
expect("hit_pct_window is the window's own ratio (50%), not the mean of cumulative ratios (95%)",
       abs(rec["hit_pct_window"] - 50.0) < 0.01, rec["hit_pct_window"])
expect("the old per-poll mean is still published so no consumer breaks",
       abs(rec["hit_pct_mean"] - 95.0) < 0.01, rec["hit_pct_mean"])
expect("accept_pct_window comes from the draft counters (80%), and differs from a mean of ratios",
       abs(rec["accept_pct_window"] - 80.0) < 0.01, rec["accept_pct_window"])
expect("the window it describes is labelled so a number cannot detach from its meaning",
       rec["window_s"] == int(server.DB_WINDOW_S), rec["window_s"])

# An empty denominator has no rate — which is not the same as 0 %.
con = fresh()
rows = [row(NOW - 300 + i * 50, reqs=1, prompt=0, reused=0, output=0, offered=0, accepted=0,
            hit_pct=None, accept_pct=None) for i in range(6)]
insert(con, rows)
rec = server.db_analysis(con)["recent"]
expect("a window that read no prompt has no hit rate: None, not 0%",
       rec["hit_pct_window"] is None, rec["hit_pct_window"])
expect("a window that offered no drafts has no accept rate: None, not 0%",
       rec["accept_pct_window"] is None, rec["accept_pct_window"])

# ---------- a33-09/a33-11: token-weighted rates ----------
# Four idle polls carrying a stale 60 tok/s and one busy poll at 30 skew an unweighted mean.
con = fresh()
rows = [row(NOW - 250 + i * 50, tok_s=60.0, reqs=1, output=0, busy=0) for i in range(4)]
rows.append(row(NOW - 50, tok_s=30.0, reqs=2, output=300, busy=1))
insert(con, rows)
rec = server.db_analysis(con)["recent"]
expect("tok_s_mean stays the unweighted per-poll mean it always was (54.0)",
       abs(rec["tok_s_mean"] - 54.0) < 0.01, rec["tok_s_mean"])
expect("tok_s_weighted is tokens over span, so idle polls stop dragging the rate",
       abs(rec["tok_s_weighted"] - 300 / rec["span_s"]) < 0.01,
       (rec["tok_s_weighted"], rec["span_s"]))
expect("the weighted figure counts only real output (300 tokens in the window)",
       rec["output_tokens"] == 300, rec["output_tokens"])

# prefill_weighted needs the cumulative prompt_ms column; rows predating it have NULL.
# Counters must MOVE (they are cumulative), or the window contains no work at all.
con = fresh()
rows = [row(NOW - 200 + i * 50, reqs=1 + i, prompt=1000 + i * 1000, reused=500 + i * 500,
            output=10 + i * 10, busy=1, prompt_ms=1000 + i * 500) for i in range(5)]
insert(con, rows)
rec = server.db_analysis(con)["recent"]
# delta read = (5000-1000) - (2500-500) = 2000 tokens over delta prompt_ms 2000 ms -> 1000 tok/s
expect("prefill_weighted divides tokens actually read by the prompt_ms that read them",
       abs(rec["prefill_weighted"] - 1000.0) < 0.01, rec["prefill_weighted"])
con = fresh()
insert(con, [row(NOW - 200 + i * 50, reqs=1, prompt=1000, reused=500, output=10, busy=1)
             for i in range(5)])
rec = server.db_analysis(con)["recent"]
expect("prefill_weighted stays None when the rows predate the prompt_ms column",
       rec["prefill_weighted"] is None, rec["prefill_weighted"])

# M81-review S4: during the prompt_ms rollout a window mixes NULL and non-NULL rows.
# cumulative_delta skips NULLs, so an all-rows numerator over a non-NULL-only denominator
# charged tokens to time that never read them. The two rows without prompt_ms read 2000
# tokens that the bounded rows never account for.
con = fresh()
insert(con, [row(NOW - 200, reqs=1, prompt=1000, reused=0, output=10, busy=1),
             row(NOW - 150, reqs=2, prompt=2000, reused=0, output=20, busy=1),
             row(NOW - 100, reqs=3, prompt=3000, reused=0, output=30, busy=1, prompt_ms=1000),
             row(NOW - 50, reqs=4, prompt=4000, reused=0, output=40, busy=1, prompt_ms=2000)])
rec = server.db_analysis(con)["recent"]
# honest: the two rows that carry prompt_ms read 1000 tokens in 1000 ms -> 1000 tok/s.
# the old split-row-set maths reported 3000 tok/s from the same window.
expect("prefill_weighted sums both sides over the prompt_ms span (1000, not 3000)",
       abs(rec["prefill_weighted"] - 1000.0) < 0.01, rec["prefill_weighted"])

# M81-review-015 D1: the opposite failure. Restricting BOTH sides to the rows that carry
# prompt_ms also breaks cumulative_delta, because that helper splits segments at a decrease
# and the NULL-ms middle row is the only evidence of the counter reset here. Dropping it
# makes the numerator read 0, i.e. a fake zero on a window that really moved 1000 tokens.
con = fresh()
insert(con, [row(NOW - 200, reqs=1, prompt=5000, reused=0, output=0, busy=1, prompt_ms=9000),
             row(NOW - 150, reqs=2, prompt=200, reused=0, output=0, busy=1),
             row(NOW - 100, reqs=3, prompt=1200, reused=0, output=0, busy=1, prompt_ms=10000)])
rec = server.db_analysis(con)["recent"]
# The reset survives (prompt moved 1000 across the two segments) and the denominator is the
# prompt_ms span (1000 ms), so the honest rate is 1000 tok/s. Row-filtering both sides gives 0.0.
expect("a counter reset seen only in a NULL-prompt_ms row still counts (1000, not a fake 0)",
       abs(rec["prefill_weighted"] - 1000.0) < 0.01, rec["prefill_weighted"])

# ---------- a33-10: impossible prefill readings are bounded and say so ----------
con = fresh()
rows = [row(NOW - 200 + i * 50, reqs=1 + i, prompt=1000 + i * 100, reused=0, output=100 + i * 50,
            busy=1, tok_s=40.0, prefill=p)
        for i, p in enumerate([300.0, 400.0, 1_905_830.0, 200.0])]
insert(con, rows)
rec = server.db_analysis(con)["recent"]
expect("a 1.9M tok/s prefill sample is excluded from the mean",
       abs(rec["prefill_mean"] - 300.0) < 0.01, rec["prefill_mean"])
expect("no published prefill peak can exceed the physical ceiling",
       rec["prefill_max"] <= server.PREFILL_CEILING_TOK_S, rec["prefill_max"])
expect("the bound announces itself so a filtered mean is never passed off as raw",
       rec["prefill_bounded"] is True, rec["prefill_bounded"])
con = fresh()
insert(con, [row(NOW - 200 + i * 50, reqs=1 + i, prompt=1000 + i * 100, reused=0,
                 output=100 + i * 50, busy=1, prefill=p)
             for i, p in enumerate([9_000.0, 50_000.0])])
rec = server.db_analysis(con)["recent"]
expect("a window whose every prefill sample is impossible reports nothing rather than a fake",
       rec["prefill_mean"] is None and rec["prefill_max"] is None and rec["prefill_bounded"] is True,
       (rec["prefill_mean"], rec["prefill_max"], rec["prefill_bounded"]))
m, mx, b = server.bounded_prefill([100.0, 200.0])
expect("a clean sample set raises no bound flag", b is False and mx == 200.0, (m, mx, b))

# ---------- M75 ghost guard must survive (regression guard) ----------
con = fresh()
insert(con, [row(NOW - 200 + i * 50, tok_s=48.9, prefill=173582.0, reqs=0, prompt=0,
                 reused=0, output=0, busy=0) for i in range(6)])
rec = server.db_analysis(con)["recent"]
expect("a window with 0 requests and 0 tokens still nulls the throughput means (M75 guard)",
       rec["tok_s_mean"] is None and rec["prefill_mean"] is None,
       (rec["tok_s_mean"], rec["prefill_mean"]))

# ---------- a33-17: duplicate timestamps and the span floor ----------
con = fresh()
# every row at the same instant: span 0, so no rate is computable
insert(con, [row(NOW - 100, tok_s=40.0, reqs=5, prompt=100, reused=10, output=20, busy=1)
             for _ in range(6)])
rec = server.db_analysis(con)["recent"]
expect("a zero-length span yields no requests-per-minute instead of dividing by 1e-9",
       rec["req_per_min"] is None, rec["req_per_min"])
expect("a zero-length span yields no weighted rate either",
       rec["tok_s_weighted"] is None, rec["tok_s_weighted"])
expect("the span is reported honestly as 0 rather than a 1e-9 sentinel",
       rec["span_s"] == 0.0, rec["span_s"])
con = fresh()
insert(con, [row(NOW - 20 + i * 3, tok_s=40.0, reqs=1 + i, prompt=10 + i, reused=0,
                 output=5 + i, busy=1) for i in range(4)])
rec = server.db_analysis(con)["recent"]
expect("a span at or above one sampling period does support a rate",
       rec["req_per_min"] is not None and rec["req_per_min"] > 0, rec["req_per_min"])

# ---------- counter resets still sum correctly (must not regress) ----------
con = fresh()
rows = [row(NOW - 300, reqs=10, prompt=1000, reused=800, output=100, busy=1),
        row(NOW - 250, reqs=11, prompt=1100, reused=900, output=110, busy=1),
        # engine restarts: every counter drops
        row(NOW - 200, reqs=1, prompt=500, reused=400, output=50, busy=1),
        row(NOW - 150, reqs=3, prompt=900, reused=700, output=90, busy=1)]
insert(con, rows)
rec = server.db_analysis(con)["recent"]
expect("a mid-window counter reset sums the segments (prompt delta 100 + 400)",
       rec["prompt_tokens"] == 500, rec["prompt_tokens"])
# reused segments: (900-800) + (700-400) = 400 over the same 500 read.
expect("the window hit ratio survives a reset (400 reused / 500 read = 80%)",
       abs(rec["hit_pct_window"] - 80.0) < 0.01, rec["hit_pct_window"])

# ---------- db_hour_aggregates: the same maths, on an explicit span ----------
# This path feeds periods.hour (the HUD trend strip and the History table). Before
# M81-T3 it averaged cumulative ratios per poll and published prefill_weighted as a
# permanent None stub, so it needed its own assertions rather than inheriting
# db_analysis's.
HOUR_END = NOW - NOW % 3600
HOUR_START = HOUR_END - 3600
con = fresh()
hrows = []
for i in range(12):
    t = HOUR_START + 60 + i * 240
    hrows.append(row(t, hit_pct=95.0, accept_pct=80.0, reqs=10 + i,
                     prompt=1000 + i * 100, reused=950 + i * 50, output=50 + i * 10,
                     tok_s=40.0, prefill=300.0, busy=1,
                     offered=200 + i * 10, accepted=160 + i * 8, prompt_ms=5000 + i * 500))
insert(con, hrows)
h = server.db_hour_aggregates(con, HOUR_START, HOUR_END)
# deltas: prompt 1100, reused 550 -> 50 %; offered 110, accepted 88 -> 80 %
expect("the hour span reports its own hit ratio (50%), not a mean of cumulative ratios (95%)",
       abs(h["hit_pct_window"] - 50.0) < 0.01, h["hit_pct_window"])
expect("the hour span reports its own accept ratio from the draft counters (80%)",
       abs(h["accept_pct_window"] - 80.0) < 0.01, h["accept_pct_window"])
# delta read = 1100-550 = 550 tokens over delta prompt_ms 5500 ms -> 100 tok/s
expect("prefill_weighted is computed in the hour path too (it used to be a None stub)",
       h["prefill_weighted"] is not None and abs(h["prefill_weighted"] - 100.0) < 0.01,
       h["prefill_weighted"])
expect("the hour span's weighted decode rate is tokens over span, not a mean of polls",
       abs(h["tok_s_weighted"] - h["output_tokens"] / h["span_s"]) < 0.01,
       (h["tok_s_weighted"], h["output_tokens"], h["span_s"]))
expect("the hour span keeps the old per-poll means so no consumer changes meaning",
       abs(h["hit_pct_mean"] - 95.0) < 0.01 and abs(h["tok_s_mean"] - 40.0) < 0.01,
       (h["hit_pct_mean"], h["tok_s_mean"]))
# A span holding one row still gets its baseline from before lo, and the movement
# across the boundary is attributed to this span (the day path had the same gap).
con = fresh()
insert(con, [row(HOUR_START - 10, reqs=4, prompt=400, reused=200, output=40, busy=1)]
            + [row(HOUR_START + 300, reqs=9, prompt=900, reused=450, output=90, busy=1)])
h = server.db_hour_aggregates(con, HOUR_START, HOUR_END)
expect("a single-row hour still gets a baseline from before the span (requests delta 5)",
       h["requests"] == 5, h["requests"])
expect("that baseline's span supports a rate (310 s, above the floor)",
       h["span_s"] == 310.0 and h["req_per_min"] is not None, (h["span_s"], h["req_per_min"]))
# M81-review S5: db_analysis rounds this figure and db_hour_aggregates did not, so the
# same quantity reached the payload at two different precisions. Pinned to the invariant
# (the published value equals its own 2-dp rounding) rather than a literal, so a fixture
# offset shifting cannot turn a passing run into a mystery failure; 50/310 is not exact in
# two decimals, which is what keeps this able to fail on an unrounded value.
expect("the hour path rounds tok_s_weighted like db_analysis does",
       h["tok_s_weighted"] == round(h["output_tokens"] / h["span_s"], 2),
       (h["tok_s_weighted"], h["output_tokens"], h["span_s"]))
# M81-review-015 D3: the hour path carried ANY earlier row as its baseline, so a retained
# row from before an outage gave a one-hour window a span of ~173,400 s and divided this
# hour's movement by it. An hour's rate must not be computed across a gap the hour did not
# observe; the baseline has to be recent, the same rule day_aggregates now enforces.
con = fresh()
insert(con, [row(HOUR_START - 2 * 86400, reqs=3, prompt=1000, reused=0, output=600, busy=1),
             row(HOUR_START + 600, reqs=5, prompt=1600, reused=0, output=1000, busy=1),
             row(HOUR_START + 3000, reqs=8, prompt=2400, reused=0, output=1400, busy=1)])
h = server.db_hour_aggregates(con, HOUR_START, HOUR_END)
# Without the bound the retained row set span_s to 173,400 s (measured) and every rate was
# divided by the outage. With it the hour spans its own two rows.
expect("an hour does not take a two-day-old baseline as its context (span 2400 s, not 173400)",
       h["span_s"] == 2400.0, (h["span_s"], h["polls"]))
expect("the same hour reports its own movement (3 requests) rather than the gap's",
       h["requests"] == 3, h["requests"])
expect("and its weighted rate is over the span it actually observed",
       abs(h["tok_s_weighted"] - round(400 / 2400, 2)) < 0.001,
       (h["tok_s_weighted"], h["output_tokens"], h["span_s"]))
# With no baseline at all, one row spans zero seconds: no rate is computable, and the
# old 1e-9 sentinel used to divide by it anyway.
con = fresh()
insert(con, [row(HOUR_START + 300, reqs=9, prompt=900, reused=450, output=90, busy=1)])
h = server.db_hour_aggregates(con, HOUR_START, HOUR_END)
expect("a lone row with no baseline reports a zero span, not a 1e-9 sentinel",
       h["span_s"] == 0.0, h["span_s"])
expect("a zero span yields no req/min and no weighted rate in the hour path",
       h["req_per_min"] is None and h["tok_s_weighted"] is None,
       (h["req_per_min"], h["tok_s_weighted"]))

con.close()
print("ALL PASSED (simulated)" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
