# Session Memory
# Format: YAML blocks, last 3 loaded per session, auto-compacted at 15 entries
# DO NOT edit manually — updated by /acp-commit

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


