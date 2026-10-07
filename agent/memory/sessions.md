# Session Memory
# Format: YAML blocks, last 3 loaded per session, auto-compacted at 15 entries
# DO NOT edit manually — updated by /acp-commit

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

