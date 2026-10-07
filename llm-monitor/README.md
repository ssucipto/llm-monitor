# Local LLM Monitor

A live dashboard for the local LLM engine running on this machine. It is not the
homelab dashboard — it monitors whatever engine currently owns **port 8080**:
either **Strata Coder** or **Vulkan llama.cpp** (Qwen3.8-27B), the two engines the
Hermes workspace switches between.

## Files

| File         | Purpose                                                            |
|--------------|--------------------------------------------------------------------|
| `index.html` | Page structure — element IDs are the API contract                  |
| `style.css`  | Dark theme with automatic light mode (`light-dark()` palette)      |
| `app.js`     | Fetches `/api/stats`, renders, auto-refreshes every 5 s            |
| `server.py`  | Static server + `/api/stats` endpoint (Python stdlib)              |

## Run it

```bash
cd llm-monitor
python server.py          # default port 8090; pass one to change: python server.py 8081
```

Then open **http://localhost:8090**. The header badge reads **Live** when the
backend can reach the engine. If the engine on port 8080 is down, the badge flips
to **Stale** and the page keeps its last rendered state (unlike the homelab
template, there is no simulation fallback — a monitor should show truth, not
fabricated numbers).

## What it monitors

The backend reads the engine's own HTTP endpoints plus the Hermes workspace state
files and log tails. Sections:

- **Header identity** — the engine that owns the port and the model it is serving,
  set large and bold in the top bar with a monogram mark (stacked layers for Strata,
  a V over a ring for Vulkan), colored with the engine's own accent. The prefill
  speed reading lives here too, with a compact gradient speed meter pinned at the
  top so it stays visible while the page scrolls.
- **At a glance** — the hero band under the header: decode tok/s, model state (Reading /
  Generating / Queued / Idle), watts, % context (two decimals), and % cache hit.
- **Engine** — which service owns the port (Strata / Vulkan), model, build, loaded
  state, model path. From `/health`, `/v1/models`, `/props`.
- **Live inference** — current state (idle/processing), phase, prompt/generated
  tokens, elapsed, queued. From `/metrics.live` (Strata) or `/slots` (llama).
- **Context window** — used/max tokens with a gauge.
- **Throughput** — current + mean tok/s, prefill rate, and a self-redrawing
  sparkline of the engine's own `history.tok_s` array.
- **Requests activity** — a second sparkline of requests-per-interval. The engine
  keeps no request-count history, so the backend buckets the request records' own
  timestamps (or the SQLite counter) into fixed intervals; a flat stretch is an
  idle engine, which is the point of the chart.
- **Power** — energy the engine is drawing. The engine schema carries `gpu_power` /
  `gpu_power_limit` (its own monitor draws a Power card from them), but on this AMD
  HIP build they come back null — the driver exposes no userspace power counter, unlike
  NVIDIA's NVML. So the panel reports the source explicitly (`measured` / `modelled`)
  and never dresses a modelled figure up as a measurement. The model scales the rated
  envelope (RX 7900 XTX + Ryzen 5600X) by engine activity: prefill is dense GEMM (hot),
  decode streams weights (bandwidth-bound, well under peak), idle is the card parked.
- **GPU** — parity with the engine's own monitor's gpu/vram/temp/power/pcie cards:
  utilisation, VRAM used/total, temperature gauges, plus power, PCIe RX and device
  identity. On a driver with no userspace counter (this AMD HIP build) every reading is
  null and the panel says so in words rather than drawing gauges at zero.
- **Hardware** — CPU %, RAM used/total, VRAM free, disk read/write, GPU and CPU
  identity. From `/metrics.hardware`.
- **Cache** — prompt-token reuse hit-rate, KV cache type, expert slots/cache,
  conversation cache. From `/metrics`.
- **Speculative decode** — MTP draft accept-rate, drafts offered/accepted.
- **Requests** — recent generations (duration, finish reason, prompt/read/output
  tokens, tok/s, hit-rate) from `/metrics.requests`.
- **Telemetry** — windowed analysis from the SQLite history: requests, tok/s mean/peak,
  prefill mean, hit/accept rate, idle %, energy, and a trend vs the prior window. A
  lifetime **session-totals** line (since / requests / prompt / output from `totals`) sits
  alongside it as a look-back that stays useful before the window has enough samples.
- **Endpoints** — a compact footer chip marks which engine endpoints (`health`/`metrics`/
  `slots`/`models`/`status`) the backend reached this poll, so a partial outage is visible
  without opening the console.
- **Switch** — `engine-active.txt`, the active llama profile, owner, PID, and the
  full profile inventory with the active one highlighted.
- **System log** — merged tails of `watchdog.log`, `autostart.log`, `server.log.err`,
  collapsed with `hidden="until-found"`.
- **History** — daily/weekly/monthly rollups from a tiny per-day table in the SQLite
  side channel, with period comparisons (today vs yesterday, this week vs previous,
  this month vs previous, each with a % delta). A **day scrubber** lets you slide a
  marker (or click) across recorded days to inspect any past day's requests, tok/s,
  energy, hit-rate and idle %, with its delta vs the day before. Because the poll
  table is bounded to ~28h, ended days are frozen into the rollup at each day
  boundary before pruning can drop them, so weekly/monthly history survives uptime
  the raw polls cannot.

## Drag-and-drop layout

Any panel can be dragged by its heading and dropped anywhere in the card masonry
or the history band — document order drives both, so a drop reorders the DOM and
the latest positions are remembered automatically in `localStorage` between reloads.
While dragging, a **dashed slot** shows exactly where the panel will land and the
other panels part around it, so the drop point is unambiguous before you release;
the dragged panel eases toward the pointer for a fluid follow, and a card can land
in the band or vice versa. The footer **Save layout** button commits the arrangement
explicitly and **Reset layout** restores the default priority order (`?reset=1` in
the URL clears the save too). Touch is excluded (so page scrolling is never hijacked),
and the hero band is fixed.

## `/api/stats` shape

```json
{
  "engine":   {"active","service","model","model_alias","max_context","loaded","version","images","api_key","model_path","build_info","port_open"},
  "status":   {"state","phase","queued","busy","activity"},
  "live":     {"state","queued","phase","prompt_tokens","prompt_read","prompt_total","generated","max_tokens","elapsed_s","tok_s","tok_s_mean","prefill_tok_s_mean"},
  "context":  {"used","max","pct","slots","source"},
  "cache":    {"kv_type","kv_resident","expert_slots","expert_cache_mib","conversation_cache","hit_rate","hit_pct","reused_tokens","prompt_tokens"},
  "spec":     {"spec","mtp_max","lookup","drafts_offered","drafts_accepted","accept_rate","accept_pct"},
  "hardware": {"cpu_pct","ram_used","ram_total","ram_pct","vram_free_mib","disk_read_mb","disk_write_mb","tok_s","tok_s_mean","gpu_util","gpu_mem_used","gpu_mem_total","gpu_temp","gpu_power","gpu_power_limit","gpu_pcie_rx_mb","gpu_pcie_gen","gpu_pcie_gen_max","gpu_pcie_width","gpu_name","gpu_count","cpu_name","cores","threads"},
  "throughput":{"now","mean","prefill","prefill_source","source"},
  "power":    {"total_w","gpu_w","cpu_w","gpu_measured_w","gpu_limit_w","peak_w","pct_of_peak","source","model"},
  "gpu":      {"util_pct","mem_used","mem_total","mem_pct","temp_c","power_w","power_limit_w","pcie_rx_mb","pcie_gen","pcie_gen_max","pcie_width","name","count","history_available"},
  "config":   {"pool_workers","pcie_frac","spec","spec_min_p","mtp_max","lookup","expert_slots","expert_slots_primary","expert_cache_mib","expert_cache_primary_mib","arena_mib","cvec","vram_elastic","conversation_cache_slots","conversation_cache_min_free_mib","tail_role_token"},
  "engine_history": {"cpu":[...],"ram_used":[...],"tok_s":[...],"disk_read_mb":[...],"gpu_util":[...],"gpu_power":[...], ...},
  "history":  {"tok_s":[...],"prefill":[...],"requests":[...],"power_w":[...],"cpu":[...],"hit_pct":[...],"gpu_util":[...]?},
  "history_bucket_s": 75,
  "requests": [{"duration_s","finish","prompt_tokens","prompt_read","reused","output_tokens","prompt_ms","decode_ms","decode_tok_s","hit_rate","pcie_share","drafts_offered","drafts_accepted","engine_generated","file_mb","ram_blobs","file_blobs","time"}],
  "requests_kept": 272,
  "totals":   {"since","requests","prompt_tokens","reused","output_tokens","prompt_ms","decode_ms","drafts_offered","drafts_accepted"},
  "analysis": {"recent":{"polls","span_s","requests","prompt_tokens","reused","output_tokens","req_per_min","tok_s_mean","tok_s_max","prefill_mean","hit_pct_mean","accept_pct_mean","power_w_mean","energy_wh","idle_pct"},"previous":{...}},
  "telemetry": {"ok":true,"rows":N} | {"ok":false,"error":"OperationalError: ..."},
  "daily":     [{"d","date","polls","requests","prompt_tokens","reused","output_tokens","tok_s_mean","tok_s_max","prefill_mean","hit_mean","accept_mean","power_mean","energy_wh","idle_pct","hours":[24]}],
  "periods":   {"day":{"current":{...},"previous":{...},"current_label","previous_label"},"week":{...},"month":{...}},
  "switch":   {"engine_active","llama_active_profile","llama_last_profile","owner","pid","profiles"},
  "log":      [{"level","iso","msg","source"}],
  "endpoints":{"health","metrics","slots","models","status"},
  "fetched_at": "..."
}
```

`history` is the SQLite-backed series (drawn by the sparklines); `engine_history` is the
engine's own `history` arrays passed through unchanged. `requests` in `history` is always
per-interval, never the engine's cumulative counter. `telemetry` reports whether the SQLite
side channel is live — when it is not, the trends and the Telemetry panel say so rather than
looking like a quiet engine.

## Configuration

All sources are at the top of `server.py`:

- `ENGINE_URL` — the engine to monitor (default `http://127.0.0.1:8080`).
- `WORKSPACE` — the Hermes hub root (default `C:\Project\hermes`).
- `LOG_FILES` / `STATE_FILES` — the log and state-file paths it tails/reads.
- `LLAMA_PROFILES` — the profile inventory shown in the Switch panel.

To monitor a different machine or port, change those constants. The front end
stays unchanged because the response shape is the contract.

## Animation

Same motion system as the homelab template, reused here: tweened gauge numbers,
a self-redrawing sparkline (`pathLength="1"` + unit-free dash maths), a countdown
ring on the badge (`@property --sweep`, duration from `--poll-ms` set by `app.js`
from `REFRESH_MS`), staggered panel/row/log entrance via a `--i` index, and an
ambient backdrop. All informational, so the `prefers-reduced-motion: reduce`
block at the **bottom** of `style.css` switches it off without losing any reading.
