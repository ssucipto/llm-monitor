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

