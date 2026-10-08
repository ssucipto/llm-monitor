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

