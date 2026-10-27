# Correction Log — Filtered by task_type before loading
# Populated automatically when developer says "log it" or "wrong, log this"
# Max 5 entries loaded per session, filtered to current task_type + priority:high

- date: 2026-10-17
  task_type: bug-fix-simple
  mistake: "PowerShell `$flag = false` (bare word) is a command call, not a boolean. Under $ErrorActionPreference = Stop it throws and ends the script. Found in service-supervisor.ps1 line 155."
  correction: "Write $false and $true. After any edit, parse the file AND run it once on a safe path (for example a free spare port). A clean parse does not prove the script runs."
  priority: high

- date: 2026-10-17
  task_type: bug-fix-architectural
  mistake: "Verified a supervisor on an older version of the file. The file changed after the test (file 00:47, process started 00:39), so the receipts described code that was no longer on disk."
  correction: "Before recording a verification, note the file's LastWriteTime and the process StartTime. If the file is newer than the process, restart the process and re-run the check. Never record a result for code you have not run from disk."
  priority: high

- date: 2026-10-17
  task_type: bug-fix-architectural
  mistake: "Stacked 91 near-identical probe scripts (t7-*.ps1) to chase one question. The user had to ask 'are you stuck?'"
  correction: "Budget two probe variants per question. If the same probe returns nothing twice, change approach or state the verdict. Keep one-shot helpers in one scratch folder and delete them when done. Never leave probes in a task folder."
  priority: high

- date: 2026-10-17
  task_type: bug-fix-simple
  mistake: "Installer header says 'needs no administrator rights' but the boot task registration needs elevation."
  correction: "Make documentation match behaviour. Verify each claim with the real command before writing it down."
  priority: normal

- date: 2026-10-17
  task_type: bug-fix-architectural
  mistake: "A skill listed 'Stop-ScheduledTask stops the child server' as a verified fact; no test had run it. The server survived as an orphan, and under the S4U boot task the desktop could not even see or stop it."
  correction: "Every 'verified fact' needs the test that proved it, with the time. For process lifecycle, test the real path (task stop, cross-session) instead of the convenient one (kill by PID in the same session)."
  priority: high

- date: 2026-10-17
  task_type: handover-executor
  mistake: "A gate and a lint written to enforce rule R7 broke R7 themselves (unchecked PID stops in G10) and missed the incident's own pattern (Get-Process python | Stop-Process); their fixtures were pinned to the current HEAD."
  correction: "Test a checker against the exact incident it exists for, give each bad fixture exactly one expected failure, and keep fixtures independent of the live repo state (pass HEAD in)."
  priority: high

- date: 2026-10-27
  task_type: testing
  mistake: "Wrote a browser assertion for a collapsible <details> as 'the table must have zero height when the fold is closed'. It failed on correct code: Chrome hides a closed details body with content-visibility on the ::details-content pseudo-element, so descendant elements keep their layout boxes and still report a rect."
  correction: "For a collapsed <details>, assert on the fold element's own height (it collapses to its summary line) or on getComputedStyle(details, '::details-content').contentVisibility — never on a descendant's getBoundingClientRect. Verify which mechanism the browser actually uses by printing diagnostics (contentVisibility, ::details-content display, offsetParent) instead of guessing at the CSS. Also: when a change shrinks a region, re-measure every count/geometry assertion over that region in the SAME commit; a currently-green check is not a safe carryover."
  priority: high

- date: 2026-10-27
  task_type: testing
  mistake: "Tried to read an app.js constant from CDP with Runtime.evaluate('DEFAULT_ORDER.tiles'). app.js is loaded as <script type=module>, so its top-level consts are module-scoped and unreachable; the expression returned undefined and the assertion would have compared against nothing."
  correction: "Do not reach for a module's internals to state an expectation. Parse the shipped source in the test (re over 'const DEFAULT_ORDER = {...}') and assert the live DOM against what the FILE says — that is both possible and stronger, because it also catches markup drift. Related: after re-ordering DOM blocks by hand or script, add a check that the initial markup order equals the JS default order; otherwise the pre-JS fallback silently diverges from the arranged page."
  priority: normal

- date: 2026-10-27
  task_type: testing
  mistake: "Wrote an assertion as `assert (A if cond else B), msg` where `cond` could never be true, so only one branch ever ran; and in the same check I read a DOM readout AFTER a later input event, so it compared the wrong state. The check reported PASS while asserting almost nothing."
  correction: "Never encode an either/or inside a single assert — write one assert per claim. If a fallback regex is needed, put it in its own assert with its own message. When a check drives several inputs (End, ArrowLeft, Home), capture every observable at the moment it is supposed to be true, not at the end of the sequence. Cross-asserting two independent readouts (aria-valuetext vs the visible line) is what makes 'the wrong value reached the UI' detectable; asserting each against a regex alone lets both be wrong together."
  priority: high

- date: 2026-10-27
  task_type: testing
  mistake: "Wrote an assertion as `daily[-1].get('prefill_max') is not None`. The fixture had no polls on 'today', so db_daily returned no today entry at all and daily[-1] was the FROZEN row — the assertion checked the wrong object and passed green. It only became real once the fixture seeded today and the expected value was pinned to an exact number."
  correction: "Never assert through a positional pick (list[-1], rows[0]) when the element's existence is what you are testing. Select it by its key (d['d'] == TODAY) so a missing element raises rather than silently substituting, and pin an exact expected value instead of `is not None`. Also check the fixture actually creates the branch: a live 'today' aggregate needs polls whose timestamps fall inside (day_start, now) — anchor them as fractions of the elapsed day so the test cannot break just after midnight UTC."
  priority: high

- date: 2026-10-27
  task_type: testing
  mistake: "Wrote an assertion for 'the hourly path bounds impossible prefill readings' as server.bounded_prefill([300.0, 1_210_150.0])[1] == 300.0 — it tested the helper, not db_hour_aggregates. It passed green even with the bound removed from the hour path, because the helper was still correct."
  correction: "An assertion about a code path must assert on that path's own returned record. For every 'X happens in function F' check, call F and inspect F's output; mutating F's body MUST turn the check red. Prove it by deleting the call inside F, not by testing F's helper in isolation. (Found here by actually running the mutation: prefill_max 1210150.0 sailed through.)"
  priority: high

- date: 2026-10-27
  task_type: bug-fix-simple
  mistake: "Replaced a key's value in a Python dict literal while the old line was still present, so the dict had the key twice and the LAST one won — the fix did nothing and only a test caught it. Later in the same task, a new aggregate key was added whose SELECT never fetched the column it needed, shipping a permanent None stub that looked implemented."
  correction: "After any key-replacement edit in a dict literal, scan for duplicate keys with an AST walk (ast.Dict over the module, count Constant str keys) — py_compile and grep both miss it. When adding a computed key, add its source column to every SELECT that feeds it and assert the value is non-None in a fixture whose counters actually move; a None stub passes any 'is None or close' test."
  priority: high

- date: 2026-10-17
  task_type: bug-fix-simple
  mistake: "restart-llm-monitor.ps1 used foreach ($pid_ in Get-OurOwners) { Stop-Process -Id $pid_ } without parentheses; PowerShell ran the call as a bare statement and iterated an EMPTY stream, so no process was ever stopped."
  correction: "In foreach ($x in <expr>), a bare command invocation is parsed as a statement, not a piped value. Assign first ($owners = Get-OurOwners) or wrap in parentheses, then iterate the variable."
  priority: high

- date: 2026-10-26
  task_type: cross-cutting
  mistake: "Deleted the whole agent/ tree. A scratch folder had been created at llm-monitor/agent/scratch-m80 (inside the app dir); to remove it I called the delete tool on the parent-looking path llm-monitor/agent, which resolved to the repo-root agent/ directory. Everything gitignored under it (reports, tasks, milestones, sessions, tests/ui) was unrecoverable — GitHub held only the 405 tracked files."
  correction: "Delete only the exact leaf you created, never a parent or a path you typed from memory. Before any delete_path on a directory: (1) list_directory that exact path and confirm its contents are only your scratch files, (2) confirm it is not a tracked or gitignored-but-valued tree, (3) prefer deleting the single file by full path. Never assume a directory name is unique — llm-monitor/agent and <repo>/agent both exist here. Scratch folders go in agent/scratch-<task>/ at the repo root and are named in the same message that creates them."
  priority: high

- date: 2026-10-26
  task_type: cross-cutting
  mistake: "Work that took a whole session (the tests/ui suite, M79/M80 records) lived only in gitignored paths, so one bad delete destroyed it. There is no backup of agent/ anywhere on the machine."
  correction: "Code that gates CI must be tracked: agent/tests/** is test code, not a report body, and belongs in git (add an exception in agent/.gitignore or move it under tests/). Before finishing any session that writes new tooling, state whether it is tracked and show git status."
  priority: high

- date: 2026-10-26
  task_type: testing
  mistake: "Restored progress.yaml from HEAD after the accidental delete and treated it as correct, which silently resurrected stale rows: task-78-h2/h3 were status: pending although M78 shipped in 0.1.13-0.1.15, and active_handoff pointed at a report file that no longer exists. acp-validate.ts cannot catch either (it checks milestone-doc Status vs the milestone entry, and never reads active_handoff)."
  correction: "After restoring any records file from git, verify its SEMANTICS against shipped evidence, not just its structure: every task row's status must agree with CHANGELOG/commits, and every path pointer must resolve on disk. Grep for pointers (active_handoff.path, file:) and test each one with a real exists check. A validator passing does not mean the records are true."
  priority: high

- date: 2026-10-26
  task_type: testing
  mistake: "Shipped three new browser checks as if they were coverage. One (reload-restores-order) would have compared the PRE-reload DOM, because document.readyState can still report 'complete' on the old document right after Page.navigate. Another (view-toggle-spans) turned out to be unfailable: with both the explicit layout call and the ResizeObserver removed, nothing sets gridRowEnd:auto, so it can never go red."
  correction: "Every new assertion gets a mutation attempt in the same session. If it cannot be made to fail, say so in the report and the task doc instead of implying coverage. When a test reloads a page, prove the document is fresh (set window.__sentinel before navigating, poll until it is gone) — never trust readyState alone."
  priority: high
