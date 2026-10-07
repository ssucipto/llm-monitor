# Changelog

All notable changes to the **llm-monitor** dashboard are documented here.
Version numbers track the project (not the ACP Enhanced framework, which is
versioned separately at 6.40.0). This project follows [Semantic Versioning](https://semver.org).

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
