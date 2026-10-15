# Session Memory
# Format: YAML blocks, last 3 loaded per session, auto-compacted at 15 entries
# DO NOT edit manually — updated by /acp-commit

- date: 2026-10-15
  executor: strata-coder
  tasks:
    - r1-01
  done:
    - installed-acp-ci-review-integrity-harness
    - authored-missing-review-scan-ts-and-taint-scan-py
    - fixed-progress-yaml-duplicate-key-parse-bug
    - fixed-tab-cr-emit-contract-in-review-scan
    - fixed-review-measure-scanner-exit-code-handling
    - fixed-e2e-integrity-fp-baseline-grep
    - removed-per-finding-python-and-awk-spawns-perf-fix
    - host-calibrated-perf-budget-in-ci-step
    - all-10-ci-gates-pass-full-tier
  deferred: []
  key_fact: "Windows/Git-Bash process-spawn overhead is ~5-10x a Linux agent host; the framework's own finding-free scan floor here is ~1.4s vs ~103ms on the calibrated host, so absolute-ms perf budgets must be host-calibrated (measure floor, budget=max(2000,3x floor)) rather than hardcoded"

- date: 2026-10-12
  executor: strata-coder
  tasks: []
  done:
    - acp-validate-version-and-pointer-checks
    - fixed-stale-current-milestone-M1-to-M75
    - added-missing-status-field-to-milestone-75-doc
    - confirmed-code-gates-py-compile-node-check-pass
  deferred:
    - r1-01-ci-harness-na
  key_fact: "progress.yaml had a stale current_milestone (M1) while M71-M75 were completed; and milestone-75 doc was missing the **Status** field that the other three milestone docs carry. Both corrected so /acp-validate cross-layer status + file-pointer checks pass. YAML parses clean after edits."
  done:
    - m74-backend-timeseries-aggregation-endpoint
    - m74-sub-day-minute-and-hourly-bucketing-with-counter-reset-safety
    - m74-multi-day-rollups-with-live-today-merge
    - m74-interactive-svg-timeseries-charts
    - m74-metric-tabs-all-throughput-tokens-requests
    - m74-range-selectors-15m-1h-3h-6h-24h-7d-30d-90d
    - m74-hover-crosshair-and-interactive-tooltips
    - m74-client-side-fallback-downsampling
    - audit-17-pre-impl-readiness
    - audit-18-post-impl-verification
    - review-008-coderabbit-diff-review
  deferred:
    - r1-01-ci-harness-na
  key_fact: "M74 landed: Interactive SVG timeseries chart panel (#charts) across 8 configurable timeframes (15m, 1h, 3h, 6h, 24h, 7d, 30d, 90d) and 4 metric modes (All Combined, Tokens/s, Token Usage, Requests). Endpoint GET /api/timeseries aggregates SQLite poll and day tables with counter-reset protection. High-density SVG canvas renders vector geometry, hover crosshair, and floating tooltip. Client-side fallback provides seamless downsampling resilience."

- date: 2026-10-12
  executor: antigravity-coordinator
  tasks:
    - task-73
  done:
    - m73-average-tok-s-and-average-prefill
    - m73-peak-throughput-rates-and-ttft-latency
    - m73-dedicated-prefill-sparkline
    - m73-compact-hud-average-prefill
    - audit-15-pre-impl-readiness
    - audit-16-post-impl-verification
    - review-007-coderabbit-diff-review
  deferred:
    - r1-01-ci-harness-na
  key_fact: "M73 landed: Throughput panel expanded to 9 metrics: Average decode tok/s, Peak decode, Current prefill, Average prefill, Peak prefill, Prompt latency (TTFT), and Request rate. Added dedicated SVG prefill sparkline (#prefill-spark) in emerald green. Compact HUD gained average prefill readout (#hud-prefill-sub). Client-side fallback derivation provides zero-restart resilience."

- date: 2026-10-12
  executor: antigravity-coordinator
  tasks:
    - task-72
  done:
    - m72-compact-hud-half-page-interface
    - m72-accessible-multi-tab-system
    - m72-desktop-overlay-popout-window
    - audit-13-pre-impl-readiness
    - audit-14-post-impl-verification
    - review-006-coderabbit-diff-review
  deferred:
    - r1-01-ci-harness-na
  key_fact: "M72 landed: Multi-tab navigation with Full Dashboard and Compact HUD views. Compact HUD provides high-density layout (identity orb, hero speed, 2x2 vitals matrix, last generation spotlight, micro trends, sparkline, endpoint pills) bound to live /api/stats. Pop-out launcher opens standalone 480x820 overlay window with TOC and chrome suppressed. 100% non-regressed with zero DOM collisions."

- date: 2026-10-12
  executor: antigravity-coordinator
  tasks:
    - task-71
  done:
    - m71-total-tokens-per-request
    - m71-token-history-hour-today-yesterday-week-month
    - m71-history-comparison-table-hour-today-week-month
    - m71-last-request-vs-previous-comparison
    - audit-11-pre-impl-readiness
    - audit-12-post-impl-verification
    - review-005-coderabbit-diff-review
  deferred:
    - r1-01-ci-harness-na
  key_fact: "M71 landed: Requests table renders Total tokens (prompt + out) and live request delta. History panel displays token totals (last request, this hour, today, yesterday, this week, this month) and a 5-row comparison table (Last request vs Previous, This hour vs Last hour, Today vs Yesterday, This week vs Last week, This month vs Last month) with deltas, request counts, and speeds. Resilient to backend restarts with client fallback."

- date: 2026-10-11
  executor: antigravity-coordinator
  tasks: []
  done:
    - audit-10-remediations-landed
    - review-004-coderabbit-fixes
    - db-prune-catastrophic-truncation-fixed
    - sqlite-indexes-idx-poll-t-idx-day-d
    - strip-dead-gather-functions
    - urlsplit-query-string-support
    - sessions-yaml-syntax-repaired
    - requests-table-time-column-added
  deferred:
    - r1-01-ci-harness-na
  key_fact: "Engine exposes unix epoch timestamp in /metrics.requests ('time'), but Requests table omitted Time column; added HH:MM:SS Time column to Requests table in index.html & app.js. Engine has no caller IP/client source telemetry."

- date: 2026-10-08
  executor: strata-coder
  tasks: []
  done:
    - decode-speed-surfaced-header-chip
    - throughput-panel-big-number-labeled-decode
    - audit-9-removed-redundant-decode-fact-row
  deferred:
    - r1-01-ci-harness-na
  key_fact: "Decode speed surfaced once per surface: header chip 'decode tok/s' + panel big number suffixed 'decode'. audit-9 caught that the first pass added a redundant Decode fact row (thr-decode duplicated thr-now, both from throughput.now) + a label inconsistency; removed it. No orphan thr-decode ref. Scanner clean."

- date: 2026-10-08
  executor: strata-coder
  tasks: []
  done:
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

