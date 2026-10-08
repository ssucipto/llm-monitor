# Session Memory
# Format: YAML blocks, last 3 loaded per session, auto-compacted at 15 entries
# DO NOT edit manually — updated by /acp-commit

- date: 2026-10-08
  executor: strata-coder
  tasks: []
  done:
    - r3-01-per-series-sparkline-window
    - drawspark-windowms-caption
    - header-tok-reading-added
  deferred:
    - r1-01-ci-harness-na
  key_fact: "r3-01 closed: drawSpark takes per-series windowMs; tok_s/power/cpu/vram=REFRESH_MS(5s), requests=historyBucketMs(from data.history_bucket_s*1000, default 75s), hist=86400000. Caption states per-sample interval + span, no blanket label. Header tok/s added (top-tok, mirrors top-prefill)."

- date: 2026-10-08
  executor: strata-coder
  tasks: []
  done:
    - audit-8-telemetry-lifecycle-2nd-pass
    - a7-05-drafts-and-pcie-share-captured
    - poll-schema-alter-migration-23-col
    - insert-arity-bug-fixed-23-placeholders
  deferred:
    - r3-01-sparkline-window-label
    - r1-01-ci-harness-na
  key_fact: "a7-05 closed: drafts_offered/drafts_accepted (totals) + pcie_share (requests[0]) now in poll row + export. Zero extra engine cost (same /metrics dict). ALTER loop extended to (col,ctype); old 20-col DBs migrate to 23. INSERT arity bug (22 vs 23 ?) caught by migration test, not py_compile."

- date: 2026-10-08
  executor: strata-coder
  tasks: []
  done:
    - audit-7-telemetry-lifecycle-report
    - db-prune-days-rollup-pruning
    - db-daily-max-400-to-90-three-months
    - api-export-json-and-csv
    - engine-log-capability-confirmed-short-window
  deferred:
    - a7-05-engine-per-request-fields
    - r3-01-sparkline-window-label
    - r1-01-ci-harness-na
  key_fact: "telemetry.sqlite3 is a persistent gitignored file beside server.py (survives sessions). Engine keeps only 60 samples/series + 12-30 request records and has NO /log endpoint, so our DB is the only durable record. day rollup was never pruned (unbounded disk) and cap was 400d; fixed to 90d + db_prune_days. Added /api/export (JSON named fields + provenance) and /api/export.csv. Data verified real (6239 poll rows, plausible values)."

- date: 2026-10-08
  executor: strata-coder
  tasks: []
  done:
    - gpu-2nd-pass-audit-6
    - gpu-2nd-pass-review-003
    - vram-free-mib-reference-frame-confirmed-card-relative
    - gpu-mem-hint-zero-guard-fix
    - acp-ci-fast-skip-honest
  deferred:
    - r3-01-sparkline-window-label
    - r1-01-ci-harness-na
  key_fact: "vram_free_mib is card-relative (live: 367->250 busy, 1722 idle — rises when idle, falls when busy; arena+expert_cache sum constant 27458 > 24576 so they overlap inside the card). Derived VRAM fix is sound, NOT a shortcut. Only real defect found in 2nd pass: app.js gpu-mem-hint used truthiness (mem_used && mem_total) which hides a legitimate 0; fixed to != null."

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

