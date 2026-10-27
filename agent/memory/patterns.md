# Reusable Code Patterns
# Populated automatically by /acp-commit when patterns are identified
# Format: date-stamped YAML entries, max 60 days active

- date: 2026-10-07
  name: side-channel-path-resolve
  kind: bug-pattern
  problem: |
    A Python server that opens a side-channel file (SQLite, log, cache) with a
    path derived from a relative location silently targets the wrong file when
    the process is started from a different working directory. sqlite raises
    "unable to open database file"; the feature degrades to empty and the UI
    looks like a quiet system rather than a broken one.
  solution: |
    Resolve the path absolutely at import time from the module file, not the
    cwd: DB_PATH = str(Path(__file__).resolve().with_name("telemetry.sqlite3")).
    Then surface the side-channel's status in the payload ({"ok":bool,"error":...})
    and render it, so a disabled channel is visibly distinct from an empty one.
  applies_to: any stdlib-served server.py that opens files beside the script
  guards:
    - test for presence (x != null) not truthiness when 0 is a valid value
    - keep the side channel wrapped so a DB error can never take the app down

- date: 2026-10-08
  name: sqlite-additive-column-migration
  kind: bug-pattern
  problem: |
    Adding a field to a SQLite row schema breaks existing installs. A bare
    INSERT with more columns than the CREATE list crashes on old DBs, and
    py_compile never catches a mismatch between the number of columns, the
    number of `?` placeholders, and the number of value-tuple elements — only
    a live DB round-trip does. Reading a column added by ALTER via COUNT(col)
    can also error, so verify by SELECT * and index.
  solution: |
    Keep the original CREATE unchanged. After opening, run an ALTER loop over
    (col, ctype) pairs: for each, try ALTER ADD COLUMN and swallow the
    OperationalError if it already exists. Extend the INSERT to the new arity
    and keep the export's poll_cols list in lockstep. Count columns ==
    placeholders == values, and prove it with a migration test (old DB -> ALTER
    -> named INSERT) rather than trusting py_compile.
  applies_to: any SQLite-backed side channel that gains telemetry fields over time
  guards:
    - ALTER loop must be idempotent (catch already-exists) so it runs every open
    - keep CREATE, INSERT, and export column lists in one place to avoid drift
    - validate arity with a live DB test, not just a syntax compile

- date: 2026-10-17
  name: fixture-tested-lint-and-state-gate
  kind: verification-pattern
  problem: |
    Parse checks and analyser passes do not prove that a service script works.
    A bare boolean ($x = false) parses and passes PSScriptAnalyzer, yet ends the
    script at runtime under ErrorActionPreference=Stop. A gate of parse-only checks
    passed the defect it was meant to stop.
  solution: |
    Pair every rule-check script with fixtures: one good file that must pass and
    one bad file per rule that must fail for the expected reason, run by a test
    runner. For running services, add a state gate that checks owner chain, task
    settings, file-time versus process-time, and a runtime smoke test on a spare
    port. Record the gate output as evidence.
  example: |
    lint-handover.ps1 with tests/lint-handover/run-tests.ps1 (7 expectations);
    gate-service.ps1 with check G1b (regex for bare booleans) and G10 (spare-port start).
  applies_to: any script or handover claim that says "verified", "supervised" or "fixed"

- date: 2026-10-17
  name: supervisor-owned-cross-session-control
  kind: windows-service-pattern
  problem: |
    A supervisor started by a scheduled task may run in another session (S4U at boot). Its children
    leave the task's job, so a task stop leaves them running, and the desktop can neither read their
    command lines nor stop them.
  solution: |
    The supervisor owns its children: put them in a kill-on-close job (Add-Type, CreateJobObject,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, AssignProcessToJobObject for the wrapper and the server).
    It writes a state file (PIDs, start times, heartbeat) that other tools use to attest the chain
    when they cannot read it, and it honours a stop-request file newer than its own start.
  example: |
    llm-monitor/service-supervisor.ps1 (LlmMonitorJob, Write-State, Test-StopRequested);
    restart-llm-monitor.ps1 (stop request first); gate-service.ps1 G3/G6 (state attestation).
  applies_to: any Windows supervisor run from Task Scheduler, especially S4U or SYSTEM tasks

- date: 2026-10-27
  name: window-correct-rate-and-honest-bound
  kind: telemetry-aggregation-pattern
  problem: |
    A dashboard shows rates whose labels lie. Poll columns hold session-CUMULATIVE
    ratios (hit_pct, accept_pct); averaging them per poll and printing them under a
    "last 60 min" label reports a session figure, and the error varies per snapshot
    so no constant can correct it. Means of instantaneous per-poll rates are dragged
    by idle polls. A rate reconstructed from a token count divided by a timestamp
    from a different request boundary produces physically impossible values (1.9M
    tok/s on a card that decodes at 40), and a max(1e-9, span) sentinel makes the
    zero-span guard unreachable while duplicate timestamps already exist in the DB.
  solution: |
    Three rules, each with its own test:
    1. Window ratio from counters, never from ratios: delta(numerator)/delta(denominator)
       over the span, using a reset-aware segment sum (cumulative_delta) and carrying
       the row just before the span as the delta baseline only.
    2. Rate = movement / span, not a mean of per-poll rates (tok_s_weighted,
       prefill_weighted from a cumulative prompt_ms column). If the column does not
       exist for those rows, publish None rather than guessing.
    3. Bound on PUBLISHED paths only, derive the ceiling from the observed
       distribution (find the natural break, state the % excluded in a comment), set a
       *_bounded flag, and print "· bounded" next to the number. Raw samples stay in
       the DB so an export is still re-derivable. Replace sentinel spans with a floor
       tied to the sampling cadence and return None for any rate it rejects.
    Label every window server-side (mean_window, peak_window) and print it inline so a
    number cannot detach from its meaning.
  example: |
    llm-monitor/server.py: PREFILL_CEILING_TOK_S, SPAN_FLOOR_S, window_pct(),
    bounded_prefill(), the baseline-carry in day_aggregates/db_hour_aggregates,
    throughput.mean_window/peak_window; tests/telemetry/ asserts each rule.
  applies_to: any poll-based telemetry that stores cumulative counters alongside
    per-poll snapshots and publishes means to a UI
