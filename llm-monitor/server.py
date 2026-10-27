#!/usr/bin/env python3
"""Local LLM monitor — serves the dashboard + a live /api/stats endpoint.

Run:  python server.py [port]     (default port 8090)
Then open http://localhost:8090

This is NOT the homelab dashboard. It monitors the local LLM engine that owns
port 8080 on this machine — either Strata (IQ3_S) or Vulkan llama.cpp (Qwen3.8-27B)
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

import http.server
import json
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import usage_ledger

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
# LLM_MONITOR_DB exists for the tests (audit-33 a33-34): the browser suite starts this
# real server, and without an override every /api/stats it requests appends a poll row
# to the production history — measured 2026-10-26 as 20,280 -> 20,282 rows for one request.
DB_PATH = os.environ.get("LLM_MONITOR_DB") or str(Path(__file__).resolve().with_name("telemetry.sqlite3"))

# M78 usage ledger (numbers only; README "Usage ledger"): its own SQLite file beside server.py and the two sources it reads.
# The LLM_MONITOR_* overrides exist for the tests (tests/usage/test_usage_api.py builds synthetic sources).
USAGE_DB = os.environ.get("LLM_MONITOR_USAGE_DB") or str(Path(__file__).resolve().with_name("usage.sqlite3"))
CLAUDE_ROOT = os.environ.get("LLM_MONITOR_CLAUDE_ROOT") or str(Path.home() / ".claude" / "projects")
HERMES_DB = os.environ.get("LLM_MONITOR_HERMES_DB") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "hermes", "state.db")
USAGE_STATUS = {"claude_code": "missing", "hermes": "missing"}
_USAGE_LOCK = threading.Lock()


def usage_ingest(budget_s=5.0):
    """One ingest pass (the thread every 60 s, and a catch-up before each /api/usage answer); one writer at a time.
    Returns partial: True when the time budget ran out or the pass failed (the answer then says so)."""
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
    """Daemon: ingest every 60 s, so the ledger fills with no dashboard tab open (audit #93 PA-01)."""
    while True:
        usage_ingest(5.0)
        time.sleep(60)
DB_MAX_ROWS = 20000
DB_PRUNE_EVERY = 500
DB_WINDOW_S = 3600  # the two analysis windows (recent vs previous)
DB_DAILY_MAX = 90   # finalized days kept in the rollup table (~3 months, pruned in telemetry)

# M81-T3 (audit-33 a33-10). Physical ceiling for a prefill (prompt-read) rate.
# Measured on this PC's live rows (20,165 non-null prefill samples, 2026-10-27):
# p50 345 tok/s, p90 1,093, and the honest source agrees — a real request read
# 5,941 tokens in 42,519.8 ms = 140 tok/s. The band above 2,000 holds only 65 of
# 20,165 rows, then a long tail runs to 1,905,830 tok/s, which no card of this
# class (decode 4-124 tok/s) can reach. The cause is prefill_rate(last_req)
# dividing a token count by a prompt_ms from a different request boundary, then
# re-sampling it every poll. Samples over this ceiling are excluded from every
# aggregate and never stored, and the aggregate carries prefill_bounded so the
# panel says so out loud rather than silently dropping them.
PREFILL_CEILING_TOK_S = 5000.0

# M81-T3 (audit-33 a33-17). A span shorter than one sampling period cannot
# support a per-minute or per-second rate: the live DB already holds duplicate
# timestamps (20,303 rows / 20,285 distinct), so last-first can be 0. Tied to the
# dashboard's REFRESH_MS (app.js:12), which is how often a poll row is written.
SPAN_FLOOR_S = 5.0

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

# Total VRAM for THIS machine's card (RX 7900 XTX = 24 GB GDDR). Used only to turn the
# engine's live `vram_free_mib` into a used/total VRAM reading on drivers that expose no
# gpu_mem_* counters. The panel labels it derived, never as a driver measurement.
VRAM_TOTAL_MIB = 24576

# How hard the GPU works per engine state, as a fraction of its peak. The same table
# drives both the modelled power draw and the modelled utilisation, so the two readings
# can never disagree. Prefill is dense GEMM (compute-bound, hottest); decode streams
# weights from VRAM (bandwidth-bound, well under peak on RDNA3); queued waits on the CPU.
GPU_ACTIVITY = {"reading": 1.0, "generating": 0.65, "processing": 0.65, "queued": 0.1}

# ---------- Host hardware detection (M81-T1, audit-33 a33-01) ----------
# The engine names our GPU for us, and on this PC it is wrong: it indexes the Windows
# display device class in class order, and a leftover driver entry for a card that was
# removed sorts ahead of the installed one. Measured here on 2026-10-26:
#   engine hardware_static  -> "AMD Radeon RX 6800 XT", gpu_vram_total_mib 16368
#   Windows PnP (live)      -> "AMD Radeon RX 7900 XTX", DEV_744C
# The discriminator is the PCI instance's ConfigFlags: the stale entry carries 32
# (not currently installed), the live one carries 0. Enumerating the instances and
# joining them to the class subkeys through the instance's Driver value gives the
# installed card plus its real 64-bit VRAM size, with stdlib only.
#
# Cost measured on this host: 1.3 ms, so it runs once at import and is cached. Never
# call it per poll. WMI is not in the standard library, and WMI's AdapterRAM is a
# UInt32 cap (~4 GB on a 24 GB card), so the registry's qwMemorySize is the only
# trustworthy size available here.
DISPLAY_CLASS_GUID = "{4d36e968-e325-11ce-bfc1-08002be10318}"


def _display_adapters():
    """This machine's display adapters from the registry: [{name, vram_mib, index, present}].

    Returns [] off Windows or when nothing can be read; a caller must treat an empty list as
    "no OS opinion", never as "no GPU".
    """
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []

    def val(key, name):
        try:
            return winreg.QueryValueEx(key, name)[0]
        except OSError:
            return None

    # 1. Which class subkeys belong to a PCI device that is actually present.
    installed = {}
    try:
        pci = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SYSTEM\\CurrentControlSet\\Enum\\PCI")
    except OSError:
        return []
    try:
        for i in range(winreg.QueryInfoKey(pci)[0]):
            dev_id = winreg.EnumKey(pci, i)
            try:
                dev_key = winreg.OpenKey(pci, dev_id)
            except OSError:
                continue
            try:
                for j in range(winreg.QueryInfoKey(dev_key)[0]):
                    inst_name = winreg.EnumKey(dev_key, j)
                    try:
                        inst = winreg.OpenKey(dev_key, inst_name)
                    except OSError:
                        continue
                    driver = val(inst, "Driver")
                    flags = val(inst, "ConfigFlags") or 0
                    winreg.CloseKey(inst)
                    if not isinstance(driver, str):
                        continue
                    head, _, sub = driver.partition("\\")
                    if head.lower() != DISPLAY_CLASS_GUID.lower() or not sub.isdigit():
                        continue
                    # 0x20 = the flag device tooling uses for "not currently present";
                    # 0x02 = disabled in Device Manager. Either way it is not our GPU.
                    if sub not in installed:
                        installed[sub] = (flags & (0x20 | 0x02)) == 0
            finally:
                winreg.CloseKey(dev_key)
    finally:
        winreg.CloseKey(pci)

    # 2. Read the name and the 64-bit VRAM size off those subkeys.
    out = []
    try:
        root = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            "SYSTEM\\CurrentControlSet\\Control\\Class\\" + DISPLAY_CLASS_GUID,
        )
    except OSError:
        return []
    try:
        for i in range(winreg.QueryInfoKey(root)[0]):
            sub = winreg.EnumKey(root, i)
            if not sub.isdigit():
                continue
            try:
                key = winreg.OpenKey(root, sub)
            except OSError:
                continue
            name = val(key, "DriverDesc")
            mem = val(key, "HardwareInformation.qwMemorySize")
            winreg.CloseKey(key)
            if not isinstance(name, str) or not name.strip():
                continue
            out.append({
                "index": sub,
                "name": name.strip(),
                "present": installed.get(sub, True),
                "vram_mib": int(mem) // (1024 * 1024) if isinstance(mem, int) else None,
            })
    finally:
        winreg.CloseKey(root)
    return out


def detect_host_hardware():
    """The GPU this machine actually has, resolved once at import.

    Filters the not-installed adapters out, then applies the same 2 GiB floor Strata's own
    helper uses so an APU's integrated Radeon cannot outrank a real card. Returns a dict:
      {"name", "vram_mib", "source": "os"|"unavailable", "adapters": [...], "stale": [...]}
    `stale` keeps the adapters that were filtered out, so a disagreement with the engine can
    be shown rather than hidden.
    """
    adapters = _display_adapters()
    live = [a for a in adapters if a["present"]]
    stale = [a for a in adapters if not a["present"]]
    # An integrated GPU (512 MiB on a modern APU) is not the card an LLM runs on; keep it
    # only when nothing bigger exists. Untested on this PC (the 5600X has no iGPU).
    big = [a for a in live if (a["vram_mib"] or 0) >= 2048]
    chosen = big or live
    if not chosen:
        return {"name": None, "vram_mib": None, "source": "unavailable",
                "adapters": adapters, "stale": stale}
    return {
        "name": chosen[0]["name"],
        # A model split across several cards is not what this reports; the engine's own
        # gpu_count stays authoritative for how many cards HIP loaded.
        "vram_mib": chosen[0]["vram_mib"],
        "source": "os",
        "adapters": chosen,
        "stale": stale,
    }


HOST_GPU = detect_host_hardware()


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

    # watchdog.log: [yyyy-MM-dd HH:MM:SS] msg (new format) or the legacy [HH:MM:SS] msg: both are parsed (CR-12), because
    # old lines stay in the file and an older watchdog keeps writing the short form until it is restarted
    for ln in _tail(LOG_FILES["watchdog"], 6):
        m = re.match(r"\[(?:\d{4}-\d{2}-\d{2} )?(\d{2}:\d{2}:\d{2})\]\s+(.*)", ln)
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
        prompt = r.get("prompt_tokens")
        out_tok = r.get("output_tokens")
        total_tok = (prompt or 0) + (out_tok or 0) if (prompt is not None or out_tok is not None) else None
        out.append({
            "duration_s": r.get("duration_s"),
            "finish": r.get("finish"),
            "total_tokens": total_tok,
            "prompt_tokens": prompt,
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
    activity = None

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
            activity = GPU_ACTIVITY.get(state or "", 0.0)
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
        # Alias of peak_w (M81-T2, audit-33 a33-03): the Compact HUD power gauge reads
        # power.rated_w, which build_stats never emitted, so that gauge sat at 0 and its hint
        # always fell back to "of rated peak". peak_w stays the canonical key; read that one.
        "rated_w": peak,
        "pct_of_peak": round(total / peak * 100, 1) if total and peak else None,
        "source": source,
        "model": POWER_MODEL,
        # The same activity fraction that scaled the power draw, exposed so the GPU
        # panel's modelled utilisation and the power figure cannot drift apart.
        "activity": round(activity * 100, 1) if source == "modelled" else None,
    }


# ---------- Telemetry (sqlite) ----------
# One numeric row per poll. Everything the analysis needs is a delta or an average over
# these rows, so no JSON is stored and the file stays a couple of MB regardless of how
# long the engine runs.
def db_init():
    """Open (creating if needed) the telemetry database.

    The connection is opened per poll, not cached across polls: ThreadingHTTPServer
    handles each request in its own thread, and Python's sqlite3 refuses to use a
    connection in a thread other than the one that created it (ProgrammingError). The
    CREATE is guarded so the table surviving from a previous run is not an error.
    """
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(
            "CREATE TABLE poll ("
            "t REAL, cpu REAL, ram REAL, tok_s REAL, prefill REAL,"
            "ctx_used REAL, ctx_pct REAL, hit_pct REAL, accept_pct REAL,"
            "reqs INTEGER, prompt_tokens INTEGER, reused INTEGER, output_tokens INTEGER,"
            "power_w REAL, power_src TEXT, gpu_util REAL, gpu_power REAL, busy INTEGER,"
            " vram_used REAL, vram_total REAL,"
            " drafts_offered INTEGER, drafts_accepted INTEGER, pcie_share REAL,"
            " prompt_ms REAL)"
        )
    except sqlite3.OperationalError:
        pass  # the table survived from a previous run
    # A table from an older build lacks the newer columns; ALTER them in so the
    # existing history survives each schema change rather than being reset. The
    # draft counters + pcie_share are the richer dogfooding fields (a7-05): they
    # come from data the poll already fetches (totals + request records), so they
    # add no extra engine request.
    for col, ctype in (("vram_used", "REAL"), ("vram_total", "REAL"),
                       ("drafts_offered", "INTEGER"), ("drafts_accepted", "INTEGER"),
                       ("pcie_share", "REAL"),
                       # M81-T3 (a33-11): the engine's cumulative prompt_ms, so a
                       # window's prefill rate can be read/prompt_ms instead of an
                       # unweighted mean of per-poll instantaneous rates. Rows from
                       # before this column exist have NULL, which every reader here
                       # treats as "no weighted figure", never as 0.
                       ("prompt_ms", "REAL")):
        try:
            con.execute(f"ALTER TABLE poll ADD COLUMN {col} {ctype}")
        except sqlite3.OperationalError:
            pass  # the column is already there
    try:
        con.execute(
            "CREATE TABLE day (d INTEGER, polls INTEGER, span_s REAL, reqs INTEGER,"
            " prompt INTEGER, reused INTEGER, output INTEGER, tok_mean REAL, tok_max REAL,"
            " prefill_mean REAL, hit_mean REAL, accept_mean REAL, power_mean REAL,"
            " energy_wh REAL, idle_pct REAL, hours TEXT)"
        )
    except sqlite3.OperationalError:
        pass  # the table survived from a previous run
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_poll_t ON poll(t)")
    except sqlite3.OperationalError:
        pass
    try:
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_day_d ON day(d)")
    except sqlite3.OperationalError:
        pass
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
    gpu = stats.get("gpu") or {}
    reqs = stats.get("requests") or []
    last_req = reqs[0] if reqs and isinstance(reqs[0], dict) else None
    con.execute(
        "INSERT INTO poll (t, cpu, ram, tok_s, prefill, ctx_used, ctx_pct, hit_pct, accept_pct,"
        " reqs, prompt_tokens, reused, output_tokens, power_w, power_src, gpu_util, gpu_power, busy,"
        " vram_used, vram_total, drafts_offered, drafts_accepted, pcie_share, prompt_ms)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            now,
            hw.get("cpu_pct"), hw.get("ram_used"),
            # The prefill sample is stored as build_stats produced it. Since M81-T3
            # build_stats bounds it at the source, so new rows never hold an
            # impossible rate; rows written before that fix keep their raw value on
            # purpose (the DB stays the honest record and /api/export can still show
            # what the engine really reported), which is why every aggregate here
            # bounds defensively as well.
            thr.get("now"), thr.get("prefill"),
            ctx.get("used"), ctx.get("pct"),
            cache.get("hit_pct"), spec.get("accept_pct"),
            totals.get("requests"), totals.get("prompt_tokens"), totals.get("reused"), totals.get("output_tokens"),
            power.get("total_w"), power.get("source"),
            gpu.get("util_pct"), gpu.get("power_w"),
            1 if live.get("state") not in ("idle", None) else 0,
            gpu.get("mem_used"), gpu.get("mem_total"),
            totals.get("drafts_offered"), totals.get("drafts_accepted"),
            (last_req or {}).get("pcie_share"),
            # M81-T3: the engine's cumulative prompt_ms (the denominator a window
            # prefill rate needs) and a prefill sample that is bounded at the source,
            # so an impossible reading never reaches the DB, the chart axis or any
            # aggregate. thr["prefill_bounded"] says the bound fired this poll.
            totals.get("prompt_ms"),
        ),
    )
    con.commit()
    return now


def db_prune(con):
    """Drop the oldest rows past the cap in one DELETE."""
    cut = con.execute("SELECT t FROM poll ORDER BY t DESC LIMIT 1 OFFSET ?", (DB_MAX_ROWS,)).fetchone()
    if cut:
        con.execute("DELETE FROM poll WHERE t < ?", (cut[0],))
        con.commit()


def db_prune_days(con):
    """Drop rollup days older than the retention window so history stays ~3 months.

    db_finalize_days bounds which days it WRITES but never deletes old ones, so without
    this the day table grows unbounded on disk. Days are tiny (one row/day), so a full-scan
    DELETE over a <=90-row table is trivial and runs every poll.
    """
    latest = con.execute("SELECT t FROM poll ORDER BY t DESC LIMIT 1").fetchone()
    if not latest:
        return
    today = int(latest[0] // 86400)
    con.execute("DELETE FROM day WHERE d < ?", (today - DB_DAILY_MAX,))
    con.commit()


def cumulative_delta(rows, idx):
    """Span total from a cumulative counter that may reset mid-span.

    The engine's counters reset when it restarts, so a plain last-minus-first can
    go negative (or swallow a whole session). Split at each decrease and sum the
    segments; the first segment contributes only its own movement, since the
    counter's baseline predates recording.
    """
    total = 0
    seg_start = None
    prev = None
    for r in rows:
        v = r[idx]
        if v is None:
            continue
        if prev is None or v < prev:
            if prev is not None and seg_start is not None:
                total += prev - seg_start
            seg_start = v
        prev = v
    if prev is not None and seg_start is not None:
        total += prev - seg_start
    return total


def window_pct(rows, num_idx, den_idx):
    """The span's OWN ratio, from two cumulative counters (M81-T3, a33-08).

    The per-poll hit_pct / accept_pct columns store session-cumulative ratios
    (server.py build_stats divides the engine's lifetime totals), so averaging
    them per poll answers "what has this engine done since it started", not
    "what did it do in this window". Measured 2026-10-27 over the last 60 min:
    the per-poll mean showed 65.96 % while the window's own delta ratio is 88.19 %.
    Both sides are cumulative counters, so their deltas give the window figure.
    Returns None when the window moved no denominator (no prompt read, no drafts
    offered) — an empty window has no rate, which is not the same as 0 %.
    """
    den = cumulative_delta(rows, den_idx)
    if not den:
        return None
    num = cumulative_delta(rows, num_idx) or 0
    return num / den * 100


def bounded_prefill(vals):
    """(mean, max, bounded) over prefill samples that are physically possible.

    See PREFILL_CEILING_TOK_S for the measurement behind the ceiling. The flag is
    returned so every consumer can label the number rather than quietly showing a
    filtered mean (a33-10: stored rows reach 1,905,830 tok/s on a card that
    decodes at 4-124). Never silently drops data: the caller must print the tag.
    """
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, None, False
    kept = [v for v in vals if v <= PREFILL_CEILING_TOK_S]
    bounded = len(kept) != len(vals)
    if not kept:
        # Every sample was impossible: report nothing rather than a fake number.
        return None, None, True
    return sum(kept) / len(kept), max(kept), bounded


def day_aggregates(con, lo, hi):
    """Summarise one [lo, hi) span of poll rows (a UTC day slice).

    Cumulative counters make a span's real work last-minus-first, split at
    counter resets (see cumulative_delta); the per-poll columns give means/max
    directly. Also returns 24 hourly request counts so the day scrubber can
    draw a day's activity without keeping per-hour rows.

    M81-T3 (audit-34 G-34-03): the row just before `lo` is carried in as a delta
    baseline only, the same trick db_hour_aggregates already uses. Without it the
    first hour of a day has no baseline and its movement lands in no day at all —
    measured with rows (DAY-300, reqs=5) (DAY+600, 8) (DAY+4000, 12), the old code
    reported 4 for the day when the true movement is 7. The baseline row is NOT
    counted in polls/span/idle, which describe the day itself.
    """
    base = con.execute(
        "SELECT t, tok_s, prefill, hit_pct, accept_pct, reqs, prompt_tokens, reused,"
        " output_tokens, power_w, busy, drafts_offered, drafts_accepted"
        " FROM poll WHERE t < ? ORDER BY t DESC LIMIT 1",
        (lo,)).fetchone()
    rows = con.execute(
        "SELECT t, tok_s, prefill, hit_pct, accept_pct, reqs, prompt_tokens,"
        " reused, output_tokens, power_w, busy, drafts_offered, drafts_accepted"
        " FROM poll WHERE t >= ? AND t < ? ORDER BY t",
        (lo, hi)).fetchall()
    if not rows:
        return None
    # Delta maths sees the carried baseline; per-poll stats see only the day's rows.
    span_rows = ([base] if base else []) + rows

    def avg(i):
        vals = [r[i] for r in rows if r[i] is not None]
        return sum(vals) / len(vals) if vals else None

    power_vals = [r[9] for r in rows if r[9] is not None]
    span = rows[-1][0] - rows[0][0]
    hours = []
    prev_seg_last = base
    for h in range(24):
        h_lo = lo + h * 3600
        h_hi = h_lo + 3600
        seg = [r for r in rows if h_lo <= r[0] < h_hi]
        if not seg:
            hours.append(0)
            continue
        # With a baseline the segment can be one row; without one it needs two.
        seg = ([prev_seg_last] + seg) if prev_seg_last else seg
        hours.append(cumulative_delta(seg, 5))
        prev_seg_last = seg[-1]
    prompt_tok = cumulative_delta(span_rows, 6)
    reused_tok = cumulative_delta(span_rows, 7)
    output_tok = cumulative_delta(span_rows, 8)
    req_delta = cumulative_delta(span_rows, 5)
    tot_tok = (prompt_tok or 0) + (output_tok or 0)

    # Ghost-idle suppression (M81-T3, a33-13): db_analysis has had this since M75,
    # day_aggregates never did, so a 0-request day rolled up a stale per-poll rate
    # that then fed the week/month weighted means in db_periods.
    if req_delta > 0 or tot_tok > 0:
        tok_s_mean = avg(1)
        tok_s_max = max((r[1] for r in rows if r[1] is not None), default=None)
        prefill_mean, prefill_max, prefill_bounded = bounded_prefill([r[2] for r in rows])
    else:
        tok_s_mean = None
        tok_s_max = None
        prefill_mean = None
        prefill_max = None
        prefill_bounded = False
    return {
        "polls": len(rows),
        "span_s": round(span, 1),
        "requests": req_delta,
        "total_tokens": tot_tok,
        "prompt_tokens": prompt_tok,
        "reused": reused_tok,
        "output_tokens": output_tok,
        "tok_s_mean": tok_s_mean,
        "tok_s_max": tok_s_max,
        "prefill_mean": prefill_mean,
        "prefill_max": prefill_max,
        "prefill_bounded": prefill_bounded,
        # M81-T3 (a33-08): the day's OWN ratio, not a mean of session-cumulative
        # per-poll ratios. Old rollup rows keep whatever was written at the time;
        # only days finalised from now on carry the window figure. accept uses the
        # draft counters (a7-05), which is what an accept rate is actually made of.
        "hit_mean": window_pct(span_rows, 7, 6),
        "accept_mean": window_pct(span_rows, 12, 11),
        "power_mean": avg(9),
        "energy_wh": round(sum(power_vals) * span / 3600 / len(power_vals), 3) if power_vals else None,
        "idle_pct": round(100 * sum(1 for r in rows if not r[10]) / len(rows), 1),
        "hours": hours,
    }


def db_finalize_days(con):
    """Freeze ended UTC days into the rollup table before pruning can drop them.

    The poll table only holds ~28h of rows, so daily/weekly/monthly views need a
    tiny per-day table written at the day boundary. Days with no polls are skipped
    (a gap, honestly rendered as missing).
    """
    latest = con.execute("SELECT t FROM poll ORDER BY t DESC LIMIT 1").fetchone()
    oldest = con.execute("SELECT t FROM poll ORDER BY t ASC LIMIT 1").fetchone()
    if not latest or not oldest:
        return
    today = int(latest[0] // 86400)
    have = {r[0] for r in con.execute("SELECT d FROM day")}
    for d in range(max(int(oldest[0] // 86400), today - DB_DAILY_MAX), today):
        if d in have:
            continue
        agg = day_aggregates(con, d * 86400, (d + 1) * 86400)
        if not agg:
            continue
        con.execute(
            "INSERT INTO day (d, polls, span_s, reqs, prompt, reused, output,"
            " tok_mean, tok_max, prefill_mean, hit_mean, accept_mean, power_mean,"
            " energy_wh, idle_pct, hours) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d, agg["polls"], agg["span_s"], agg["requests"], agg["prompt_tokens"],
             agg["reused"], agg["output_tokens"], agg["tok_s_mean"], agg["tok_s_max"],
             agg["prefill_mean"], agg["hit_mean"], agg["accept_mean"], agg["power_mean"],
             agg["energy_wh"], agg["idle_pct"], json.dumps(agg["hours"])),
        )
    con.commit()


def _iso_day(d):
    return datetime.fromtimestamp(d * 86400, timezone.utc).strftime("%Y-%m-%d")


def db_hour_aggregates(con, lo, hi):
    """Summarise poll rows in [lo, hi) anchored to the preceding boundary row."""
    # prompt_ms (index 13) is only read by prefill_weighted; rows written before the
    # column exists come back NULL, which keeps that figure None rather than guessed.
    base = con.execute(
        "SELECT t, tok_s, prefill, hit_pct, accept_pct, reqs, prompt_tokens, reused, output_tokens, power_w, busy, "
        "drafts_offered, drafts_accepted, prompt_ms FROM poll WHERE t < ? ORDER BY t DESC LIMIT 1", (lo,)).fetchone()
    rows = con.execute(
        "SELECT t, tok_s, prefill, hit_pct, accept_pct, reqs, prompt_tokens, reused, output_tokens, power_w, busy, "
        "drafts_offered, drafts_accepted, prompt_ms FROM poll WHERE t >= ? AND t < ? ORDER BY t", (lo, hi)).fetchall()
    if not rows:
        return None
    all_rows = ([base] + rows) if base else rows
    first, last = (all_rows[0], all_rows[-1]) if all_rows else (rows[0], rows[-1])
    # M81-T3 (a33-17): the old max(1e-9, ...) sentinel made the "if span > 0" guard
    # below unreachable and let a duplicate-timestamp span divide by 1e-9. A span
    # under one sampling period cannot support a rate at all.
    span = last[0] - first[0]
    rate_ok = span >= SPAN_FLOOR_S
    req_delta = cumulative_delta(all_rows, 5) if all_rows else 0
    prompt_delta = cumulative_delta(all_rows, 6) if all_rows else 0
    reused_delta = cumulative_delta(all_rows, 7) if all_rows else 0
    output_delta = cumulative_delta(all_rows, 8) if all_rows else 0
    tot_tokens = (prompt_delta or 0) + (output_delta or 0)

    # Suppress ghost throughput: if 0 requests and 0 tokens occurred, tok_s_mean MUST be None!
    if req_delta > 0 or tot_tokens > 0:
        tok_vals = [r[1] for r in rows if r[1] is not None]
        tok_mean = sum(tok_vals) / len(tok_vals) if tok_vals else None
        tok_max = max(tok_vals, default=None)
        prefill_mean, prefill_max, prefill_bounded = bounded_prefill([r[2] for r in rows])
    else:
        tok_mean = None
        tok_max = None
        prefill_mean = None
        prefill_max = None
        prefill_bounded = False

    power_vals = [r[9] for r in rows if r[9] is not None]
    hit_vals = [r[3] for r in rows if r[3] is not None]
    accept_vals = [r[4] for r in rows if r[4] is not None]

    return {
        "polls": len(rows),
        "span_s": round(span, 1),
        "requests": req_delta,
        "total_tokens": tot_tokens,
        "prompt_tokens": prompt_delta,
        "reused": reused_delta,
        "output_tokens": output_delta,
        "req_per_min": round(req_delta / span * 60, 2) if (rate_ok and span > 0) else None,
        "tok_s_mean": tok_mean,
        "tok_s_max": tok_max,
        "prefill_mean": prefill_mean,
        "prefill_max": prefill_max,
        "prefill_bounded": prefill_bounded,
        "hit_pct_mean": (sum(hit_vals) / len(hit_vals)) if hit_vals else None,
        "accept_pct_mean": (sum(accept_vals) / len(accept_vals)) if accept_vals else None,
        # M81-T3 (a33-08): the span's own ratios, computed from the cumulative
        # counters. Additive keys; *_pct_mean stay as they were so no existing
        # consumer changes meaning, and the panel reads these instead.
        "hit_pct_window": window_pct(all_rows, 7, 6),
        "accept_pct_window": window_pct(all_rows, 12, 11),
        # M81-T3 (a33-09/a33-11): a rate over the span, not a mean of instantaneous
        # per-poll rates. tok_s_mean weights every idle poll equally with every
        # busy one, so a long idle stretch drags the figure toward zero.
        "tok_s_weighted": (output_delta / span) if (rate_ok and output_delta) else None,
        # Same rule as db_analysis: prompt_ms is a cumulative counter, so a span whose
        # rows predate the column has no computable prefill rate.
        "prefill_weighted": (
            round(max(0.0, prompt_delta - reused_delta) / ms_delta * 1000, 2)
            if (rate_ok and (ms_delta := cumulative_delta(all_rows, 13))) else None),
        "power_w_mean": (sum(power_vals) / len(power_vals)) if power_vals else None,
        "energy_wh": round(sum(power_vals) * span / 3600 / len(power_vals), 3) if power_vals else None,
        "idle_pct": round(100 * sum(1 for r in rows if not r[10]) / len(rows), 1),
    }


def db_daily(con, limit=DB_DAILY_MAX):
    """Finalized days oldest-first plus today's live partial, as day dicts."""
    out = []
    for r in con.execute(
        "SELECT d, polls, span_s, reqs, prompt, reused, output,"
        " tok_mean, tok_max, prefill_mean, hit_mean, accept_mean, power_mean,"
        " energy_wh, idle_pct, hours FROM day ORDER BY d"
    ):
        out.append({
            "d": r[0], "date": _iso_day(r[0]), "polls": r[1], "requests": r[3],
            "total_tokens": (r[4] or 0) + (r[6] or 0),
            "prompt_tokens": r[4], "reused": r[5], "output_tokens": r[6],
            "tok_s_mean": r[7], "tok_s_max": r[8], "prefill_mean": r[9],
            "hit_mean": r[10], "accept_mean": r[11], "power_mean": r[12],
            "energy_wh": r[13], "idle_pct": r[14], "hours": json.loads(r[15]),
        })
    now = datetime.now(timezone.utc).timestamp()
    d = int(now // 86400)
    agg = day_aggregates(con, d * 86400, now + 1)
    if agg:
        agg["d"] = d
        agg["date"] = _iso_day(d)
        agg["total_tokens"] = (agg.get("prompt_tokens") or 0) + (agg.get("output_tokens") or 0)
        out.append(agg)
    return out[-limit:]


def db_timeseries(con, range_str="1h"):
    """Aggregate telemetry history into bucketed timeseries for charting.

    Supports minute, hourly, and daily ranges with counter-reset safety.
    """
    now = datetime.now(timezone.utc).timestamp()
    ranges = {
        "15m": (900, 30),
        "1h": (3600, 60),
        "3h": (10800, 60),
        "6h": (21600, 60),
        "12h": (43200, 60),
        "24h": (86400, 48),
    }
    days_map = {"7d": 7, "30d": 30, "90d": 90}

    if range_str in ranges:
        span_s, num_buckets = ranges[range_str]
        bucket_s = span_s / num_buckets
        start_t = now - span_s
        rows = con.execute(
            "SELECT t, tok_s, prefill, reqs, prompt_tokens, reused, output_tokens "
            "FROM poll WHERE t >= ? ORDER BY t ASC",
            (start_t - bucket_s,),
        ).fetchall()

        buckets = []
        last_reqs = None
        last_prompt = None
        last_reused = None
        last_output = None

        init_rows = [r for r in rows if r[0] < start_t]
        if init_rows:
            last_reqs = init_rows[-1][3]
            last_prompt = init_rows[-1][4]
            last_reused = init_rows[-1][5]
            last_output = init_rows[-1][6]

        for b in range(num_buckets):
            b_lo = start_t + b * bucket_s
            b_hi = b_lo + bucket_s
            b_mid = b_lo + bucket_s / 2
            b_rows = [r for r in rows if b_lo <= r[0] < b_hi]

            tok_vals = [r[1] for r in b_rows if r[1] is not None]
            prefill_vals = [r[2] for r in b_rows if r[2] is not None]

            cur_reqs = b_rows[-1][3] if b_rows else None
            cur_prompt = b_rows[-1][4] if b_rows else None
            cur_reused = b_rows[-1][5] if b_rows else None
            cur_output = b_rows[-1][6] if b_rows else None

            def calc_delta(cur, prev, col_idx):
                if cur is None:
                    return 0
                if prev is None:
                    return cumulative_delta(b_rows, col_idx) or 0
                return max(0, cur - prev) if cur >= prev else cur

            req_delta = calc_delta(cur_reqs, last_reqs, 3)
            prompt_delta = calc_delta(cur_prompt, last_prompt, 4)
            reused_delta = calc_delta(cur_reused, last_reused, 5)
            output_delta = calc_delta(cur_output, last_output, 6)

            if cur_reqs is not None:
                last_reqs = cur_reqs
            if cur_prompt is not None:
                last_prompt = cur_prompt
            if cur_reused is not None:
                last_reused = cur_reused
            if cur_output is not None:
                last_output = cur_output

            dt = datetime.fromtimestamp(b_mid, timezone.utc)
            label = dt.strftime("%H:%M" if span_s >= 3600 else "%H:%M:%S")

            buckets.append({
                "t": round(b_mid, 1),
                "time": dt.isoformat(),
                "label": label,
                "requests": req_delta,
                "prompt_tokens": prompt_delta,
                "reused": reused_delta,
                "output_tokens": output_delta,
                "total_tokens": prompt_delta + output_delta,
                "tok_s_mean": round(sum(tok_vals) / len(tok_vals), 1) if tok_vals else None,
                "tok_s_max": round(max(tok_vals), 1) if tok_vals else None,
                "prefill_mean": round(sum(prefill_vals) / len(prefill_vals), 1) if prefill_vals else None,
                "prefill_max": round(max(prefill_vals), 1) if prefill_vals else None,
            })

    elif range_str in days_map:
        num_days = days_map[range_str]
        span_s = num_days * 86400
        bucket_s = 86400
        today_idx = int(now // 86400)
        start_day = today_idx - (num_days - 1)

        day_rows = con.execute(
            "SELECT d, reqs, prompt, reused, output, tok_mean, tok_max, prefill_mean "
            "FROM day WHERE d >= ? ORDER BY d ASC",
            (start_day,),
        ).fetchall()
        by_d = {r[0]: r for r in day_rows}

        today_start = today_idx * 86400
        today_agg = day_aggregates(con, today_start, now)

        buckets = []
        for d in range(start_day, today_idx + 1):
            dt = datetime.fromtimestamp(d * 86400 + 43200, timezone.utc)
            label = dt.strftime("%b %d")
            if d == today_idx and today_agg:
                buckets.append({
                    "t": d * 86400 + 43200,
                    "time": dt.isoformat(),
                    "label": label,
                    "requests": today_agg.get("requests") or 0,
                    "prompt_tokens": today_agg.get("prompt_tokens") or 0,
                    "reused": today_agg.get("reused") or 0,
                    "output_tokens": today_agg.get("output_tokens") or 0,
                    "total_tokens": today_agg.get("total_tokens") or 0,
                    "tok_s_mean": today_agg.get("tok_s_mean"),
                    "tok_s_max": today_agg.get("tok_s_max"),
                    "prefill_mean": today_agg.get("prefill_mean"),
                    "prefill_max": None,
                })
            elif d in by_d:
                r = by_d[d]
                p = r[2] or 0
                o = r[4] or 0
                buckets.append({
                    "t": d * 86400 + 43200,
                    "time": dt.isoformat(),
                    "label": label,
                    "requests": r[1] or 0,
                    "prompt_tokens": p,
                    "reused": r[3] or 0,
                    "output_tokens": o,
                    "total_tokens": p + o,
                    "tok_s_mean": r[5],
                    "tok_s_max": r[6],
                    "prefill_mean": r[7],
                    "prefill_max": None,
                })
            else:
                buckets.append({
                    "t": d * 86400 + 43200,
                    "time": dt.isoformat(),
                    "label": label,
                    "requests": 0,
                    "prompt_tokens": 0,
                    "reused": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "tok_s_mean": None,
                    "tok_s_max": None,
                    "prefill_mean": None,
                    "prefill_max": None,
                })
    else:
        return None

    tok_means = [b["tok_s_mean"] for b in buckets if b["tok_s_mean"] is not None]
    tok_maxes = [b["tok_s_max"] for b in buckets if b["tok_s_max"] is not None]
    pre_means = [b["prefill_mean"] for b in buckets if b["prefill_mean"] is not None]
    pre_maxes = [b["prefill_max"] for b in buckets if b["prefill_max"] is not None]

    summary = {
        "total_requests": sum(b["requests"] for b in buckets),
        "total_tokens": sum(b["total_tokens"] for b in buckets),
        "prompt_tokens": sum(b["prompt_tokens"] for b in buckets),
        "output_tokens": sum(b["output_tokens"] for b in buckets),
        "reused_tokens": sum(b["reused"] for b in buckets),
        "tok_s_mean": round(sum(tok_means) / len(tok_means), 1) if tok_means else None,
        "tok_s_max": max(tok_maxes) if tok_maxes else None,
        "prefill_mean": round(sum(pre_means) / len(pre_means), 1) if pre_means else None,
        "prefill_max": max(pre_maxes) if pre_maxes else None,
    }

    return {
        "range": range_str,
        "span_s": span_s,
        "bucket_s": bucket_s,
        "buckets": buckets,
        "summary": summary,
    }


def db_export(con, fmt="json"):
    """Serialize the retained history for sharing with an agent (JSON string or CSV text).

    The poll table is already bounded to DB_MAX_ROWS and the day rollup to DB_DAILY_MAX
    (pruned in telemetry), so this is exactly the window we keep -- nothing older leaks out.
    Poll rows are emitted as NAMED fields (not positional tuples) so a reader can use them
    without the source, and a meta block states the window and schema. This is the
    "usable data, not garbage" contract: field names, units, and provenance travel with it.
    Always returns a string (JSON is pre-serialized) so the caller never juggles types.
    """
    poll_cols = ("t", "cpu", "ram", "tok_s", "prefill", "ctx_used", "ctx_pct", "hit_pct",
                 "accept_pct", "reqs", "prompt_tokens", "reused", "output_tokens",
                 "power_w", "power_src", "gpu_util", "gpu_power", "busy", "vram_used", "vram_total",
                 "drafts_offered", "drafts_accepted", "pcie_share")
    rows = con.execute(f"SELECT {', '.join(poll_cols)} FROM poll ORDER BY t").fetchall()
    days = db_daily(con)
    if fmt == "csv":
        import csv
        import io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(poll_cols)
        for r in rows:
            w.writerow(r)
        return buf.getvalue()
    return json.dumps({
        "generated": datetime.now(timezone.utc).timestamp(),
        "window_days": DB_DAILY_MAX,
        "poll_cols": list(poll_cols),
        "poll_rows": [dict(zip(poll_cols, r)) for r in rows],
        "days": days,
    })


def db_periods(dlist, analysis=None, requests=None, hourly=None):
    """Today vs yesterday, this week vs previous, this month vs previous, this hour vs last hour, last request vs previous request.

    Weeks start Monday (UTC); months are calendar months. Means are poll-weighted
    across the days in a period, so a quiet day cannot skew an average.
    """
    req_cur = None
    req_prev = None
    if requests and len(requests) >= 1:
        r0 = requests[0]
        t0 = r0.get("total_tokens")
        if t0 is None and (r0.get("prompt_tokens") is not None or r0.get("output_tokens") is not None):
            t0 = (r0.get("prompt_tokens") or 0) + (r0.get("output_tokens") or 0)
        req_cur = {
            "requests": 1,
            "total_tokens": t0,
            "prompt_tokens": r0.get("prompt_tokens"),
            "output_tokens": r0.get("output_tokens"),
            "tok_s_mean": r0.get("decode_tok_s"),
            "duration_s": r0.get("duration_s"),
        }
    if requests and len(requests) >= 2:
        r1 = requests[1]
        t1 = r1.get("total_tokens")
        if t1 is None and (r1.get("prompt_tokens") is not None or r1.get("output_tokens") is not None):
            t1 = (r1.get("prompt_tokens") or 0) + (r1.get("output_tokens") or 0)
        req_prev = {
            "requests": 1,
            "total_tokens": t1,
            "prompt_tokens": r1.get("prompt_tokens"),
            "output_tokens": r1.get("output_tokens"),
            "tok_s_mean": r1.get("decode_tok_s"),
            "duration_s": r1.get("duration_s"),
        }

    if hourly:
        hour_cur = hourly.get("current")
        hour_prev = hourly.get("previous")
    else:
        hour_cur = (analysis or {}).get("recent")
        hour_prev = (analysis or {}).get("previous")

    req_block = {
        "current": req_cur,
        "previous": req_prev,
        "current_label": "Last request",
        "previous_label": "Previous request",
    }

    now_ts = datetime.now(timezone.utc).timestamp()
    today = int(now_ts // 86400)

    if not dlist:
        day_span_cur = {
            "requests": 0, "total_tokens": 0, "prompt_tokens": 0, "output_tokens": 0,
            "energy_wh": 0.0, "tok_s_mean": None, "tok_s_max": None, "hit_mean": None,
            "accept_mean": None, "idle_pct": 100.0, "days": 0,
        }
        return {
            "request": req_block,
            "hour": {"current": hour_cur, "previous": hour_prev,
                     "current_label": "This hour", "previous_label": "Last hour"},
            "day": {"current": day_span_cur, "previous": None,
                    "current_label": "Today", "previous_label": "Yesterday"},
            "week": None, "month": None,
            "token_history": {
                "last_request": req_cur.get("total_tokens") if req_cur else None,
                "prev_request": req_prev.get("total_tokens") if req_prev else None,
                "this_hour": (hour_cur.get("total_tokens") if hour_cur else 0) or 0,
                "last_hour": hour_prev.get("total_tokens") if hour_prev else None,
                "today": 0, "yesterday": None, "this_week": 0, "this_month": 0,
            },
        }
    by_d = {x["d"]: x for x in dlist}

    def span(day_indices):
        ds = [by_d[d] for d in day_indices if d in by_d]
        if not ds:
            return None
        polls = sum(x["polls"] for x in ds) or 1

        def wmean(key):
            pairs = [(x[key], x["polls"]) for x in ds if x[key] is not None]
            tot = sum(w for _, w in pairs)
            return sum(v * w for v, w in pairs) / tot if tot else None

        return {
            "requests": sum(x["requests"] or 0 for x in ds),
            "total_tokens": sum((x.get("total_tokens") or ((x.get("prompt_tokens") or 0) + (x.get("output_tokens") or 0))) for x in ds),
            "prompt_tokens": sum(x["prompt_tokens"] or 0 for x in ds),
            "output_tokens": sum(x["output_tokens"] or 0 for x in ds),
            "energy_wh": round(sum(x["energy_wh"] or 0 for x in ds), 2),
            "tok_s_mean": wmean("tok_s_mean"),
            "tok_s_max": max((x["tok_s_max"] for x in ds if x["tok_s_max"] is not None), default=None),
            "hit_mean": wmean("hit_mean"),
            "accept_mean": wmean("accept_mean"),
            "idle_pct": round(sum(x["idle_pct"] * x["polls"] for x in ds) / polls, 1),
            "days": len(ds),
        }

    def month_key(d):
        dt = datetime.fromtimestamp(d * 86400, timezone.utc)
        return (dt.year, dt.month)

    now_dt = datetime.fromtimestamp(today * 86400, timezone.utc)
    first_ts = (today - (now_dt.day - 1)) * 86400
    prev_dt = datetime.fromtimestamp(first_ts - 86400, timezone.utc)
    cur_month = (now_dt.year, now_dt.month)
    prev_month = (prev_dt.year, prev_dt.month)
    wk = today - (today + 3) % 7  # Monday of the current week (epoch day 0 is a Thursday)
    day_span_cur = span([today]) or {
        "requests": 0, "total_tokens": 0, "prompt_tokens": 0, "output_tokens": 0,
        "energy_wh": 0.0, "tok_s_mean": None, "tok_s_max": None, "hit_mean": None,
        "accept_mean": None, "idle_pct": 100.0, "days": 0,
    }
    day_span_prev = span([today - 1])
    week_span_cur = span(range(wk, today + 1))
    week_span_prev = span(range(wk - 7, wk))
    month_span_cur = span([x["d"] for x in dlist if month_key(x["d"]) == cur_month])
    month_span_prev = span([x["d"] for x in dlist if month_key(x["d"]) == prev_month])

    return {
        "request": req_block,
        "hour": {"current": hour_cur, "previous": hour_prev,
                 "current_label": "This hour", "previous_label": "Last hour"},
        "day": {"current": day_span_cur, "previous": day_span_prev,
                "current_label": "Today", "previous_label": "Yesterday"},
        "week": {"current": week_span_cur, "previous": week_span_prev,
                 "current_label": "This week", "previous_label": "Last week"},
        "month": {"current": month_span_cur, "previous": month_span_prev,
                  "current_label": "This month", "previous_label": "Last month"},
        "token_history": {
            "last_request": req_cur.get("total_tokens") if req_cur else None,
            "prev_request": req_prev.get("total_tokens") if req_prev else None,
            "this_hour": (hour_cur.get("total_tokens") if hour_cur else 0) or 0,
            "last_hour": hour_prev.get("total_tokens") if hour_prev else None,
            "today": (day_span_cur.get("total_tokens") if day_span_cur else 0) or 0,
            "yesterday": day_span_prev.get("total_tokens") if day_span_prev else None,
            "this_week": (week_span_cur.get("total_tokens") if week_span_cur else 0) or 0,
            "this_month": (month_span_cur.get("total_tokens") if month_span_cur else 0) or 0,
        },
    }


def db_analysis(con, window_s=DB_WINDOW_S):
    """Compare the recent window against the one before it.

    One scan over a bounded table, split in Python, so the cost does not grow with uptime.
    Cumulative totals are stored per row, so a window's real work is the difference between
    its first and last row.
    """
    now = datetime.now(timezone.utc).timestamp()
    rows = con.execute(
        "SELECT t, cpu, tok_s, prefill, hit_pct, accept_pct, reqs, prompt_tokens,"
        " reused, output_tokens, power_w, busy, drafts_offered, drafts_accepted, prompt_ms"
        " FROM poll WHERE t >= ? ORDER BY t",
        (now - 2 * window_s,)).fetchall()
    out = {}
    for label, lo, hi in (("recent", now - window_s, now), ("previous", now - 2 * window_s, now - window_s)):
        window = [r for r in rows if lo <= r[0] < hi]
        if len(window) < 2:
            out[label] = None
            continue
        first, last = window[0], window[-1]
        # M81-T3 (a33-17): no 1e-9 sentinel. Duplicate timestamps exist in the live
        # DB (20,303 rows / 20,285 distinct), so span can legitimately be 0; a span
        # under one sampling period cannot support any per-minute rate.
        span = last[0] - first[0]
        rate_ok = span >= SPAN_FLOOR_S

        def avg(i):
            vals = [r[i] for r in window if r[i] is not None]
            return sum(vals) / len(vals) if vals else None

        power_vals = [r[10] for r in window if r[10] is not None]
        prompt_delta = cumulative_delta(window, 7) or 0
        output_delta = cumulative_delta(window, 9) or 0
        req_count = cumulative_delta(window, 6) or 0
        reused_delta = cumulative_delta(window, 8) or 0
        tot_tok = prompt_delta + output_delta
        busy_polls = sum(1 for r in window if r[11])
        tok_s_mean = avg(2) if (req_count > 0 or tot_tok > 0) else None
        tok_s_max = max((r[2] for r in window if r[2] is not None), default=None) if (req_count > 0 or tot_tok > 0) else None
        prefill_mean = prefill_max = None
        prefill_bounded = False
        if req_count > 0 or tot_tok > 0:
            prefill_mean, prefill_max, prefill_bounded = bounded_prefill([r[3] for r in window])
        out[label] = {
            "polls": len(window),
            "span_s": round(span, 1),
            "requests": req_count,
            "total_tokens": tot_tok,
            "prompt_tokens": prompt_delta,
            "reused": reused_delta,
            "output_tokens": output_delta,
            "req_per_min": round(req_count / span * 60, 2) if rate_ok else None,
            "tok_s_mean": tok_s_mean,
            "tok_s_max": tok_s_max,
            "prefill_mean": prefill_mean,
            "prefill_max": prefill_max,
            "hit_pct_mean": avg(4),
            "accept_pct_mean": avg(5),
            # M81-T3 (a33-08): the window's OWN ratios. hit_pct/accept_pct per poll
            # are session-cumulative, so averaging them answers a different question
            # than the panel's label claims. Measured over the last 60 min on this
            # PC: mean-of-cumulatives 65.96 % vs the window's true 88.19 %.
            "hit_pct_window": window_pct(window, 8, 7),
            "accept_pct_window": window_pct(window, 13, 12),
            # M81-T3 (a33-09/a33-11): rate over the span rather than a mean of
            # instantaneous per-poll rates. tok_s_mean weights each poll equally,
            # so idle polls drag it down; these weight by what actually moved.
            "tok_s_weighted": round(output_delta / span, 2) if (rate_ok and output_delta) else None,
            # prompt_ms is a cumulative counter (new column); rows written before it
            # existed are NULL, so this stays None rather than inventing a rate.
            "prefill_weighted": (
                round(max(0.0, prompt_delta - reused_delta) / ms_delta * 1000, 2)
                if (rate_ok and (ms_delta := cumulative_delta(window, 14))) else None),
            "prefill_bounded": prefill_bounded,
            "busy_polls": busy_polls,
            "window_s": int(window_s),
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
        "SELECT t, tok_s, prefill, reqs, power_w, cpu, hit_pct, busy, vram_used, vram_total FROM poll"
        " ORDER BY t DESC LIMIT ?", (limit,)).fetchall()
    rows.reverse()
    return rows


# The connection is opened per poll (see telemetry): ThreadingHTTPServer handles each
# request in its own thread, and sqlite3 refuses to reuse a connection across threads
# (ProgrammingError on the second poll). The write counter decides when to prune; it
# stays 0 if sqlite cannot be used, and every use is guarded.
_DB_WRITES = 0


def telemetry(stats):
    """Record this poll and return (history rows, window analysis, status).

    Returns (None, None, status) if the database is unavailable, in which case the caller
    falls back to deriving series from the engine's own request records. The status is
    part of the payload so a disabled DB is visible on the dashboard, not just in the
    server's console — an empty trend is otherwise indistinguishable from a quiet engine.
    """
    global _DB_WRITES
    con = None
    try:
        con = db_init()
        _DB_WRITES += 1
        db_record(con, stats)
        db_finalize_days(con)  # before pruning, so a closed day is captured
        db_prune_days(con)     # keep the rollup to ~3 months (day rows are tiny)
        if _DB_WRITES % DB_PRUNE_EVERY == 0:
            db_prune(con)
        rows = db_rows(con)
        now_ts = datetime.now(timezone.utc).timestamp()
        cur_h_start = (int(now_ts) // 3600) * 3600
        prev_h_start = cur_h_start - 3600
        hour_cur = db_hour_aggregates(con, cur_h_start, now_ts + 1)
        hour_prev = db_hour_aggregates(con, prev_h_start, cur_h_start)
        hourly = {"current": hour_cur, "previous": hour_prev}
        return rows, db_analysis(con), {"ok": True, "rows": len(rows)}, db_daily(con), hourly
    except Exception as err:
        print(f"[telemetry] disabled: {err}")
        return None, None, {"ok": False, "error": f"{type(err).__name__}: {err}"}, None, None
    finally:
        if con is not None:
            con.close()


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
    prefill_bounded = False

    # M81-T3 (a33-10): the in-flight estimate is the source of the impossible
    # readings. The engine reports prompt_read before the prompt has finished,
    # so an early sample divides a large token count by a near-zero elapsed_s. Of
    # 20,165 stored prefill samples, all 1,114 above 3,000 tok/s came from busy
    # polls, running to 1,905,830 tok/s on a card whose decode tops out at 124.
    # So each candidate is tried in honesty order and the first physically
    # possible one wins; if any candidate was over the ceiling the value carries
    # prefill_bounded so the panel prints "· bounded". Nothing is dropped without
    # being labelled, and a bound does not leave the panel blank.
    candidates = []
    if isinstance(live, dict) and live.get("state") == "reading" and live.get("elapsed_s"):
        read = live.get("prompt_read")
        if read is None:
            read = (live.get("prompt_tokens") or 0) - (live.get("reused") or 0)
        candidates.append((max(0.0, read) / live["elapsed_s"], "live"))
    lr = prefill_rate(last_req)
    if lr is not None:
        candidates.append((lr, "last"))
    if hw.get("prefill_tok_s_mean") is not None:
        candidates.append((hw["prefill_tok_s_mean"], "engine"))
    for value, src in candidates:
        if value > PREFILL_CEILING_TOK_S:
            prefill_bounded = True
            continue
        prefill_now, prefill_source = value, src
        break

    prefill_mean = hw.get("prefill_tok_s_mean")
    if not prefill_mean and totals.get("prompt_tokens") and totals.get("prompt_ms"):
        prompt_read = (totals.get("prompt_tokens") or 0) - (totals.get("reused") or 0)
        if totals["prompt_ms"] > 0:
            prefill_mean = max(0.0, prompt_read) / (totals["prompt_ms"] / 1000)

    req_count = totals.get("requests") or 0
    prompt_latency_ms = (totals["prompt_ms"] / req_count) if (req_count > 0 and totals.get("prompt_ms")) else None
    decode_latency_ms = (totals["decode_ms"] / req_count) if (req_count > 0 and totals.get("decode_ms")) else None

    hit = (totals["reused"] / totals["prompt_tokens"]) if totals.get("prompt_tokens") else None
    offered = totals.get("drafts_offered")
    accepted = totals.get("drafts_accepted")
    accept_rate = (accepted / offered) if offered else None
    hit_pct = hit * 100 if hit is not None else None
    accept_pct = accept_rate * 100 if accept_rate is not None else None

    power = gather_power(metrics, live)

    # GPU parity with the engine's own monitor (its cards are speed/gpu/vram/temp/
    # power/pcie/cpu/disk). On this AMD HIP build the gpu_* counters come back null —
    # psutil has no GPU API on Windows — but the engine's own `vram_free_mib` is live,
    # so VRAM is recoverable here: used = the card's total - free. Everything the panel
    # shows from a counter it cannot read is labelled (derived / modelled / rated) so no
    # figure is ever presented as a driver measurement.
    gpu_hist = gather_history() or {}
    vram_free = eng.get("vram_free_mib")
    vram_derived = hw.get("gpu_mem_used") is None and vram_free is not None
    gpu_mem_used = hw.get("gpu_mem_used")
    gpu_mem_total = hw.get("gpu_mem_total")
    # The card's real size, in trust order: what the OS registry reports (64-bit, live adapter),
    # then the engine's figure (wrong on a PC with a stale class entry — see HOST_GPU), then the
    # rated constant. WMI's AdapterRAM is never used: it is a UInt32 cap (~4 GB on a 24 GB card).
    vram_total_mib = HOST_GPU["vram_mib"] or static.get("gpu_vram_total_mib") or VRAM_TOTAL_MIB
    if vram_derived:
        gpu_mem_used = max(0, vram_total_mib - int(vram_free))
        gpu_mem_total = vram_total_mib
    gpu = {
        # Utilisation has no counter on this driver, so the modelled activity from the
        # power model fills the gauge — labelled modelled so it reads as an estimate.
        "util_pct": hw.get("gpu_util") if hw.get("gpu_util") is not None
                   else (power or {}).get("activity"),
        "util_source": "measured" if hw.get("gpu_util") is not None else (
            "modelled" if (power or {}).get("activity") is not None else None),
        "mem_used": gpu_mem_used,
        "mem_total": gpu_mem_total,
        "mem_pct": (gpu_mem_used / gpu_mem_total * 100)
                   if (gpu_mem_used is not None and gpu_mem_total) else None,
        "mem_source": "measured" if hw.get("gpu_mem_used") is not None else (
            "derived" if vram_derived else None),
        "vram_free_mib": vram_free,
        "temp_c": hw.get("gpu_temp"),
        "power_w": hw.get("gpu_power"),
        "power_limit_w": hw.get("gpu_power_limit"),
        "power_source": "measured" if hw.get("gpu_power") is not None else (
            "modelled" if (power or {}).get("gpu_w") is not None else None),
        "pcie_rx_mb": hw.get("gpu_pcie_rx_mb"),
        "pcie_gen": hw.get("gpu_pcie_gen"),
        "pcie_gen_max": hw.get("gpu_pcie_gen_max"),
        "pcie_width": hw.get("gpu_pcie_width"),
        # M81-T1 (audit-33 a33-01): the OS wins over the engine. The engine's name comes from
        # indexing the display device class in class order, which on a PC with a leftover driver
        # entry for a removed card names the wrong adapter (here: an RX 6800 XT ahead of the
        # installed RX 7900 XTX). "measured" is dropped for this field — nothing measured it.
        "name": HOST_GPU["name"] or static.get("gpu_name")
                or (POWER_MODEL["gpu_name"] if static.get("gpu_count") else None),
        "count": static.get("gpu_count"),
        "name_source": HOST_GPU["source"] if HOST_GPU["name"] else (
            "engine" if static.get("gpu_name") else ("rated" if static.get("gpu_count") else None)),
        # A disagreement between the OS and the engine is information, not noise: show both.
        "name_conflict": (static.get("gpu_name")
                          if HOST_GPU["name"] and static.get("gpu_name")
                          and static.get("gpu_name") != HOST_GPU["name"] else None),
        "vram_total_mib_source": "os" if HOST_GPU["vram_mib"] else (
            "engine" if static.get("gpu_vram_total_mib") else (
                "rated" if vram_derived else None)),
        # True when the panel has any gpu_* series to draw, including the VRAM series
        # derived from the engine's live vram_free_mib.
        "history_available": any(k in gpu_hist for k in (
            "gpu_util", "gpu_temp", "gpu_power", "gpu_mem_used")),
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
            "ram_pct": (hw.get("ram_used") / hw["ram_total"] * 100) if (hw.get("ram_total") and hw.get("ram_used") is not None) else None,
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
            # M81-T1 (a33-06): this used to pass the engine's raw value with no fallback, which is
            # how the Hardware panel could print "1 GPU(s)" and now how it would print the wrong
            # card. Same resolution order as the gpu object, so the two panels can never disagree.
            "gpu_name": gpu["name"],
            "gpu_name_source": gpu["name_source"],
            "gpu_count": static.get("gpu_count"),
            "cpu_name": static.get("cpu_name"),
            "cores": static.get("cores"),
            "threads": static.get("threads"),
        },
        "throughput": {
            "now": tok_now,
            "mean": tok_mean,
            "peak": None,
            "prefill": prefill_now,
            "prefill_bounded": prefill_bounded,
            "prefill_mean": prefill_mean,
            "prefill_peak": None,
            "prefill_source": prefill_source,
            "source": tok_source,
            "prompt_latency_ms": prompt_latency_ms,
            "decode_latency_ms": decode_latency_ms,
            "req_per_min": None,
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
    rows, analysis, telemetry_status, daily, hourly = telemetry(stats)
    stats["telemetry"] = telemetry_status
    stats["daily"] = daily or []
    stats["periods"] = db_periods(stats["daily"], analysis=analysis, requests=stats.get("requests"), hourly=hourly)
    if analysis and analysis.get("recent"):
        rec = analysis["recent"]
        stats["throughput"]["peak"] = rec.get("tok_s_max")
        stats["throughput"]["prefill_peak"] = rec.get("prefill_max")
        stats["throughput"]["recent_mean"] = rec.get("tok_s_mean")
        stats["throughput"]["recent_prefill_mean"] = rec.get("prefill_mean")
        stats["throughput"]["req_per_min"] = rec.get("req_per_min")
        # M81-T3 (a33-09): name the window each figure describes, because three
        # different windows are on screen at once and their labels used to lie.
        stats["throughput"]["mean_window"] = "session"
        stats["throughput"]["peak_window"] = f"last {int((rec.get('window_s') or DB_WINDOW_S) / 60)} min"
        if rec.get("prefill_bounded"):
            stats["throughput"]["prefill_bounded"] = True
    if rows:
        # M81-T3 (a33-10): the prefill sparkline scales by max(samples), so one
        # impossible historical sample (up to 1,905,830 tok/s) flattens every real
        # value in the chart. Rows written before the source bound keep their raw
        # value in the DB on purpose, so the published series is bounded here and
        # the panel is told via prefill_bounded. Over-ceiling samples become holes
        # in the curve (drawSpark skips nulls) rather than a fake axis.
        series_prefill = [(None if v is not None and v > PREFILL_CEILING_TOK_S else v) for v in (r[2] for r in rows)]
        # Count the over-ceiling samples from the raw values: a null in the series
        # is an idle poll with no prefill at all, not a bounded one.
        n_bounded = sum(1 for v in (r[2] for r in rows) if v is not None and v > PREFILL_CEILING_TOK_S)
        stats["history"] = {
            "tok_s": [r[1] for r in rows],
            "prefill": series_prefill,
            "power_w": [r[4] for r in rows],
            "cpu": [r[5] for r in rows],
            "hit_pct": [r[6] for r in rows],
        }
        if n_bounded or prefill_bounded:
            stats["history"]["prefill_bounded"] = True
            stats["history"]["prefill_bounded_n"] = n_bounded
            stats["throughput"]["prefill_bounded"] = True
        stats["history"]["requests"] = bucket_db_requests(
            [(r[0], r[3]) for r in rows]) or bucket_requests(metrics) or []
        # The engine's own gpu_* series pass through when they carry values, so a
        # build that reports them (or NVIDIA's NVML) gets a sparkline for free.
        for key in ("gpu_util", "gpu_temp", "gpu_mem_used", "gpu_pcie_rx_mb"):
            if gpu.get("history_available") and key in gpu_hist:
                stats["history"][key] = gpu_hist[key]
        # VRAM is the one GPU reading this driver can supply, and its history lives in
        # our own poll rows (the engine keeps no vram_free_mib series), so derive the
        # percentage here rather than waiting for a gpu_* series that never arrives.
        vram_pct = [
            (r[8] / (r[9] or VRAM_TOTAL_MIB) * 100) if r[8] is not None else None
            for r in rows
        ]
        if any(v is not None for v in vram_pct):
            stats["history"]["vram_pct"] = vram_pct
            gpu["history_available"] = True
    else:
        stats["history"] = {}
        stats["history"]["requests"] = bucket_requests(metrics) or []
    stats["history"].setdefault("prefill", bucket_requests(metrics, extract=prefill_rate) or [])
    stats["history_bucket_s"] = 1800 / 24
    stats["analysis"] = analysis
    return stats


# ---------- HTTP server ----------
def build_export(fmt="json"):
    """Open a fresh connection and serialize the retained history for the export routes.

    Opened per request (not shared across threads) for the same cross-thread reason as
    telemetry(). Returns the body string, or None if the DB is unavailable so the caller
    can fall through to a 404 rather than crash.
    """
    try:
        con = db_init()
    except Exception:
        return None
    try:
        return db_export(con, fmt)
    except Exception as err:
        print(f"[export] disabled: {err}")
        return None
    finally:
        con.close()


def build_timeseries(range_str="1h"):
    """Open DB connection, query timeseries aggregation, and return JSON string."""
    try:
        con = db_init()
    except Exception:
        return None
    try:
        data = db_timeseries(con, range_str)
        return json.dumps(data) if data is not None else None
    except Exception as err:
        print(f"[timeseries] query error: {err}")
        return None
    finally:
        con.close()


class _Server(http.server.ThreadingHTTPServer):
    # On Windows, the default SO_REUSEADDR lets a second process bind the same port silently.
    # With reuse off, a duplicate launch fails with WinError 10048 instead. Side effect: a quick restart can
    # fail while the old socket is in TIME_WAIT; the supervisor retries with backoff.
    allow_reuse_address = False


def serve(port):
    import urllib.parse
    from functools import partial

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            path = parsed.path.rstrip("/")
            if path == "/api/stats":
                body = json.dumps(build_stats()).encode()
                ctype = "application/json"
            elif path == "/api/export" or path == "/api/export.csv":
                payload = build_export("csv" if path.endswith(".csv") else "json")
                if payload is None:
                    super().do_GET()
                    return
                body = payload.encode()
                ctype = "text/csv" if path.endswith(".csv") else "application/json"
            elif path == "/api/timeseries":
                qs = urllib.parse.parse_qs(parsed.query)
                range_str = qs.get("range", ["1h"])[0]
                payload = build_timeseries(range_str)
                if payload is None:
                    self.send_error(404, "Timeseries unavailable")
                    return
                body = payload.encode()
                ctype = "application/json"
            elif path in ("/api/usage", "/api/usage/sessions"):
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
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_request(self, code="-", size="-"):
            # Only 4xx/5xx access lines are logged: the 5 s dashboard poll writes ~3 MB/day of 2xx lines.
            # Compare as a number; str(HTTPStatus) is only the number from Python 3.11 on.
            try:
                status = int(code)
            except (TypeError, ValueError):
                return
            if status >= 400:
                super().log_request(code, size)

    root = str(Path(__file__).resolve().parent)
    handler = partial(_Handler, directory=root)
    threading.Thread(target=usage_thread, name="usage-ingest", daemon=True).start()
    httpd = _Server(("127.0.0.1", port), handler)
    httpd.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT_DEFAULT
    print(f"Serving LLM monitor + /api/stats on http://localhost:{port} (Ctrl+C to stop)")
    serve(port)
