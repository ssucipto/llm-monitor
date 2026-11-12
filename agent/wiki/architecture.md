# System Architecture
# Update monthly or when service boundaries change
# last_verified: 2026-11-06

last_verified: 2026-11-06

## System Map

```
               [ Browser / UI Dashboard (port 8090) ]
                                |
                   HTTP GET (/api/stats, /api/timeseries, /api/usage)
                                v
               [ LLM Monitor Server (llm-monitor/server.py) ]
                 |                       |                 |
  +--------------+---------+             |                 +----------------+
  |                        |             v                                  |
  v                        v      [ Autonomous Telemetry Daemon ]           v
[ Usage Thread ]    [ Strata Engine ]   (every 15s, _TELEMETRY_LOCK)  [ Log Ingestion ]
  |                 (port 8080/8081)     |                              |
  v                        |             v                              v
(usage.sqlite3)            +---> (telemetry.sqlite3)           (C:\ai\Strata\*.log)
```

## Service Boundaries

- **`llm-monitor/server.py` (`:8090`)**:
  - Hosts the dashboard frontend (vanilla ES6, accessible HTML/CSS).
  - Background daemon `telemetry_poll_daemon()` polls `/metrics` every 15s under `_TELEMETRY_LOCK`, persisting rolling hardware/engine telemetry into SQLite (`telemetry.sqlite3`) independently of browser tabs.
  - Background daemon `usage_thread` ingests token usage from Claude Desktop / Cline session files into SQLite (`usage.sqlite3`).
  - Evaluates live engine config (`gather_config`) exposing DFlash2 drafting, k8v4 KV cache, 32k resident KV window, and conversation cache metadata.
  - Dynamically discovers and tails the active engine log (`gather_log`) based on `engine_active.txt` (Strata at `C:\ai\Strata\strata-*.log` or llama.cpp fallback).
- **Service Supervisor & Watchdog (`service-supervisor.ps1`, `restart-llm-monitor.ps1`)**:
  - Run as scheduled tasks `LLMMonitor` (interactive desktop) and `LLMMonitorBoot` (Session 0 S4U boot service).
  - Enforces process ownership tree: `service-supervisor.ps1` -> `run-server-8090.cmd` -> `python.exe server.py`.
  - Communicates graceful shutdown via `stop-8090.request` and cross-session state attestation via `service-8090.state.json`.
  - Strictly prohibits killing processes by name (never touches LLM Gateway on 8080 or Strata on 8081).
- **Service Verification Gates (`agent/scripts/gate-service.ps1`)**:
  - Gates G1-G9 enforcing PSScriptAnalyzer compliance, syntax parse, process supervision chain, scheduled tasks, process write times, log purity, and port availability.

## Key Data Flows

1. **Autonomous Telemetry Loop**:
   - `telemetry_poll_daemon()` wakes every 15s.
   - Calls `build_stats()` under `_TELEMETRY_LOCK`.
   - Fetches JSON from engine `/metrics` on `http://127.0.0.1:8080` (with fallback to 8081).
   - Ingests CPU, RAM, GPU power/utilization, token throughput, cache hit ratios, and speculative decode rates.
   - Appends poll row to `telemetry.sqlite3` (`poll` table, max 20,000 rows).
   - Updates `_LAST_TELEMETRY_WRITE`.
2. **Dashboard Query Flow**:
   - Browser requests `GET /api/stats`.
   - `server.py` serves current snapshot from memory/engine.
   - Browser requests `GET /api/timeseries?range=1h`.
   - `server.py` queries `telemetry.sqlite3` and formats 1m/5m/1h aggregations for SVG sparklines.
3. **Usage Accounting Flow**:
   - `usage_thread` checks session roots every 60s.
   - Parses jsonl transcripts and extracts model token counts, cost calculations, and timestamps into `usage.sqlite3`.

## External Dependencies

- **Local LLM Gateway / Strata Engine**:
  - Listens on `http://127.0.0.1:8080` (upstream proxy) and `http://127.0.0.1:8081` (Strata Coder 0.1.57 with Qwen2.5-Coder-32B-Instruct / unsloth-ud-iq4_xs-v31).
  - Exposes `/health`, `/metrics`, `/slots`, `/props`, `/v1/models`.
- **Operating System & Python Runtime**:
  - Windows 11 with PowerShell 5.1/7+.
  - Python 3.12 Standard Library (`http.server`, `sqlite3`, `urllib`, `threading`, `json`). Zero third-party Python dependencies.
