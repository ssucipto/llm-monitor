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
| `server.py`  | Static server + the `/api/*` JSON endpoints (Python stdlib)        |

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

## Run it as a supervised service

The dashboard runs under a supervisor: if `server.py` dies, it is restarted with
backoff (5 s doubling to 60 s), and every start and exit is logged. A duplicate
launch fails with a bind error instead of silently sharing the port. The server runs
inside the supervisor's kill-on-close job, so when the supervisor ends (stopped task,
killed process, stop request) its server ends with it: no orphans.

| File                     | Purpose |
|--------------------------|---------------------------------------------------------------|
| `service-supervisor.ps1` | Runs `server.py` in the foreground, restarts it with backoff, logs lifecycle to `service-<port>.log`, rotates logs over 5 MB to `.1`, writes `service-<port>.state.json`, honours `stop-<port>.request`, takes over an orphaned server of ours. |
| `install-service.ps1`    | Registers one logon task (`LLMMonitor`) that runs the supervisor, no execution time limit. With `-WithBoot` it also registers `LLMMonitorBoot` (system startup, S4U, no stored password). `-WithBoot` needs an elevated native shell. |
| `install-service.bat`    | Thin wrapper: runs `install-service.ps1` with the same arguments. |
| `restart-llm-monitor.ps1`| Restarts the dashboard on any port; never stops anything by name (details below). |

Run the installer **once** from a normal Windows shell (double-click, `cmd /c`, or
PowerShell, not from Git-Bash/MSYS, which cannot register tasks):

```bat
llm-monitor\install-service.bat
REM or with the boot trigger (elevated native shell):
powershell -NoProfile -ExecutionPolicy Bypass -File llm-monitor\install-service.ps1 -WithBoot
```

Start it now: `Start-ScheduledTask -TaskName LLMMonitor`
Stop it: `Stop-ScheduledTask -TaskName LLMMonitor` (then `Disable-ScheduledTask` to keep it off).
Restart: `restart-llm-monitor.ps1` (or `-Port <n>` for a test port; without a task for that port it starts a supervisor directly).

Files in `%LOCALAPPDATA%\LLMMonitor` (per port):

| File | Content |
|---|---|
| `service-<port>.log` | Lifecycle: `supervisor:` lines (start, server start with PIDs, exit, restart, rotation, end) and `restart:` lines from the restart script |
| `service-<port>.err.log` | Server errors and 4xx/5xx access lines only (2xx lines are not logged) |
| `service-<port>.out.log` | Server stdout |
| `service-<port>.state.json` | Supervisor, wrapper and server PIDs, start times, heartbeat (every 10 s) |
| `run-server-<port>.cmd` | The wrapper the supervisor runs |

`service.log`, `service.err.log` and `service.out.log` (no port) are from the old launcher and are no longer written.

**How the restart script works.** It refuses at once if a process that is not this
dashboard owns the port. Otherwise it writes `stop-<port>.request`; every supervisor of
that port stops its own server and logs `supervisor end (stop requested, exit 0)`. Then it
stops both tasks, stops any remaining supervisor or server of ours by PID (after a full-path
command-line match), and starts `LLMMonitor` again.

**Boot decision (T6): option B.** The dashboard also starts at system startup via the
S4U boot task, with no stored password. That chain runs in session 0: from the desktop its
processes show no command line and cannot be stopped, so the restart script and the gate
identify it through the state file and stop it through the stop request. At sign-in, the
logon task's supervisor sees the attested server and exits (`already served`). The S4U
context was tested without a reboot (`Start-ScheduledTask LLMMonitorBoot`, 2026-10-17); the
startup trigger itself still needs a real reboot test (carryover a25-02). To revert to
logon-only, run the installer without `-WithBoot`.

## What it monitors

The backend reads the engine's own HTTP endpoints plus the Hermes workspace state
files and log tails. Sections:

- **Header identity** — the engine that owns the port and the model it is serving,
  set large and bold in the top bar with a monogram mark (stacked layers for Strata,
  a V over a ring for Vulkan), colored with the engine's own accent. The prefill
  speed reading lives here too, with a full-width gradient speed gauge pinned to the
  bottom edge of the sticky header (scale ticks every 25% and a knob that slides to
  the current reading) so it stays visible while the page scrolls.
- **At a glance** — the KPI strip in the sticky header: decode tok/s, model state (Reading /
  Generating / Queued / Idle), watts, % context (two decimals), and % cache hit.
- **Engine** — which service owns the port (Strata / Vulkan), model, build, loaded
  state, model path. From `/health`, `/v1/models`, `/props`.
- **Live inference** — current state (idle/processing), phase, prompt/generated
  tokens, elapsed, queued. From `/metrics.live` (Strata) or `/slots` (llama).
- **Context window** — used/max tokens with a gauge.
- **Throughput** — current + mean tok/s, prefill rate, and a self-redrawing
  sparkline of the engine's own `history.tok_s` array. The current reading is the
  **decode** speed (labeled `decode tok/s` in the header chip and suffixed `decode`
  on the panel's big number, so the two never disagree).
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
  identity. On this AMD HIP build the driver exposes no `gpu_*` counters, but the
  readings split by what is honestly recoverable: **VRAM is derived** from the engine's
  live `vram_free_mib` against the fixed card total (RX 7900 XTX = 24 GB), so the panel
  shows real used/total tagged `derived`; **utilisation and power are modelled** from the
  same engine-activity table that drives the Power card (prefill hot, decode bandwidth-bound,
  idle parked), tagged `modelled`; the **device name falls back to the rated card** since
  the machine is fixed. Temperature and PCIe RX have no counter and no honest proxy, so
  they stay `--` and the panel says so in words rather than dressing a guess as a reading.
  Every figure carries its source (`measured` / `derived` / `modelled` / `rated`).
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
- **Timeseries chart** — an interactive SVG chart over eight windows: `15m` / `1h` /
  `3h` / `6h` / `24h` and `7d` / `30d` / `90d`, in four metric tabs (All Combined,
  Tokens/s, Token Usage, Requests; the prefill series rides along in All Combined).
  Backed by `GET /api/timeseries?range=<r>` — which also accepts `12h` — bucketing the
  SQLite history with counter-reset safety and returning `{range, span_s, bucket_s,
  n_buckets, empty_buckets, buckets:[{t,time,label,samples,requests,prompt_tokens,
  reused,output_tokens,total_tokens,tok_s_mean,tok_s_max,prefill_mean,prefill_max,
  prefill_bounded}], summary}`. A bucket with `samples: 0` is a gap in observation, not
  an idle engine, and the chart draws it that way. An unknown range is HTTP 404; if the
  endpoint fails, the panel rebuilds its buckets from the `/api/stats` payload instead
  of going blank.

## Layout

The panels are laid out by a **masonry engine**: a CSS grid with 4 px track rows where
`app.js` gives each card a row span computed from its own height. Cards pack flush in
each column with no blank gutters, the column count follows the window width
(`minmax(300px, 1fr)`, collapsing to one column at or below 900 px), and the wide panels
(requests, charts, history) plus the whole **Detail** region span the full width. The
layout is recomputed on load, on every data render, when a `<details>` opens or closes,
when a card is resized, when you switch between the Full and Compact views, and after
each drag.

## Drag-and-drop layout

Any panel can be dragged by its heading and dropped anywhere in the tile grid or the
collapsible **Detail** region at the bottom — document order drives both, so a drop
reorders the DOM and the latest positions are remembered automatically in `localStorage`
between reloads (layouts saved by the older two-container layout migrate on load).
While dragging, a **dashed slot** shows exactly where the panel will land and the
other panels part around it, so the drop point is unambiguous before you release;
the dragged panel eases toward the pointer for a fluid follow, and a card can land
in the Detail region or vice versa. The footer **Save layout** button commits the arrangement
explicitly and **Reset layout** restores the default priority order (`?reset=1` in
the URL clears the save too). Touch is excluded (so page scrolling is never hijacked),
and the KPI strip is fixed.

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
  "gpu":      {"util_pct","util_source","mem_used","mem_total","mem_pct","mem_source","vram_free_mib","temp_c","power_w","power_limit_w","power_source","pcie_rx_mb","pcie_gen","pcie_gen_max","pcie_width","name","name_source","count","history_available"},
  "config":   {"pool_workers","pcie_frac","spec","spec_min_p","mtp_max","lookup","expert_slots","expert_slots_primary","expert_cache_mib","expert_cache_primary_mib","arena_mib","cvec","vram_elastic","conversation_cache_slots","conversation_cache_min_free_mib","tail_role_token"},
  "engine_history": {"cpu":[...],"ram_used":[...],"tok_s":[...],"disk_read_mb":[...],"gpu_util":[...],"gpu_power":[...], ...},
  "history":  {"tok_s":[...],"prefill":[...],"requests":[...],"power_w":[...],"cpu":[...],"hit_pct":[...],"gpu_util":[...]?,"vram_pct":[...]?},
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

## Export

Two endpoints ship the collected telemetry to an outside reviewer (agent, dogfooding,
troubleshooting) with field names and provenance so the data is usable, not garbage:

- `GET /api/export` — JSON: `{poll_rows, days, meta:{generated, window_days, poll_cols}}`.
  `poll_rows` are named-keyed (never positional), `poll_cols` lists the schema so a reader
  can map columns. Retention is bounded to ~90 days (`DB_DAILY_MAX`), so the export window
  never exceeds ~3 months of data.
- `GET /api/export.csv` — plain CSV (header row + rows) for spreadsheet/agent ingestion.

The poll row now carries the richer dogfooding fields `drafts_offered`, `drafts_accepted`,
and `pcie_share` (read from the same `/metrics` dict the poll already reads — zero extra
engine cost), so speculative-decode and PCIe-share signals are available for analysis.

## Usage ledger

Token usage of the orchestrator (Claude Code) and of the local executor (Hermes running Strata), per time window, repo and
session, for the Homelab delegation protocol (milestone M78; Homelab ADR-022).

- **What is read:** `%USERPROFILE%\.claude\projects\**\*.jsonl` (only the `assistant` lines' ids, timestamps, model, working
  folder and the four token counts) and `%LOCALAPPDATA%\hermes\state.db` (read-only: per-session model usage and the repo folder).
- **What is never read or stored:** message text, titles, prompts, tool output.
- **Where:** `llm-monitor/usage.sqlite3` (gitignored, its own file beside the telemetry DB). A thread ingests every 60 s, and
  every `/api/usage` call catches up first (at most 10 s; `partial: true` if it ran out).
- **API:** `GET /api/usage?from=ISO&to=ISO[&repo=PATH][&session=ID]` (totals, a cost-weighted unit, source status) and
  `GET /api/usage/sessions?...` (one row per session and role). A bad window is HTTP 400; a missing source is `null`, never 0.
- **Executor models:** Hermes rows count as executor usage only for the models in `LLM_MONITOR_EXECUTOR_MODELS`
  (comma-separated; default `strata-iq3_s,qwen3.8-flash-next-iq3_s`); `/api/usage` names them in `executor_models`.
- **Tests:** `py -3.12 tests/usage/run-tests.py` (synthetic data only; `run-e2e-tests.sh` runs it; CI: `usage-tests.yml`).

## Configuration

All sources are at the top of `server.py`:

- `ENGINE_URL` — the engine to monitor (default `http://127.0.0.1:8080`).
- `WORKSPACE` — the Hermes hub root (default `C:\Project\hermes`).
- `LOG_FILES` / `STATE_FILES` — the log and state-file paths it tails/reads.
- `LLAMA_PROFILES` — the profile inventory shown in the Switch panel.

To monitor a different machine or port, change those constants. The front end
stays unchanged because the response shape is the contract.

### Test overrides (environment)

The suites in `agent/tests/ui/` and `tests/` start this same `server.py`, so its files
and its upstream are overridable by environment variable (one more, `LLM_MONITOR_EXECUTOR_MODELS`,
is documented under **Usage ledger**). They exist for tests; leave them unset
to run the dashboard normally.

| Variable | Replaces |
| --- | --- |
| `LLM_MONITOR_DB` | `telemetry.sqlite3`. Without it every `/api/stats` a test page requests appends a poll row to the real history (measured: 20,280 → 20,282 rows for one request). |
| `LLM_MONITOR_USAGE_DB` | `usage.sqlite3` |
| `LLM_MONITOR_CLAUDE_ROOT` / `LLM_MONITOR_HERMES_DB` | the two ledger sources |
| `LLM_MONITOR_FIXTURE` | the live engine on `ENGINE_URL`. Points at a JSON object of `{endpoint path: response}` — see `agent/tests/ui/fixtures/engine.json`. Only the engine's HTTP answers are replaced; workspace state files, log tails and our own SQLite history stay real. A path the fixture does not list reads as "endpoint unreachable", so a fixture may be partial. An unreadable fixture **stops startup** rather than falling back to the live engine, because testing the live engine by accident is the defect this exists to remove. |

Run them with `py -3.12 agent/tests/ui/run-tests.py` (browser + static),
`py -3.12 tests/telemetry/run-tests.py` and `py -3.12 tests/usage/run-tests.py`;
CI runs all three (`usage-tests.yml`).

## Animation

Same motion system as the homelab template, reused here: tweened gauge numbers,
a self-redrawing sparkline (`pathLength="1"` + unit-free dash maths), a countdown
ring on the badge (`@property --sweep`, duration from `--poll-ms` set by `app.js`
from `REFRESH_MS`), staggered panel/row/log entrance via a `--i` index, and an
ambient backdrop. All informational, so the `prefers-reduced-motion: reduce`
block at the **bottom** of `style.css` switches it off without losing any reading.

## Updating ACP

`/acp-version-update` refreshes `AGENTS.md` and `CLAUDE.md`. Local rules added to those files are lost on update. After every update, check that the `Local rules` section of `AGENTS.md` still exists, and re-add it from the local rule skill if not. Files under `agent/skills/local.*` and `agent/routing/taxonomy.yml` are preserved.
