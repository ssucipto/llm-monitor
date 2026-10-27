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

- date: 2026-10-27
  name: versioned-default-state-migration
  kind: design-pattern
  problem: |
    A product ships a default arrangement (panel order, layout, column set) that
    users can override, and the override is persisted in localStorage. Changing
    DEFAULT_ORDER then does nothing for existing users: restoreOrder honours the
    save, so the change is invisible to exactly the people who asked for it.
    Bumping the storage key fixes it but destroys their order with no notice.
  solution: |
    Version the saved state. persistOrder writes v: ORDER_VERSION; restore honours
    a save whose v matches EXACTLY and replaces anything else with the defaults,
    re-saving immediately at the current version. The replacement must be announced
    in the same place the user can undo it (a note beside Save/Reset, with Dismiss),
    and Reset clears the note. Legacy shapes migrate by arriving version-less. Never
    discard a current-version save.
  example: |
    llm-monitor/app.js: ORDER_VERSION, persistOrder(), restoreOrder(),
    noteLayoutReplaced() + #layout-note; test_ui_browser.py
    layout-version-migration plants a reversed version-less save and asserts the DOM
    matches the defaults, the note is visible, and the payload is re-saved at v2.
  applies_to: any persisted user arrangement that the product later re-prioritises
  guards:
    - assert the initial markup order equals the JS default order (pre-JS fallback drift)
    - when a region shrinks, re-measure its count/geometry assertions in the same commit

- date: 2026-10-27
  name: deterministic-harness-for-a-live-dependent-app
  kind: testing-pattern
  problem: |
    A dashboard's test harness starts the REAL server, which talks to a live upstream
    (an inference engine on a fixed port). So every value assertion depends on what the
    upstream happens to report at run time, and on a CI runner with no upstream the whole
    payload degrades to nulls so only structural checks can say anything. Worse, the test
    server writes into the PRODUCTION history file, so the suite pollutes the data it is
    meant to observe, and fixed sleeps before geometry reads make runs flaky.
  solution: |
    Make the upstream source overridable at the single boundary that talks to it, and
    fail loudly when the override is unusable. (1) ENV override for the persistence path
    so no test writes production rows; assert the production row count is UNCHANGED by a
    full suite run - that measurement is the proof. (2) ENV override pointing at a pinned
    document that answers the same function the live path uses; an unset key in the
    document returns the same shape as "endpoint unreachable" so fixtures may be partial;
    an unreadable fixture aborts startup (SystemExit) rather than silently testing the
    live upstream. Give the fixture values the real host CANNOT produce, which is what
    makes the measured code path reachable in tests at all. (3) Replace every
    read-after-change sleep with an in-page stamp the app already sets at the end of each
    pass (layout, render, fetch, render-of-chart, secondary fetch), then poll a predicate.
    Where a fetch is throttled, wait for the FETCH stamp and THEN the render stamp, or a
    later re-render of stale data satisfies the wait.
  example: |
    llm-monitor/server.py: DB_PATH/USAGE_DB overrides, FIXTURE_PATH + _get_json's
    `if _FIXTURE is not None: return _FIXTURE.get(path)`, SystemExit(2) on a bad fixture;
    agent/tests/ui/fixtures/engine.json; test_ui_browser.py settle/settle_spans/
    settle_render/settle_usage/settle_chart + SPANS_SIG; app.js __lastLayout,
    __lastRender, __lastChartFetch, __lastChartRender, __lastUsage; static checks
    telemetry-db-isolated, engine-fixture-honoured, geometry-read-settled.
  applies_to: any harness that drives a real server whose upstream is live, host-specific
    or absent on CI
  guards:
    - a page-level fetch fixture survives navigation: keep the identifier and remove it
      before a check that needs the server's own answers
    - capture the "before" value BEFORE the action; a settle baselined afterwards passes
      or fails on nothing
    - a secondary fetch that rewrites text grows its tile after load, so geometry waits
      must require layout >= max(all content stamps), not just newer than the viewport change
    - app.js is <script type=module>: its consts are module-scoped and unreachable from
      CDP Runtime.evaluate; expose window stamps for observables, parse the source for consts
