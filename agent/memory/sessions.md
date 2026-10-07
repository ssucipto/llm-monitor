# Session Memory
# Format: YAML blocks, last 3 loaded per session, auto-compacted at 15 entries
# DO NOT edit manually — updated by /acp-commit

- date: 2026-10-07
  executor: strata-coder
  tasks: []
  done:
    - gpu-vram-derived-from-vram-free-mib
    - gpu-util-modelled-from-activity-table
    - gpu-power-card-fallback-to-model
    - gpu-name-rated-fallback
    - gpu-sparkline-vram-series-from-poll-rows
    - audit-5-gpu-readings-report
    - audit-carryovers-a5-01..06
    - readme-changelog-progress-doc-parity
  deferred:
    - r3-01-sparkline-window-label
    - r1-01-ci-harness-na
  key_fact: "On the AMD HIP driver the engine has NO gpu_* counters (psutil, no GPU API on Windows), but engine.vram_free_mib is live — so VRAM is the one recoverable GPU reading (used = fixed card total - free). amdgfxinfo64.dll won't load standalone (WinError 1114), no GFXINFO_* exports. temp/PCIe are NOT ACTIONABLE"

- date: 2026-10-07
  executor: strata-coder
  tasks: []
  done:
    - prefill-gauge-band-in-sticky-header
    - setMeter-to-setPrefillGauge
    - a2-01-telemetry-verified-live
    - readme-changelog-doc-parity
    - stray-NUL-artifact-removed
  deferred:
    - r3-01-sparkline-window-label
    - r1-01-ci-harness-na
  key_fact: "Static assets (index.html/style.css/app.js) are served from disk per request by SimpleHTTPRequestHandler, so front-end edits need no server restart — only build_stats changes do"

- date: 2026-10-07
  executor: strata-coder
  tasks: []
  done:
    - db-path-resolve-fix
    - telemetry-status-surfaced
    - falsy-zero-trend-guard
    - dead-code-cleanup-db-record
    - gpu-panel-caption
  deferred:
    - a1-02-grid-redesign
    - a2-01-restart-8090
    - r1-01-ci-harness-na
  key_fact: "DB_PATH must be .resolve()d — sqlite resolves relative paths against the process cwd, so a server started elsewhere silently gets unable to open database file (telemetry off, empty trends)"

