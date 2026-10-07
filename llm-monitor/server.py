#!/usr/bin/env python3
"""Local LLM monitor — serves the dashboard + a live /api/stats endpoint.

Run:  python server.py [port]     (default port 8090)
Then open http://localhost:8090

This is NOT the homelab dashboard. It monitors the local LLM engine that owns
port 8080 on this machine — either Strata Coder or Vulkan llama.cpp (Qwen3.8-27B)
— by reading the engine's own HTTP endpoints and the Hermes workspace state files.

Sources it reads (all on this machine):
  * engine HTTP (default http://127.0.0.1:8080): /health /metrics /slots /v1/models /props
  * workspace state files: engine-active.txt, llama-active-profile.txt, llama-last-profile.txt, hermes-owner.txt
  * log files (tailed): watchdog.log, autostart.log, server.log.err

The /api/stats response shape is the contract the front end consumes. Every field
is best-effort: if the engine is down or a file is missing, that section degrades
to nulls/empty and the page still renders. Override ENGINE_URL / WORKSPACE /
LOG_FILES at the top to point at a different machine.
"""

import json
import os
import re
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PORT_DEFAULT = 8090

# ---------- Configuration ----------
ENGINE_URL = "http://127.0.0.1:8080"
WORKSPACE = r"C:\Project\hermes"
LOG_FILES = {
    "watchdog": os.path.join(WORKSPACE, "tools", "llama-cpp", "watchdog.log"),
    "autostart": os.path.join(WORKSPACE, "tools", "llama-cpp", "autostart.log"),
    "server": os.path.join(WORKSPACE, "tools", "llama-cpp", "server.log.err"),
}
STATE_FILES = {
    "engine_active": os.path.join(WORKSPACE, "engine-active.txt"),
    "llama_active_profile": os.path.join(WORKSPACE, "llama-active-profile.txt"),
    "llama_last_profile": os.path.join(WORKSPACE, "llama-last-profile.txt"),
    "owner": os.path.join(WORKSPACE, "hermes-owner.txt"),
    "pid": os.path.join(WORKSPACE, "llama-server.pid"),
}
LLAMA_PROFILES = [
    "gemma", "qwen38-iq3", "qwen38-iq3-128k", "qwen38-iq3-long",
    "qwen38-iq4", "qwen38-xtx", "qwen38-xtx-long", "qwen38-xtx-q4", "qwen38-xtx-q5",
]
HTTP_TIMEOUT = 3.0

# ---------- Telemetry + power model ----------
# The SQLite history is deliberately tiny: one numeric row per poll, no JSON blobs,
# bounded to DB_MAX_ROWS (~1-2 MB), pruned in one cheap DELETE every DB_PRUNE_EVERY
# writes. It is a side channel — every call into it is wrapped so a database problem
# can never take the dashboard down.
# DB_PATH is resolved to an absolute path so it points at the file beside server.py
# no matter which working directory the process was started from. A relative path
# silently resolves against the process cwd, which is how a server started elsewhere
# ends up with sqlite unable to open the file (telemetry disabled, empty trends).
DB_PATH = str(Path(__file__).resolve().with_name("telemetry.sqlite3"))
DB_MAX_ROWS = 20000
DB_PRUNE_EVERY = 500
DB_WINDOW_S = 3600  # the two analysis windows (recent vs previous)

# Rated envelopes for THIS machine (see hermes CONFIGURATION.md). Used only when the
# engine does not expose measured GPU power; the payload always says which source it
# used, so the front end never presents a modelled number as a measurement.
POWER_MODEL = {
    "gpu_name": "AMD Radeon RX 7900 XTX",
    "gpu_idle_w": 20.0,
    "gpu_max_w": 350.0,
    "cpu_name": "AMD Ryzen 5 5600X",
    "cpu_idle_w": 6.0,
    "cpu_max_w": 150.0,
}


def _get_json(path):
    """GET an engine endpoint; return parsed JSON or None.

    Results are cached for the duration of one poll (_poll_reset clears the cache in
    build_stats), so the ~10 sections that all want /metrics pay for one request. This
    keeps the monitor from hammering the engine it is measuring.
    """
    if path in _CACHE:
        return _CACHE[path]
    try:
        with urllib.request.urlopen(f"{ENGINE_URL}{path}", timeout=HTTP_TIMEOUT) as res:
            value = json.loads(res.read().decode("utf-8", "replace"))
    except Exception:
        value = None
    _CACHE[path] = value
    return value


_CACHE = {}


def _poll_reset():
    _CACHE.clear()


def _read_text(key):
    """Read a workspace state file; return trimmed text or None."""
    path = STATE_FILES.get(key)
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read().strip()
    except Exception:
        return None


def _tail(path, n):
    """Return the last n lines of a file as a list, or []."""
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = [ln.rstrip("\n") for ln in fh if ln.strip()]
        return lines[-n:]
    except Exception:
        return []


# ---------- Engine detection ----------
def gather_engine():
    """Which engine owns the port, and its identity."""
    health = _get_json("/health")
    models = _get_json("/v1/models")
    props = _get_json("/props")
    marker = _read_text("engine_active")

    service = None
    if health and isinstance(health, dict):
        service = health.get("service")
    # llama.cpp /health has no 'service'; infer vulkan when the port is alive.
    if service is None and health:
        service = "vulkan"

    model = None
    if health:
        model = health.get("model")
    if not model and models and isinstance(models, dict):
        data = models.get("data") or []
        if data:
            model = data[0].get("id")

    return {
        "active": marker or "unknown",
        "service": service,
        "model": model,
        "model_alias": (props or {}).get("model_alias") if isinstance(props, dict) else None,
        "max_context": (health or {}).get("max_context") if isinstance(health, dict) else None,
        "loaded": (health or {}).get("loaded") if isinstance(health, dict) else None,
        "version": (health or {}).get("version") if isinstance(health, dict) else None,
        "images": (health or {}).get("images") if isinstance(health, dict) else None,
        "api_key": (health or {}).get("api_key") if isinstance(health, dict) else None,
        "model_path": (props or {}).get("model_path") if isinstance(props, dict) else None,
        "build_info": (props or {}).get("build_info") if isinstance(props, dict) else None,
        "port_open": health is not None,
    }


def gather_live():
    """Current inference state from /metrics.live (Strata) or /slots (llama).

    Prefill note: the engine's own `prefill_tok_s_mean` is unreliable — it reports 0.0
    both in `hardware` and across `history.prefill_tok_s_mean`. The engine's built-in
    monitor never reads it either; it derives the rate from the request record. We do
    the same here (see build_stats) and keep this field only as a last resort.
    """
    metrics = _get_json("/metrics")
    if metrics and isinstance(metrics, dict) and metrics.get("live"):
        return metrics["live"]
    # llama.cpp fallback: /slots gives per-slot processing state.
    slots = _get_json("/slots")
    if slots and isinstance(slots, list):
        busy = [s for s in slots if isinstance(s, dict) and s.get("is_processing")]
        return {
            "state": "processing" if busy else "idle",
            "queued": 0,
            "phase": None,
            "prompt_tokens": None,
            "prompt_read": None,
            "prompt_total": None,
            "generated": None,
            "max_tokens": None,
            "elapsed_s": None,
            "tok_s": None,
            "tok_s_mean": None,
            "prefill_tok_s_mean": None,
        }
    return None


def gather_context():
    """Context window usage + slots."""
    metrics = _get_json("/metrics")
    slots = _get_json("/slots")
    props = _get_json("/props")

    max_ctx = None
    if isinstance(props, dict):
        gen = props.get("default_generation_settings") or {}
        max_ctx = gen.get("n_ctx")
    if max_ctx is None and isinstance(metrics, dict):
        max_ctx = (metrics.get("engine") or {}).get("max_context")
    if max_ctx is None and isinstance(slots, list) and slots:
        max_ctx = slots[0].get("n_ctx")

    return {
        "max_context": max_ctx,
        "total_slots": (props or {}).get("total_slots") if isinstance(props, dict) else (len(slots) if isinstance(slots, list) else None),
        "slots": [s for s in slots if isinstance(s, dict)] if isinstance(slots, list) else [],
    }


def gather_cache():
    """KV cache, expert cache, conversation cache, hit rate."""
    metrics = _get_json("/metrics")
    if not metrics or not isinstance(metrics, dict):
        return None
    eng = metrics.get("engine") or {}
    conv = metrics.get("conversation_cache") or {}
    totals = metrics.get("totals") or {}
    hit = None
    if totals.get("prompt_tokens"):
        hit = totals["reused"] / totals["prompt_tokens"]
    return {
        "kv_type": eng.get("kv"),
        "kv_resident": eng.get("kv_resident"),
        "expert_slots": eng.get("expert_slots"),
        "expert_cache_mib": eng.get("expert_cache_mib"),
        "conversation_cache": conv,
        "hit_rate": hit,
        "reused_tokens": totals.get("reused"),
        "prompt_tokens": totals.get("prompt_tokens"),
    }


def gather_spec():
    """Speculative decoding (MTP) accept rate."""
    metrics = _get_json("/metrics")
    if not metrics or not isinstance(metrics, dict):
        return None
    eng = metrics.get("engine") or {}
    totals = metrics.get("totals") or {}
    offered = totals.get("drafts_offered")
    accepted = totals.get("drafts_accepted")
    rate = (accepted / offered) if offered else None
    return {
        "spec": eng.get("spec"),
        "mtp_max": eng.get("mtp_max"),
        "lookup": eng.get("lookup"),
        "drafts_offered": offered,
        "drafts_accepted": accepted,
        "accept_rate": rate,
    }


def gather_hardware():
    """CPU, RAM, VRAM, disk, GPU identity."""
    metrics = _get_json("/metrics")
    if not metrics or not isinstance(metrics, dict):
        return None
    hw = metrics.get("hardware") or {}
    static = metrics.get("hardware_static") or {}
    eng = metrics.get("engine") or {}
    ram_total = hw.get("ram_total")
    ram_used = hw.get("ram_used")
    return {
        "cpu_pct": hw.get("cpu"),
        "ram_used": ram_used,
        "ram_total": ram_total,
        "ram_pct": (ram_used / ram_total * 100) if ram_total else None,
        "vram_free_mib": eng.get("vram_free_mib"),
        "disk_read_mb": hw.get("disk_read_mb"),
        "disk_write_mb": hw.get("disk_write_mb"),
        "tok_s": hw.get("tok_s"),
        "tok_s_mean": hw.get("tok_s_mean"),
        "prefill_tok_s_mean": hw.get("prefill_tok_s_mean"),
        "gpu_util": hw.get("gpu_util"),
        "gpu_mem_used": hw.get("gpu_mem_used"),
        "gpu_mem_total": hw.get("gpu_mem_total"),
        "gpu_temp": hw.get("gpu_temp"),
        "gpu_power": hw.get("gpu_power"),
        "gpu_power_limit": hw.get("gpu_power_limit"),
        "gpu_pcie_rx_mb": hw.get("gpu_pcie_rx_mb"),
        "gpu_pcie_gen": hw.get("gpu_pcie_gen"),
        "gpu_pcie_gen_max": hw.get("gpu_pcie_gen_max"),
        "gpu_pcie_width": hw.get("gpu_pcie_width"),
        "gpu_name": static.get("gpu_name"),
        "gpu_count": static.get("gpu_count"),
        "cpu_name": static.get("cpu_name"),
        "cores": static.get("cores"),
        "threads": static.get("threads"),
    }


def gather_totals():
    """Cumulative totals since engine start."""
    metrics = _get_json("/metrics")
    if not metrics or not isinstance(metrics, dict):
        return None
    return metrics.get("totals")


def gather_config():
    """Engine configuration knobs the engine reports but never explains.

    These are static for a session, so they belong in a compact facts list rather
    than a gauge. Values arrive as strings for the fractional knobs (`pcie_frac`,
    `spec_min_p`), so they are passed through as-is rather than coerced.
    """
    metrics = _get_json("/metrics")
    if not metrics or not isinstance(metrics, dict):
        return None
    eng = metrics.get("engine") or {}
    return {
        "pool_workers": eng.get("pool_workers"),
        "pcie_frac": eng.get("pcie_frac"),
        "spec": eng.get("spec"),
        "spec_min_p": eng.get("spec_min_p"),
        "mtp_max": eng.get("mtp_max"),
        "lookup": eng.get("lookup"),
        "expert_slots": eng.get("expert_slots"),
        "expert_slots_primary": eng.get("expert_slots_primary"),
        "expert_cache_mib": eng.get("expert_cache_mib"),
        "expert_cache_primary_mib": eng.get("expert_cache_primary_mib"),
        "arena_mib": eng.get("arena_mib"),
        "cvec": eng.get("cvec"),
        "vram_elastic": eng.get("vram_elastic"),
        "conversation_cache_slots": eng.get("conversation_cache_slots"),
        "conversation_cache_min_free_mib": eng.get("conversation_cache_min_free_mib"),
        "tail_role_token": eng.get("tail_role_token"),
    }


def gather_switch():
    """Engine-switch state and the llama profile inventory."""
    return {
        "engine_active": _read_text("engine_active"),
        "llama_active_profile": _read_text("llama_active_profile"),
        "llama_last_profile": _read_text("llama_last_profile"),
        "owner": _read_text("owner"),
        "pid": _read_text("pid"),
        "profiles": LLAMA_PROFILES,
    }


def gather_log(limit=14):
    """Merge the tails of the log files into one feed, newest first."""
    entries = []

    # watchdog.log: [HH:MM:SS] msg
    for ln in _tail(LOG_FILES["watchdog"], 6):
        m = re.match(r"\[(\d{2}:\d{2}:\d{2})\]\s+(.*)", ln)
        if m:
            entries.append({"level": _level(m.group(2)), "iso": None, "msg": m.group(2), "source": "watchdog"})

    # autostart.log: [YYYY-MM-DD HH:MM:SS] [owner] msg
    for ln in _tail(LOG_FILES["autostart"], 8):
        m = re.match(r"\[([\d\-]+ [\d:]+)\]\s+\[(\w+)\]\s+(.*)", ln)
        if m:
            entries.append({"level": _level(m.group(3)), "iso": _iso(m.group(1)), "msg": m.group(3), "source": "autostart"})

    # server.log.err: llama.cpp format  0.00.152.347 I srv  llama_server: ...
    for ln in _tail(LOG_FILES["server"], 12):
        m = re.match(r"([\d.]+)\s+([IWED])\s+(.*)", ln)
        if m:
            lvl = {"I": "info", "W": "warn", "E": "bad", "D": "bad"}.get(m.group(2), "info")
            entries.append({"level": lvl, "iso": None, "msg": m.group(3), "source": "server"})

    # Sort: entries with a real timestamp first (newest), then the rest in file order.
    entries.sort(key=lambda e: e["iso"] or "", reverse=True)
    return entries[:limit]


def _level(msg):
    low = msg.lower()
    if any(k in low for k in ("fail", "error", "refused", "degraded", "not found", "fatal")):
        return "bad"
    if any(k in low for k in ("warn", "stale", "timeout", "skip", "block")):
        return "warn"
    return "info"


def _iso(datestr):
    try:
        return datetime.strptime(datestr, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
    except Exception:
        return None


def gather_history():
    """Time-series arrays the engine already keeps.

    The gpu_* series are included even though this engine leaves them null today, so a
    setup that does report them (or a future engine build) passes through unchanged.
    """
    metrics = _get_json("/metrics")
    if not metrics or not isinstance(metrics, dict):
        return None
    hist = metrics.get("history") or {}
    out = {}
    for key in (
        "cpu", "ram_used", "tok_s", "disk_read_mb", "prefill_tok_s_mean",
        "gpu_util", "gpu_mem_used", "gpu_temp", "gpu_power", "gpu_pcie_rx_mb",
    ):
        arr = hist.get(key)
        if isinstance(arr, list) and any(v is not None for v in arr):
            out[key] = arr
    return out or None


def gather_requests(limit=12):
    """Recent request records, newest first."""
    metrics = _get_json("/metrics")
    if not metrics or not isinstance(metrics, dict):
        return []
    reqs = metrics.get("requests") or []
    out = []
    for r in reqs[:limit]:
        if not isinstance(r, dict):
            continue
        out.append({
            "duration_s": r.get("duration_s"),
            "finish": r.get("finish"),
            "prompt_tokens": r.get("prompt_tokens"),
            "prompt_read": r.get("prompt_read"),
            "reused": r.get("reused"),
            "output_tokens": r.get("output_tokens"),
            "prompt_ms": r.get("prompt_ms"),
            "decode_ms": r.get("decode_ms"),
            "decode_tok_s": r.get("decode_tok_s"),
            "hit_rate": r.get("hit_rate"),
            "pcie_share": r.get("pcie_share"),
            "drafts_offered": r.get("drafts_offered"),
            "drafts_accepted": r.get("drafts_accepted"),
            "time": r.get("time"),
            "engine_generated": r.get("engine_generated"),
            "file_mb": r.get("file_mb"),
            "ram_blobs": r.get("ram_blobs"),
            "file_blobs": r.get("file_blobs"),
        })
    return out


def prefill_rate(record):
    """Derive one request's prefill rate (tok/s) the way the engine's own monitor does.

    Only the tokens the engine actually had to read count — the reused prefix was
    already in the KV cache, so dividing prompt_tokens by prompt_ms understates the
    rate by the hit rate. Returns None when the record cannot support a rate.
    """
    if not isinstance(record, dict):
        return None
    prompt = record.get("prompt_tokens")
    ms = record.get("prompt_ms")
    if not prompt or not ms:
        return None
    read = record.get("prompt_read")
    if read is None:
        read = prompt - (record.get("reused") or 0)
    return max(0.0, read) / (ms / 1000)


def bucket_requests(metrics, buckets=24, span_s=1800, extract=None):
    """Bucket the engine's own request records into fixed time intervals.

    The engine keeps no request-count or prefill history, but every request record
    carries its own timestamp, so both series can be derived here. `extract` maps a
    record to the value to average; with none, each bucket just counts records.
    Used only as a fallback while the SQLite history is still too short to draw from.
    """
    reqs = [r for r in ((metrics or {}).get("requests") or []) if isinstance(r, dict) and r.get("time")]
    if not reqs:
        return None
    now = (metrics or {}).get("time") or max(r["time"] for r in reqs)
    width = span_s / buckets
    sums = [0.0] * buckets
    counts = [0] * buckets
    for r in reqs:
        idx = int((now - r["time"]) // width)
        if 0 <= idx < buckets:
            b = buckets - 1 - idx
            counts[b] += 1
            if extract:
                v = extract(r)
                if v is not None:
                    sums[b] += v
    values = [(sums[b] / counts[b] if counts[b] else None) for b in range(buckets)] if extract else [float(c) for c in counts]
    return values


# ---------- Power ----------
def gather_power(metrics, live):
    """Energy the engine is drawing, measured where possible, modelled otherwise.

    The engine schema carries `gpu_power` / `gpu_power_limit` (its own monitor draws a
    Power card from them), but on this AMD HIP build they come back null — the driver
    exposes no userspace power counter, unlike NVIDIA's NVML. So we report the source
    explicitly and never dress a modelled figure up as a measurement.
    """
    hw = (metrics or {}).get("hardware") or {}
    measured = hw.get("gpu_power")
    limit = hw.get("gpu_power_limit")

    if measured is not None:
        gpu_w = float(measured)
        source = "measured"
    else:
        # No counter: scale the rated envelope by how hard the GPU is working.
        util = hw.get("gpu_util")
        if util is not None:
            activity = max(0.0, min(1.0, float(util) / 100))
            source = "modelled"
        else:
            # Infer it from what the engine is doing. Prefill is dense GEMM — the
            # compute-bound, hottest phase. Decode streams weights from VRAM, so it
            # sits well under peak on a memory-bandwidth-bound model. Idle is the card
            # parked. 0.65 for decode is the RDNA3 ballpark for a 27B-class decode.
            state = (live or {}).get("state")
            activity = {"reading": 1.0, "generating": 0.65, "processing": 0.65, "queued": 0.1}.get(state or "", 0.0)
            source = "modelled" if state else "unavailable"
        gpu_w = POWER_MODEL["gpu_idle_w"] + (POWER_MODEL["gpu_max_w"] - POWER_MODEL["gpu_idle_w"]) * activity

    cpu_pct = hw.get("cpu")
    cpu_w = (POWER_MODEL["cpu_idle_w"] + (POWER_MODEL["cpu_max_w"] - POWER_MODEL["cpu_idle_w"]) * max(0.0, min(1.0, cpu_pct / 100))
             if cpu_pct is not None else None)

    total = gpu_w + cpu_w if cpu_w is not None else gpu_w
    peak = POWER_MODEL["gpu_max_w"] + POWER_MODEL["cpu_max_w"]
    return {
        "total_w": round(total, 1) if total is not None else None,
        "gpu_w": round(gpu_w, 1) if gpu_w is not None else None,
        "cpu_w": round(cpu_w, 1) if cpu_w is not None else None,
        "gpu_measured_w": measured,
        "gpu_limit_w": limit,
        "peak_w": peak,
        "pct_of_peak": round(total / peak * 100, 1) if total and peak else None,
        "source": source,
        "model": POWER_MODEL,
    }


# ---------- Telemetry (sqlite) ----------
# One numeric row per poll. Everything the analysis needs is a delta or an average over
# these rows, so no JSON is stored and the file stays a couple of MB regardless of how
# long the engine runs.
def db_init():
    """Open (creating if needed) the telemetry database."""
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(
            "CREATE TABLE poll ("
            "t REAL, cpu REAL, ram REAL, tok_s REAL, prefill REAL,"
            "ctx_used REAL, ctx_pct REAL, hit_pct REAL, accept_pct REAL,"
            "reqs INTEGER, prompt_tokens INTEGER, reused INTEGER, output_tokens INTEGER,"
            "power_w REAL, power_src TEXT, gpu_util REAL, gpu_power REAL, busy INTEGER)"
        )
    except sqlite3.OperationalError:
        pass  # the table survived from a previous run
    return con


def db_record(con, stats):
    """Append one row for this poll; return the row's timestamp."""
    now = datetime.now(timezone.utc).timestamp()
    totals = stats.get("totals") or {}
    ctx = stats.get("context") or {}
    cache = stats.get("cache") or {}
    spec = stats.get("spec") or {}
    hw = stats.get("hardware") or {}
    power = stats.get("power") or {}
    live = stats.get("live") or {}
    thr = stats.get("throughput") or {}
    con.execute(
        "INSERT INTO poll (t, cpu, ram, tok_s, prefill, ctx_used, ctx_pct, hit_pct, accept_pct,"
        " reqs, prompt_tokens, reused, output_tokens, power_w, power_src, gpu_util, gpu_power, busy)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            now,
            hw.get("cpu_pct"), hw.get("ram_used"),
            thr.get("now"), thr.get("prefill"),
            ctx.get("used"), ctx.get("pct"),
            cache.get("hit_pct"), spec.get("accept_pct"),
            totals.get("requests"), totals.get("prompt_tokens"), totals.get("reused"), totals.get("output_tokens"),
            power.get("total_w"), power.get("source"),
            hw.get("gpu_util"), hw.get("gpu_power"),
            1 if live.get("state") not in ("idle", None) else 0,
        ),
    )
    con.commit()
    return now


def db_prune(con):
    """Drop the oldest rows past the cap in one DELETE."""
    cut = con.execute("SELECT t FROM poll LIMIT 1 OFFSET ?", (DB_MAX_ROWS,)).fetchone()
    if cut:
        con.execute("DELETE FROM poll WHERE t <= ?", (cut[0],))
        con.commit()


def db_analysis(con, window_s=DB_WINDOW_S):
    """Compare the recent window against the one before it.

    One scan over a bounded table, split in Python, so the cost does not grow with uptime.
    Cumulative totals are stored per row, so a window's real work is the difference between
    its first and last row.
    """
    now = datetime.now(timezone.utc).timestamp()
    rows = con.execute(
        "SELECT t, cpu, tok_s, prefill, hit_pct, accept_pct, reqs, prompt_tokens,"
        " reused, output_tokens, power_w, busy FROM poll WHERE t >= ?",
        (now - 2 * window_s,)).fetchall()
    out = {}
    for label, lo, hi in (("recent", now - window_s, now), ("previous", now - 2 * window_s, now - window_s)):
        window = [r for r in rows if lo <= r[0] < hi]
        if len(window) < 2:
            out[label] = None
            continue
        first, last = window[0], window[-1]
        span = max(1e-9, last[0] - first[0])

        def avg(i):
            vals = [r[i] for r in window if r[i] is not None]
            return sum(vals) / len(vals) if vals else None

        def delta(i):
            a, b = first[i], last[i]
            return (b - a) if (a is not None and b is not None) else None

        power_vals = [r[10] for r in window if r[10] is not None]
        out[label] = {
            "polls": len(window),
            "span_s": round(span, 1),
            "requests": delta(6),
            "prompt_tokens": delta(7),
            "reused": delta(8),
            "output_tokens": delta(9),
            "req_per_min": round((delta(6) or 0) / span * 60, 2),
            "tok_s_mean": avg(2),
            "tok_s_max": max((r[2] for r in window if r[2] is not None), default=None),
            "prefill_mean": avg(3),
            "hit_pct_mean": avg(4),
            "accept_pct_mean": avg(5),
            "power_w_mean": avg(10),
            "energy_wh": round(sum(power_vals) * span / 3600 / len(power_vals), 3) if power_vals else None,
            "idle_pct": round(100 * sum(1 for r in window if not r[11]) / len(window), 1),
        }
    return out


def bucket_db_requests(rows, buckets=24, span_s=1800):
    """Per-interval request counts from the DB's cumulative counter.

    Richer than bucketing the engine's own records, which it only keeps 12 of: the
    counter survives, so activity older than that window still shows on the chart.
    """
    if not rows:
        return None
    now = rows[-1][0]
    width = span_s / buckets
    firsts, lasts = {}, {}
    for t, reqs in ((r[0], r[1]) for r in rows):
        if reqs is None:
            continue
        idx = int((now - t) // width)
        if 0 <= idx < buckets:
            b = buckets - 1 - idx
            firsts.setdefault(b, reqs)
            lasts[b] = reqs
    if not lasts:
        return None
    # Seed with the oldest bucket's own baseline so the engine's cumulative counter
    # (which starts at whatever it was when we began recording) is not dumped into it.
    oldest = min(firsts)
    carry = firsts[oldest]
    out = []
    for b in range(buckets):
        if b in lasts:
            out.append(max(0, lasts[b] - carry))
            carry = lasts[b]
        else:
            out.append(0)
    return out


def db_rows(con, limit=240):
    """The tail of the history, oldest first, for the sparklines to draw from."""
    rows = con.execute(
        "SELECT t, tok_s, prefill, reqs, power_w, cpu, hit_pct, busy FROM poll"
        " ORDER BY t DESC LIMIT ?", (limit,)).fetchall()
    rows.reverse()
    return rows


# The connection is opened once and reused for every poll; the write counter decides
# when to prune. Both stay None/0 if sqlite cannot be used, and every use is guarded.
_DB = None
_DB_WRITES = 0


def telemetry(stats):
    """Record this poll and return (history rows, window analysis, status).

    Returns (None, None, status) if the database is unavailable, in which case the caller
    falls back to deriving series from the engine's own request records. The status is
    part of the payload so a disabled DB is visible on the dashboard, not just in the
    server's console — an empty trend is otherwise indistinguishable from a quiet engine.
    """
    global _DB, _DB_WRITES
    try:
        if _DB is None:
            _DB = db_init()
        _DB_WRITES += 1
        db_record(_DB, stats)
        if _DB_WRITES % DB_PRUNE_EVERY == 0:
            db_prune(_DB)
        rows = db_rows(_DB)
        return rows, db_analysis(_DB), {"ok": True, "rows": len(rows)}
    except Exception as err:
        print(f"[telemetry] disabled: {err}")
        return None, None, {"ok": False, "error": f"{type(err).__name__}: {err}"}


def build_stats():
    """Assemble the full monitor payload. Each section degrades independently."""
    _poll_reset()
    engine = gather_engine()
    live = gather_live()
    metrics = _get_json("/metrics")  # cached: every section below pays for one request
    eng = (metrics or {}).get("engine") or {}
    totals = (metrics or {}).get("totals") or {}
    conv = (metrics or {}).get("conversation_cache") or {}
    hw = (metrics or {}).get("hardware") or {}
    static = (metrics or {}).get("hardware_static") or {}

    reqs = (metrics or {}).get("requests") or []
    last_req = reqs[0] if reqs else None

    # Engine state chip. Strata reports the phase explicitly (reading / generating);
    # llama.cpp only says whether a slot is busy, which gather_live already collapsed
    # to processing/idle. `queued` is what makes the state worth its own chip.
    state = (live or {}).get("state")
    queued = (live or {}).get("queued") or 0
    busy = state not in ("idle", None) or queued > 0
    status = {
        "state": state,
        "phase": (live or {}).get("phase"),
        "queued": queued,
        "busy": busy,
        "activity": "active" if busy else "idle",
    }

    # Context usage: live footprint when processing, else the last request's
    # footprint (prompt + output) so the gauge reads the real window, not 0.
    ctx_used = None
    ctx_source = None
    if isinstance(live, dict) and busy:
        ctx_used = (live.get("prompt_tokens") or 0) + (live.get("generated") or 0)
        ctx_source = "live"
    elif last_req:
        ctx_used = (last_req.get("prompt_tokens") or 0) + (last_req.get("output_tokens") or 0)
        ctx_source = "last"

    max_ctx = engine.get("max_context") or eng.get("max_context")
    ctx_pct = (ctx_used / max_ctx * 100) if (ctx_used and max_ctx) else None

    # Throughput: live tok_s when generating; when idle, the last request's decode
    # rate and the session mean from totals, so the panel reads truth, not 0.
    tok_now = hw.get("tok_s")
    tok_mean = hw.get("tok_s_mean")
    tok_source = "live"
    if not tok_now:
        tok_now = (last_req or {}).get("decode_tok_s")
        tok_source = "last" if tok_now else None
    if not tok_mean and totals.get("output_tokens") and totals.get("decode_ms"):
        tok_mean = totals["output_tokens"] / (totals["decode_ms"] / 1000)

    # Prefill: the engine's own prefill_tok_s_mean is broken (it reports 0.0 in both
    # `hardware` and `history.prefill_tok_s_mean`), so derive it the way the engine's
    # built-in monitor does — only the tokens it actually had to read count.
    prefill_now = None
    prefill_source = None
    if isinstance(live, dict) and live.get("state") == "reading" and live.get("elapsed_s"):
        read = live.get("prompt_read")
        if read is None:
            read = (live.get("prompt_tokens") or 0) - (live.get("reused") or 0)
        prefill_now = max(0.0, read) / live["elapsed_s"]
        prefill_source = "live"
    if not prefill_now:
        prefill_now = prefill_rate(last_req)
        prefill_source = "last" if prefill_now else None
    if not prefill_now:
        prefill_now = hw.get("prefill_tok_s_mean")
        prefill_source = "engine" if prefill_now else None

    hit = (totals["reused"] / totals["prompt_tokens"]) if totals.get("prompt_tokens") else None
    offered = totals.get("drafts_offered")
    accepted = totals.get("drafts_accepted")
    accept_rate = (accepted / offered) if offered else None
    hit_pct = hit * 100 if hit is not None else None
    accept_pct = accept_rate * 100 if accept_rate is not None else None

    power = gather_power(metrics, live)

    # GPU parity with the engine's own monitor (its cards are speed/gpu/vram/temp/
    # power/pcie/cpu/disk). On this AMD HIP build the counters come back null, so the
    # section carries nulls and the panel says so rather than showing a fake zero.
    gpu_hist = gather_history() or {}
    gpu = {
        "util_pct": hw.get("gpu_util"),
        "mem_used": hw.get("gpu_mem_used"),
        "mem_total": hw.get("gpu_mem_total"),
        "mem_pct": (hw["gpu_mem_used"] / hw["gpu_mem_total"] * 100)
                   if (hw.get("gpu_mem_used") and hw.get("gpu_mem_total")) else None,
        "temp_c": hw.get("gpu_temp"),
        "power_w": hw.get("gpu_power"),
        "power_limit_w": hw.get("gpu_power_limit"),
        "pcie_rx_mb": hw.get("gpu_pcie_rx_mb"),
        "pcie_gen": hw.get("gpu_pcie_gen"),
        "pcie_gen_max": hw.get("gpu_pcie_gen_max"),
        "pcie_width": hw.get("gpu_pcie_width"),
        "name": static.get("gpu_name"),
        "count": static.get("gpu_count"),
        # True when the engine reports any gpu_* series, so the panel can offer a
        # sparkline only where there is real history to draw.
        "history_available": any(k in gpu_hist for k in ("gpu_util", "gpu_temp", "gpu_power", "gpu_mem_used")),
    }

    stats = {
        "engine": engine,
        "status": status,
        "live": live,
        "context": {
            "used": ctx_used,
            "max": max_ctx,
            "pct": ctx_pct,
            "slots": engine.get("total_slots"),
            "kv_resident": eng.get("kv_resident"),
            "source": ctx_source,
        },
        "cache": {
            "kv_type": eng.get("kv"),
            "kv_resident": eng.get("kv_resident"),
            "expert_slots": eng.get("expert_slots"),
            "expert_cache_mib": eng.get("expert_cache_mib"),
            "conversation_cache": conv,
            "hit_rate": hit,
            "hit_pct": hit_pct,
            "reused_tokens": totals.get("reused"),
            "prompt_tokens": totals.get("prompt_tokens"),
        },
        "spec": {
            "spec": eng.get("spec"),
            "mtp_max": eng.get("mtp_max"),
            "lookup": eng.get("lookup"),
            "min_p": eng.get("spec_min_p"),
            "drafts_offered": offered,
            "drafts_accepted": accepted,
            "accept_rate": accept_rate,
            "accept_pct": accept_pct,
        },
        "hardware": {
            "cpu_pct": hw.get("cpu"),
            "ram_used": hw.get("ram_used"),
            "ram_total": hw.get("ram_total"),
            "ram_pct": (hw["ram_used"] / hw["ram_total"] * 100) if hw.get("ram_total") else None,
            "vram_free_mib": eng.get("vram_free_mib"),
            "disk_read_mb": hw.get("disk_read_mb"),
            "disk_write_mb": hw.get("disk_write_mb"),
            "tok_s": hw.get("tok_s"),
            "tok_s_mean": hw.get("tok_s_mean"),
            "gpu_util": hw.get("gpu_util"),
            "gpu_mem_used": hw.get("gpu_mem_used"),
            "gpu_mem_total": hw.get("gpu_mem_total"),
            "gpu_temp": hw.get("gpu_temp"),
            "gpu_power": hw.get("gpu_power"),
            "gpu_power_limit": hw.get("gpu_power_limit"),
            "gpu_pcie_rx_mb": hw.get("gpu_pcie_rx_mb"),
            "gpu_pcie_gen": hw.get("gpu_pcie_gen"),
            "gpu_pcie_gen_max": hw.get("gpu_pcie_gen_max"),
            "gpu_pcie_width": hw.get("gpu_pcie_width"),
            "gpu_name": static.get("gpu_name"),
            "gpu_count": static.get("gpu_count"),
            "cpu_name": static.get("cpu_name"),
            "cores": static.get("cores"),
            "threads": static.get("threads"),
        },
        "throughput": {
            "now": tok_now,
            "mean": tok_mean,
            "prefill": prefill_now,
            "prefill_source": prefill_source,
            "source": tok_source,
        },
        "power": power,
        "gpu": gpu,
        "config": gather_config(),
        "engine_history": gather_history(),
        "requests": gather_requests(),
        "requests_kept": (metrics or {}).get("requests_kept"),
        "totals": totals or None,
        "switch": gather_switch(),
        "log": gather_log(),
        "endpoints": {
            "health": _get_json("/health") is not None,
            "metrics": metrics is not None,
            "slots": _get_json("/slots") is not None,
            "models": _get_json("/v1/models") is not None,
            "status": _get_json("/status") is not None,
        },
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    # Telemetry is the last step: it records this poll, then reads the history back so
    # the series and the analysis include the current sample.
    rows, analysis, telemetry_status = telemetry(stats)
    stats["telemetry"] = telemetry_status
    if rows:
        stats["history"] = {
            "tok_s": [r[1] for r in rows],
            "prefill": [r[2] for r in rows],
            "power_w": [r[4] for r in rows],
            "cpu": [r[5] for r in rows],
            "hit_pct": [r[6] for r in rows],
        }
        stats["history"]["requests"] = bucket_db_requests(
            [(r[0], r[3]) for r in rows]) or bucket_requests(metrics) or []
        # The engine's own gpu_* series pass through when they carry values, so a
        # build that reports them (or NVIDIA's NVML) gets a sparkline for free.
        for key in ("gpu_util", "gpu_temp", "gpu_mem_used", "gpu_pcie_rx_mb"):
            if gpu.get("history_available") and key in gpu_hist:
                stats["history"][key] = gpu_hist[key]
    else:
        stats["history"] = {}
        stats["history"]["requests"] = bucket_requests(metrics) or []
    stats["history"].setdefault("prefill", bucket_requests(metrics, extract=prefill_rate) or [])
    stats["history_bucket_s"] = 1800 / 24
    stats["analysis"] = analysis
    return stats


# ---------- HTTP server ----------


# ---------- HTTP server ----------
def serve(port):
    import http.server
    from functools import partial

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.rstrip("/") == "/api/stats":
                body = json.dumps(build_stats()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

    root = str(Path(__file__).resolve().parent)
    handler = partial(_Handler, directory=root)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    httpd.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT_DEFAULT
    print(f"Serving LLM monitor + /api/stats on http://localhost:{port} (Ctrl+C to stop)")
    serve(port)
