# Changelog

All notable changes to the **llm-monitor** dashboard are documented here.
Version numbers track the project (not the ACP Enhanced framework, which is
versioned separately at 6.40.0). This project follows [Semantic Versioning](https://semver.org).

## [0.3.0] - 2026-10-27

### Changed
- **The dashboard leads with what the model is doing.** The default tile order is now engine performance (live, throughput, context, cache, speculative decode, telemetry), then activity (charts, requests, history, usage), then hardware (gpu, power, hardware); engine config, engine switch and the system log stay a collapsed Reference region. Cache and speculative decode moved out of that region because they are engine readings. The Requests table folds in place inside its own panel. A saved layout from before this release is replaced by the new defaults and the page says so, with Dismiss and Reset beside it.
- **The GPU panel names the right card.** The engine indexes the Windows display class in class order, so on a PC with a leftover driver entry for a removed card it named an RX 6800 XT on a machine holding an RX 7900 XTX. `server.py` now resolves the name and VRAM from the registry itself (stdlib `winreg`, guarded so Linux CI still imports the file), labels the source (`via OS` / `via engine` / `rated`) and shows a disagreement instead of picking silently. WMI's `AdapterRAM` is never used: it is a UInt32 cap.
- **A missing reading no longer looks like a zero.** `setGauge` renders null as `--` with a striped indeterminate meter rather than `0%`; the GPU Temp row had been claiming a definite 0% on a driver that exposes no temperature counter. Every gauge now names where its number came from (measured / derived / modelled / rated).
- **Telemetry rates mean what their labels claim.** Hit and accept rates are computed from the window's own totals rather than averaged over session-cumulative per-poll ratios (on this PC: 88.19% shown as 65.96%). Prefill samples above a 5,000 tok/s ceiling are excluded and the panel is told via `prefill_bounded`, because one impossible historical sample (1,905,830 tok/s) flattened every real value in the chart. Each figure states the window it covers.
- **The Performance & Token chart became readable.** The y-axis belongs to one metric with its unit printed, buckets with no samples are marked as gaps instead of drawn as zero, the legend matches the plotted series, and each range tab labels the span it shows.
- **History is a labelled bar chart** with a day scrubber and keyboard access, replacing a 100x30 squiggle with no axis and no ticks. Calendar-period rows name their UTC alignment.
- **The header says what it measures.** The duplicated decode tok/s cell is gone, the prefill gauge's scale is printed next to it (`gauge to 1,250`) and derived from the series instead of a hardcoded 2000 tok/s this engine never approaches, and the header now carries engine uptime, the age of the numbers on screen and the answering build string.
- Payload keys are **additive only** (this milestone deliberately lifts the M79/M80 "zero /api changes" rule): `gpu.name_source`, `gpu.name_conflict`, `hardware.gpu_name_source`, `power.rated_w`, per-bucket `samples`, `n_buckets`/`empty_buckets`, window-weighted rate keys and `prefill_bounded`.

### Added
- `LLM_MONITOR_DB` / `LLM_MONITOR_FIXTURE` overrides in `server.py`. The browser suite drives the real server, so without them every `/api/stats` it requested appended a poll row to production `telemetry.sqlite3` (measured 20,280 -> 20,282 for one request) and every value assertion depended on whatever engine owned :8080. The fixture answers `_get_json` from a pinned document and aborts startup if that document is unusable, never falling back to the live engine silently.
- `agent/tests/ui/fixtures/engine.json` — pinned Strata-shaped engine answers whose `gpu_*` counters carry values this PC's AMD driver never supplies, which finally makes the GPU panel's measured path testable.
- The UI suite grew from browser 10 / static 7 to **browser 25 / static 16**, every new check mutation-proven. New browser checks cover the null gauge, HUD context scaling, chart axes/gaps/legend/series breaks, history bars and scrubbing, the Requests fold, layout version migration, header liveness and fixture-driven GPU values; new static checks cover GPU name provenance, empty-prior percentages, fallback bucket shape, nav coverage, header unit uniqueness, gauge scale labelling, fixture honouring and settle discipline.
- Fixed sleeps replaced by observable settles (`__lastLayout`, `__lastRender`, `__lastChartFetch`, `__lastChartRender`, `__lastUsage`). This caught a real flake: `fetchUsage()` grows the Usage tile after load, so a masonry pass that merely post-dated a viewport change could be stale — `tiles without a sufficient row span: ['usage:66']`.
- `tests/telemetry/`: the first unit tests for the telemetry maths (35 analysis + 22 day-rollup + 25 timeseries checks), running in CI alongside the usage and UI suites.

## [0.2.1] - 2026-10-26

### Changed
- The tile area is now a masonry grid instead of a fixed-row grid: `app.js` measures each panel and gives it a row span on a 4px track, so columns pack flush with no blank gutters between blocks of different heights. The column count follows the window (`minmax(300px,1fr)`, one column at or below 900px) and is recomputed on load, on every data render, when a `<details>` opens or closes, on resize (ResizeObserver), on a Full/Compact view switch and after each drag. Wide panels (requests, charts, history) and the whole Detail region span the full width; the Detail region packs in its own columns rather than one narrow stack.

### Added
- `agent/tests/ui/test_ui_browser.py`: a headless-browser functional suite that drives the dashboard over CDP with a hand-rolled stdlib websocket client (no new dependencies) on its own free port — Edge here, Chrome paths for CI, and a visible `NOTRUN browser-unavailable` skip when no browser exists. Ten checks: clean page load, live masonry row spans with no slack, full-width wide tiles, column count adapting at 1240/980/860/640px, **Save layout** writing the order, **Reset layout** clearing it and restoring the default order, a trusted-input drag persisting, the Detail region packing in its own columns with tight spans, Full→Compact→Full leaving every span correct, and a reload reproducing the saved order in both grids. Mutation-proven: renaming `#layout-save`, removing or inflating the row spans, moving the 900px breakpoint, dropping the wide-tile rule, collapsing the Detail region to one column, widening its track unit and skipping `restoreOrder()` each fail their check.

## [0.2.0] - 2026-10-26

### Changed
- Dashboard UI modernization (M79): the full view is a compact dashboard — a KPI strip in the sticky header (decode tok/s, model state, watts, % context, % cache hit) replaces the hero band; panels sit in one CSS Grid tile system (wide tiles for requests/charts/history) instead of the multi-column masonry; six secondary panels (engine, hardware, cache, spec, switch, log) move behind a collapsible Detail section. Design-token layer adds spacing/density/elevation/type scale; tables are dense with zebra rows and sticky headers; charts keep their controls and adopt tile sizing; breakpoints collapse at 900px and 480px.
- Drag-and-drop now works across the tile grid and the Detail region; saved layouts from the old masonry/band format migrate automatically. The footer Save/Reset layout buttons and `?reset=1` keep working.

### Added
- `agent/tests/ui/`: static UI suite (7 checks) that makes the id contract between index.html and app.js mechanical — literal and template-built ids, DEFAULT_ORDER vs panels, HUD id count, stale-class leftovers, and a free-port server smoke; wired into CI (`usage-tests.yml`). Mutation-proven: deleting a contract id fails the suite.

## [0.1.15] - 2026-10-25

### Fixed
- Usage ledger (M78-H5): the executor models are set by `LLM_MONITOR_EXECUTOR_MODELS` and named in `/api/usage` (`executor_models`), so a new quant no longer reads as executor 0; the repo filter stops at a path boundary (`llm-monitor-old` no longer matches `llm-monitor`). 4 new cases, 33 in all. The API test takes a free port (a fixed one failed a second run within a minute on Linux: TIME_WAIT) and checks the server came up.

### Added
- CI: `usage-tests.yml` runs the usage suites and the e2e gates on every push.

## [0.1.14] - 2026-10-25

### Fixed
- Usage ledger (M78-H4): Claude Code timestamps with milliseconds were not parsed, so every orchestrator row was stored with no time and every window read 0 for Claude Code. They now parse; a record with no usable time is skipped and counted; the rows stored without a time are removed once and re-read (5 new cases, 29 in all).

## [0.1.13] - 2026-10-25

### Added
- Usage ledger (M78): `usage_ledger.py` ingests numbers-only token usage of Claude Code and Hermes into `usage.sqlite3`; `/api/usage` and `/api/usage/sessions` serve it; a background thread ingests every 60 s; a "Usage ledger" panel shows today and 7 days. Built through the Homelab delegation pipeline (Strata IQ3_S writing from specs; contract 24 + API 4 cases, mutation proof 5/5).

## [0.1.12] - 2026-10-17

### Changed
- Dashboard runs under a supervisor (`service-supervisor.ps1`) that restarts it with backoff (5 s doubling to 60 s) and logs every start and exit to `%LOCALAPPDATA%\LLMMonitor\service-<port>.log`.
- The server runs in the supervisor's kill-on-close job: stopping or killing the supervisor (or its task) stops the server too.
- The supervisor writes `service-<port>.state.json` (PIDs, start times, heartbeat), honours `stop-<port>.request`, and takes over an orphaned server of ours instead of leaving it unsupervised.
- Installer `install-service.ps1` registers the logon task `LLMMonitor` with no execution time limit; with `-WithBoot` also the S4U boot task `LLMMonitorBoot` (elevated shell). It aborts when it cannot remove an old task. Applied by the user on 2026-10-17.
- `restart-llm-monitor.ps1` refuses a foreign port owner before touching anything, stops the dashboard through a stop request (works for the boot task's session-0 chain), stops both tasks, stops leftovers only by PID after a full-path match, and logs each action. `-Port <n>` no longer restarts the 8090 task.
- The access log records only 4xx and 5xx responses (numeric comparison, independent of the Python version).
- Logs over 5 MB rotate to `.1` when the supervisor starts a server.

### Fixed
- A second dashboard on the same port now fails with a bind error instead of silently sharing the port.
- Restart script: an empty pipeline passed an empty PID list to `Stop-Process`.
- A task stop no longer leaves the server running without a supervisor.

### Tooling (agent)
- `agent/scripts/gate-service.ps1` (state gate) and `agent/scripts/lint-handover.ps1` with fixture tests in `tests/lint-handover/`.

## [0.1.11] - 2026-10-15

### Added
- **Windows auto-start service.** Two batch files beside `server.py` start the dashboard by
  itself when the machine starts: `install-service.bat` registers two per-user scheduled tasks
  (no admin privileges) — `LLMMonitorBoot` (ONSTART, runs at every system startup/boot/restart)
  and `LLMMonitor` (ONLOGON, runs at every interactive sign-in). `llm-monitor-start.bat` spawns
  `server.py` on port 8090 detached via PowerShell `Start-Process` (so each task returns
  immediately) and resolves a real Win32 `python.exe`. Logs go to `%LOCALAPPDATA%\LLMMonitor`. The
  installer is idempotent; stop with `schtasks /delete /tn "…" /f`.

## [0.1.10] - 2026-10-12

### Added
- **Token usage history & comparison table (M71).** Total token usage per request, a 4-period
  token history (today, yesterday, this week, this month), and a 3-row history comparison table
  (today vs yesterday, this week vs last week, this month vs last month).
- **Compact half-page HUD & multi-tab interface (M72).** Accessible tab switcher (Full Dashboard
  vs Compact HUD), high-density HUD layout, one-click pop-out overlay launcher, `?view=compact`
  URL support, and standalone desktop overlay styling.
- **Comprehensive throughput analytics & prefill sparkline (M73).** Average decode tok/s, average
  prefill tok/s, rolling peak decode/prefill, prompt processing latency (TTFT), request rate,
  a dedicated SVG prefill sparkline, and a compact HUD average-prefill readout.
- **Configurable timeseries charts (M74).** Interactive SVG chart panel across 8 timeframes
  (15m, 1h, 3h, 6h, 24h, 7d, 30d, 90d) and 4 metric modes (All, Tokens/s, Token Usage,
  Requests), backed by a new `GET /api/timeseries` endpoint that aggregates the SQLite poll
  and day tables with counter-reset protection, hover crosshair, and tooltips.

### Fixed
- **History & period comparison calculations remediation (M75).** Eliminated rolling-window
  decays, ghost idle throughput comparisons, day rollover underflows, falsy-zero delta
  suppressions, and hourly boundary request losses; hour buckets now bridge so
  `sum(hours) == requests`; zero-safe percentage deltas (`+100%` / `±0%`) render correctly.
- **Progress tracking consistency.** Re-pointed the stale `current_milestone` (M1 → M75) and
  added the missing `**Status**` field to the milestone-75 doc so `/acp-validate` cross-layer
  status and file-pointer checks pass.

## [0.1.9] - 2026-10-08

### Added
- **Export endpoints for sharing collected telemetry with an outside reviewer.** `GET /api/export`
  returns JSON (`poll_rows` named-keyed, `days`, and `meta{generated, window_days, poll_cols}` so
  a reader can map columns); `GET /api/export.csv` returns plain CSV (header + rows). Data ships
  with field names and provenance, so it is usable, not garbage.
- **Richer dogfooding fields in the poll row.** `drafts_offered`, `drafts_accepted` (from the
  engine totals) and `pcie_share` (from the latest request) are now captured and exported. They come
  from the same `/metrics` dict the poll already reads, so there is zero extra engine cost.
- **Per-series sparkline window labels.** Each sparkline caption now states its own real x-axis
  (per-sample interval + span) instead of a blanket "recent history": tok/s/power/CPU/VRAM are
  per-poll (~5 s), requests follow `history_bucket_s` (default 75 s), and the history panel is per-day.
- **Decode throughput (tok/s) in the sticky header**, mirroring the prefill meter.

### Fixed
- **Backward-compatible poll schema growth.** The three new columns are added via an idempotent
  ALTER loop, so existing SQLite DBs migrate cleanly (20 → 23 columns) without losing history.

## [0.1.8] - 2026-10-07

### Fixed
- **The GPU panel no longer reads as all-zeros on the AMD HIP driver.** The five GPU
  readings split by what the driver can honestly supply:
  - **VRAM used/total is now derived** from the engine's live `vram_free_mib` against the
    fixed card total (RX 7900 XTX = 24 GB), so the panel shows real used/total (e.g.
    23.6 / 24.0 GB) tagged `derived`, and the GPU sparkline draws a VRAM series built from
    the dashboard's own poll rows (the engine keeps no `gpu_*` history series).
  - **Utilisation and power are modelled** from the same engine-activity table that drives
    the Power card (prefill hot, decode bandwidth-bound, idle parked), tagged `modelled`,
    so the GPU card and the Power card can never disagree.
  - **Device name falls back to the rated card** ("AMD Radeon RX 7900 XTX (rated)") since
    the machine is fixed, instead of printing "1 GPU(s)".
  - **Temperature and PCIe RX stay `--`** — no counter and no honest proxy on this driver
    (the engine sources hardware via psutil, which has no GPU API on Windows; the AMD
    Graphics Info API shim won't load standalone). Shown honestly, never guessed.
- Every GPU figure now carries its source (`measured` / `derived` / `modelled` / `rated`),
  and the panel's state chip distinguishes live counters from modelled readings.

### Changed
- README's GPU bullet documents the recovered/derived/modelled split; the `/api/stats`
  gpu shape gained the `*_source` fields and `history.vram_pct`.

## [0.1.7] - 2026-10-07

### Changed
- **The prefill speed meter is now a dedicated full-width gauge band** pinned to the
  bottom edge of the sticky header, under the measurements, rather than a compact
  inline bar. It reads like a slider: a track with scale ticks every 25%, a gradient
  fill, and a knob that slides to the current reading. The fill width and knob position
  are eased by the same CSS transition so the meter rises and falls in realtime as the
  prefill rate changes (the `prefers-reduced-motion` block still snaps it).
- README documents the gauge band (ticks + sliding knob) instead of the compact meter.

## [0.1.6] - 2026-10-07

### Added
- **Header identity line**: the engine that owns the port and the model it is
  serving now read large and bold in the top bar, with a monogram mark drawn per
  engine (stacked layers for Strata, a V over a ring for Vulkan) colored with the
  engine's own accent. Neither engine ships a logo asset, so the marks are inline
  SVG drawn for this dashboard.
- **Hero band gains prefill tok/s and model state** (Reading / Generating / Queued /
  Idle), so the headline readings are decode speed, prefill speed, state, watts,
  % context, % cache hit. The prefill reading carries a gradient speed meter that
  eases to the value (custom bar, not the native `<meter>`, which cannot be gradient-lit).
- The prefill speed meter was then **moved into the sticky header bar** (with its
  number) so it stays pinned at the top while the page scrolls, rather than sitting
  in the hero band.

### Changed
- The hero's % context reading now rounds to two decimals instead of printing the
  raw float; the gauge still rounds to whole percents.
- README documents the header identity line and the expanded hero band.

## [0.1.5] - 2026-10-07

### Fixed
- **Cumulative-counter deltas could go negative** when the engine restarts (its
  counters reset), so a day/window's last-minus-first swallowed a whole session or
  printed a negative. Added `cumulative_delta`, which splits at each decrease and
  sums the segments; applied to both the daily rollups and the existing windowed
  `db_analysis` (including `req_per_min`). Verified against the live DB: 351 req /
  25.0 tok/s, all positive.
- **Drag froze over the hero/gaps/footer and cross-container drops failed silently**
  because `pointermove`/`pointerup` were bound to the container. They now live on
  `document` and the drop target is hit-tested per move, so a card can land in the
  band and vice versa.
- A plain click left the preview slot stuck in the DOM; the slot is now always
  removed on release/cancel.

### Added
- **History panel**: daily/weekly/monthly rollups in a tiny per-day SQLite table
  (finalized at each day boundary before pruning, so weekly/monthly survive the
  ~28h poll window), period comparisons (today vs yesterday, this week vs previous,
  this month vs previous, each with a % delta), and a **day scrubber** to slide a
  marker across recorded days and read any past day's numbers with its delta vs the
  day before.
- **Visible drop slot**: a dashed outline shows where a dragged panel will land,
  with the other panels parting around it, so the drop point is unambiguous before
  releasing. The dragged panel eases toward the pointer for a fluid follow.
- Footer **Save layout** / **Reset layout** buttons (the arrangement also
  auto-persists on every commit, so the latest positions are always recorded).

### Changed
- README documents the History panel, the day scrubber, the visible drop slot, and
  the Save/Reset buttons; the `/api/stats` shape gains `daily` and `periods`.

## [0.1.4] - 2026-10-07

### Added
- **Drag-and-drop layout**: grab any panel by its heading and drop it anywhere in
  the card masonry or the history band. Document order drives both containers, so
  a drop reorders the DOM; the arrangement is remembered in `localStorage` and
  restored on load, and `?reset=1` in the URL clears it. A FLIP animation glides
  the panels to their new slots, and a dragged panel lifts with a deeper shadow
  and accent border. Touch is excluded so page scrolling is never hijacked, and
  drags start only on the panel box or its heading, never inside its text.
- Footer hint stating the drag affordance and the reset URL.

### Changed
- README documents the drag-and-drop layout alongside the monitoring sections.

## [0.1.3] - 2026-10-07

### Fixed
- Telemetry no longer fails with `sqlite3.ProgrammingError` ("SQLite objects created
  in a thread can only be used in that same thread") on every poll after the first.
  `ThreadingHTTPServer` serves each request in its own thread, so the connection is
  now opened per poll inside `telemetry()` in the using thread and closed afterwards
  (`check_thread=False` is Python 3.13+ and the project runs 3.12, so per-poll open
  is the correct fix). This was the cause of "telemetry off — ProgrammingError …".

### Added
- A full-width **hero band** ("At a glance") above the cards: the four headline
  readings — tok/s, watts, % context, % cache hit — as large tabular-num figures,
  collapsing to two columns under 900px.

### Changed
- **Layout**: the status cards now flow in a CSS multi-column masonry (two columns,
  `break-inside: avoid`) instead of a fixed grid, so ragged-height cards pack with
  no empty cells between blocks; the history panels remain a full-width band below.

## [0.1.2] - 2026-10-07

### Added
- A lifetime **session-totals** line in the Telemetry panel (since / requests / prompt / output
  from the engine's cumulative counters) — a look-back that stays useful before the SQLite
  window has enough samples to analyse.
- A compact **endpoint-status** chip in the footer marking which engine endpoints
  (`health`/`metrics`/`slots`/`models`/`status`) the backend reached this poll, so a partial
  outage is visible without opening the console.

### Changed
- **Layout**: replaced the fixed 2-col × 6-row grid area map with a dense auto-flow grid that
  packs panels by importance (`order`) with no forced empty cells, and lays the three history
  panels (telemetry / requests / log) full-width as a bottom band. This removes the whitespace
  around sparse panels (carryover a1-02).
- README documents the new session-totals line and endpoint chip.
- Contributor identity set to `ssucipto` in `agent/core/identity.yml`.

## [0.1.1] - 2026-10-07

### Fixed
- Telemetry history no longer silently disabled when the server is started from a
  directory other than the one beside `server.py`. `DB_PATH` is now resolved to an
  absolute path, so the SQLite side channel opens the file beside the script regardless
  of the process working directory. This was the root cause of the empty GPU/power trend
  and empty Telemetry panel.
- The trend-vs-prior-window comparison no longer treats a legitimate zero-request window
  as missing (presence check instead of truthiness).
- Removed dead duplicate `ctx`/`cache`/`spec` assignments in `db_record`.

### Added
- `/api/stats` now returns a `telemetry` field (`{"ok":true,"rows":N}` or
  `{"ok":false,"error":"..."}`) so a disabled side channel is visible on the dashboard.
- The Telemetry panel distinguishes "telemetry off — <error>" from "awaiting history".
- The GPU panel captions why its figure is empty on a driver that exposes no GPU counters
  (e.g. AMD HIP), rather than rendering a blank chart.

### Changed
- README documents the new `telemetry` field in the `/api/stats` shape.

## [0.1.0] - 2026-10-07

### Added
- Initial dashboard: engine status, live inference, context window, throughput, power
  model, cache, spec-decode, hardware, GPU, telemetry analysis, and requests table.
- SQLite telemetry with bounded history and windowed performance analysis.
- ACP Enhanced framework bootstrap and project identity.
