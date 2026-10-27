# Session Memory
# Format: YAML blocks, last 3 loaded per session, auto-compacted at 15 entries
# DO NOT edit manually — updated by /acp-commit

- date: 2026-10-27
  executor: zed
  branch: main
  tasks: [task-81-t3]
  done:
    - "a33-08 hit/accept rates are now the span's own ratios (window_pct over cumulative counters) in db_analysis, db_hour_aggregates and day_aggregates; legacy *_pct_mean keys kept so /api/stats stays additive"
    - "a33-09 every published rate carries its window label (mean_window session, peak_window last 60 min) printed inline by app.js"
    - "a33-10 PREFILL_CEILING_TOK_S 5000 from 20,165 live samples; bounded_prefill in all three aggregate paths + sparkline holes + '· bounded' tag; raw samples stay in the DB so /api/export is still honest"
    - "a33-11 tok_s_weighted and prefill_weighted (new additive prompt_ms poll column) replace unweighted means of instantaneous rates"
    - "a33-13 day_aggregates ghost-idle suppression; a33-14 SPAN_FLOOR_S 5.0 replaces the 1e-9 sentinel and makes the dead span guard live"
    - "a33-16 +100%-from-empty-prior fixed in THREE sites, not the two the audit listed (History table + both Compact HUD trend rows), guarded by a new static check no-empty-prior-percent"
    - "a33-17 first unit tests for db_analysis / day_aggregates / db_hour_aggregates: tests/telemetry (35 + 22 assertions) wired into usage-tests.yml and run-e2e-tests.sh"
    - "found and fixed a defect the audit never saw: db_hour_aggregates published prefill_weighted as a permanent None stub because its SELECT omitted prompt_ms"
    - "nine mutations proven across the two suites (window ratio x2, prefill_weighted stub, span sentinel, day baseline, ghost-idle guard, day bound, hour bound, +100% literal)"
    - "records: a33-08/09/10/11/13/14/16/17 closed with evidence, a33-37 recorded as a new pending carryover, progress.yaml M81 3/8"
  deferred:
    - "M81 T4 chart axes, T5 history chart + scrubber, T6 block order + collapsible Requests + Detail re-categorisation, T7 header, T8 steps 2-6 -> those tasks"
    - "audit-34 G-34-01: test_ui_browser detail-packing asserts >=4 tiles; T6 shrinks the region to 3 and MUST update that assertion in the same commit"
    - "a33-37 System log panel tails only Hermes llama.cpp logs while Strata's own log (6.2 MB, live today) is never read -> needs its own task"
    - "a33-12 sample density depends on open tab count; the ThreadingHTTPServer write race that makes duplicate timestamps is NOT fixed (only its arithmetic consequence is)"
    - "a33-32 saved-layout versioning decision -> must be surfaced to the user before T6 ships"
    - "a32-02 fixed sleeps -> task-81-t8 step 3; a25-02 reboot test -> still user-gated"
    - "restart of :8090 (PID 10496, older than these edits) -> supervisor owns it; its poll table has no prompt_ms column yet, so prefill_weighted is legitimately None there until it restarts"
  key_fact: "A per-poll mean of a session-cumulative ratio is not a window rate — the error varies per snapshot, so it cannot be corrected with a constant. And an assertion that calls a pure helper instead of the code path under test is unfailable: 'bounded prefill in the hour path' only became mutation-provable once it asserted on db_hour_aggregates' own returned record."

- date: 2026-10-26
  executor: zed
  branch: main
  tasks: [audit-33, audit-34, task-81-t1, task-81-t2, task-81-t8-step-1]
  done:
    - "audit-33 (36 findings) on visual presentation + measurement correctness; every claim re-verified against live /api/stats, live /metrics, the registry, the live SQLite DB or a direct experiment"
    - "M81 planned: milestone doc + 8 task docs + progress.yaml block; audit-34 pre-impl pass (8 findings) amended it before any code"
    - "a33-01 GPU named wrong: detect_host_hardware() (stdlib winreg join of Enum\PCI instances to display-class subkeys, ConfigFlags filter) names the live card; 1.3 ms, once at import; name_source os/engine/rated and name_conflict added"
    - "a33-02/03/04/05/07/36 front end: setGauge null renders -- with a striped is-none track, never 0; HUD power gauge (was reading a nonexistent rated_w) fixed via a peak_w alias; HUD context printed 7417.0% for a real 74.2%; HUD VRAM scales by mem_source; stale sparklines cleared"
    - "a33-34 test isolation: LLM_MONITOR_DB override; production poll rows unchanged across a full suite run (20,357 -> 20,357)"
    - "a32-01 closed with evidence: Actions run 40304874790 logs 'ok test_ui_browser.py: 10/10', no NOTRUN"
    - "five new checks (browser 13 / static 9), each mutation-proven against the exact original symptom"
  deferred:
    - "M81 T3 telemetry maths (window-correct hit/accept ratios, prefill outliers, day_aggregates ghost-idle, tests/telemetry) -> task-81-t3"
    - "M81 T4/T5/T6/T7 charts, history, block order + collapsible Requests, header -> those tasks"
    - "audit-34 G-34-01: test_ui_browser detail-packing asserts >=4 tiles; T6 shrinks the region to 3 and MUST update that assertion in the same commit"
    - "a32-02 fixed sleeps -> task-81-t8 step 3 (new checks settle instead of sleeping; older ones still sleep)"
    - "a25-02 reboot test -> still user-gated"
    - "restart of the :8090 server -> supervisor owns it; until then the running dashboard keeps serving the pre-fix GPU name"
  key_fact: "The engine's hardware_static.gpu_name is not a measurement: Strata indexes the Windows display device class in class order, so a leftover driver entry for a removed card (ConfigFlags 32) outranks the installed one. WMI AdapterRAM is a UInt32 cap and must never be used as VRAM total; the registry's qwMemorySize is the trustworthy size."

- date: 2026-10-26
  executor: zed
  branch: main
  tasks: [task-80-t1, task-80-t2, task-80-t3, task-80-t4, task-80-t5]
  done:
    - masonry-row-span-engine (ROW_UNIT 4px, layoutTiles/layoutAll/queueLayout, ResizeObserver)
    - detail-region-full-width + nested .tiles--detail packing (audit-30 F-30-01)
    - tile hierarchy/elevation + opacity-only entrance + 1100px KPI strip order (F-30-05..08)
    - agent/tests/ui/test_ui_browser.py rebuilt stdlib-CDP suite, 10/10 incl. save/reset/drag
    - mutation-proven save-button, masonry-spans, columns-adapt, wide-full-width, detail-packing, reload-restores-order
    - audit-32 (12 findings) and review-014 written; fixed the stale M78 task statuses; closed the dangling active_handoff
    - new browser checks detail-packing, view-toggle-spans, reload-restores-order; removed a false-pass in the reload check
    - records: CHANGELOG 0.2.1, README Layout section, progress.yaml M79+M80, a30-01/a30-02
    - recovery: agent/ restored from git + rebuilt 405 tracked and ~25 untracked docs
    - agent/.gitignore now tracks agent/tests/** so a UI suite can never be lost again
  deferred:
    - a25-02-reboot-test -> still user-gated (unchanged since M76)
    - a32-01-browser-suite-execution-in-ci -> read one Actions run log for 'ok test_ui_browser.py: 10/10'
    - a32-02-fixed-sleeps-in-browser-suite -> settle helper if a false failure is ever seen
    - push-to-remote -> user decision
    - lint-handover L9 fixture paths -> fixed with a labelled T7-receipts placeholder (original unrecoverable)
  key_fact: "gitignored ACP memory (agent/reports, milestones, tasks, sessions, and even untracked test code) has NO backup: one delete_path aimed at a scratch folder destroyed a whole session's work. Never pass a directory to delete tools; the app dir is llm-monitor/llm-monitor so 'llm-monitor/agent' is NOT 'agent'."

- date: 2026-10-17
  executor: zed
  branch: main
  tasks: [task-76-t4, task-76-t7]
  done:
    - fixes-1-5-supervisor-verified (parse + run :8090/8095-8099, HTTP 200)
    - restart-script-empty-array-fix ($owners = Get-OurOwners before foreach)
    - t7-step7-dup-supervisor-exit-0
    - install-verification (user ran install-service.ps1 -WithBoot natively; supervisor-log proof 06:06:45)
    - cleanup-probe-scripts-deleted (~230 files, scratch emptied, spare-port artifacts removed)
    - validate-findings-fixed (M76/M77 status drift -> completed/100)
    - handoff-claude-m76-install-verification written + HANDOFF-LATEST + progress.yaml active_handoff
  deferred:
    - a25-02-reboot-test -> task-76-t6 (user-gated)
  key_fact: "foreach ($x in FuncCall) without parentheses runs the call as a statement and iterates an EMPTY stream — Stop-Process -Id got an empty array; assign first ($owners = Get-OurOwners)"

- date: 2026-10-17
  executor: claude-opus-5-5
  branch: main
  tasks:
    - audit-27-m76-m77-zed-haiku-scoring
    - review-013-m76-m77-code-qualities
    - audit-27-remediation
  done:
    - scored-zed-59-haiku-67
    - gate-g10-checked-stops-and-cleanup
    - shared-kill-pattern-lint-l8-gate-g8
    - lint-head-parameter-and-exact-fixture-sets
    - gate-g7-wider-g1b-syntax-tree
    - restart-stop-request-both-tasks-port-fix
    - supervisor-kill-on-close-job-state-file-stop-request-orphan-takeover
    - s4u-boot-task-run-without-reboot
    - t7-steps-8-9-10-13-pass
    - records-milestones-changelog-readme-agents-skill-carryovers
    - adr-lm-001
    - handoff-zed-audit27-verification
  deferred:
    - reboot-test-decision-b → a25-02 (user)
    - independent-verification-of-audit-27-fixes → handoff-zed-audit27-verification-2026-10-17.md
    - commit-of-m76-m77-audit-27-work → user decision
  key_fact: "Children started with Start-Process leave the scheduled task's job, and an S4U (session 0) chain is invisible and unstoppable from the desktop. The supervisor must own its children (kill-on-close job) and expose a state file and a stop request."

- date: 2026-10-17
  executor: claude-haiku-5-5
  branch: main
  tasks:
    - m76-t0-supervision-restore
    - m76-t3-supervisor-end-log
    - m76-t3-supervisor-simplify
    - m76-t5-restart-rename
    - m77-t0-restore-supervision
    - m77-t1-lessons-labels
    - m77-t2-local-skill
    - m77-t3-taxonomy-route
    - m77-t4-lint-handover
    - m77-t5-gate-service
    - m77-t6-agents-pointer
    - m77-t7-leftovers-carryovers
  done:
    - restored-8090-supervision-owner-chain-verified
    - supervisor-logs-own-end-and-busy-workaround-removed
    - supervision-test-kill-by-pid-restart-11s
    - rotation-to-dot-1-proven-on-spare-port
    - lessons-labels-mapped-to-taxonomy-keys
    - local-handover-executor-skill-written
    - taxonomy-handover-executor-entry-added
    - lint-handover-with-fixtures-and-tests
    - gate-service-with-bare-boolean-check-and-smoke-test
    - agents-md-pointer-and-readme-update-caveat
    - carryover-closures-a25-01-a26-01-03-c22-01-02-04-cr-006
    - progress-active-handoff-cleared
    - analyser-review-of-m77-scripts
  deferred:
    - reboot-test-decision-b-user-gated → a25-02
    - orphan-server-when-supervisor-force-killed → a26-04
    - trap-path-terminating-error-untested → a26-05
    - commit-of-m76-m77-work-not-requested → user decision
  key_fact: "Analyser and parser both pass a bare boolean ($x = false); gate needs a regex check plus a runtime smoke test. Protocol loads lessons by trigger or priority high, not by task_type."

- period: 2026-10-07 to 2026-10-15
  executors: [strata-coder, antigravity-coordinator]
  note: "weekly summary — compacted 10 oldest entries per /acp-commit"
  done:
    - installed-acp-ci-review-integrity-harness (2026-10-15)
    - acp-validate-version-and-pointer-checks, fixed stale current_milestone M1->M75 (2026-10-12)
    - m74-interactive-svg-timeseries-8-timeframes-4-metric-modes (2026-10-12)
    - m73-average-and-peak-throughput-prefill-sparkline (2026-10-12)
    - m72-compact-hud-multi-tab-popout-overlay (2026-10-12)
    - m71-total-tokens-per-request-history-comparison-table (2026-10-12)
    - audit-10-remediations-db-prune-truncation-fix-sqlite-indexes (2026-10-11)
    - decode-speed-surfaced-header-chip-redundant-row-removed (2026-10-08)
    - r3-01-sparkline-per-series-window-label-header-tok (2026-10-08)
    - a7-05-drafts-and-pcie-share-poll-schema-23-col-insert-arity-fix (2026-10-08)
    - audit-7-db-prune-days-rollup-90d-cap-api-export-json-csv (2026-10-08)
    - gpu-2nd-pass-vram-card-relative-gpu-mem-hint-zero-guard-fix (2026-10-08)
    - gpu-vram-derived-from-vram-free-mib-audit-5 (2026-10-07)
    - prefill-gauge-sticky-header-a2-01-telemetry-verified-live (2026-10-07)
    - db-path-resolve-fix-telemetry-status-surfaced (2026-10-07)
  key_facts:
    - "On the AMD HIP driver the engine has NO gpu_* counters; engine.vram_free_mib is live and card-relative, so VRAM is the one recoverable GPU reading (used = fixed card total - free)."
    - "DB_PATH must be .resolve()d — sqlite resolves relative paths against the process cwd."
    - "Static assets are served from disk per request; front-end edits need no server restart, only build_stats changes do."
    - "Engine keeps only 60 samples/series + 12-30 request records and has NO /log endpoint — our SQLite DB is the only durable record."
    - "poll-schema ALTER migrations: INSERT arity bugs are caught by migration tests, not py_compile."
    - "db_prune must prune day rollups too; cap 90d (three months) via db_prune_days."
    - "Windows/Git-Bash process-spawn overhead is ~5-10x a Linux CI host; perf budgets must be host-calibrated (budget=max(2000, 3x measured floor))."


