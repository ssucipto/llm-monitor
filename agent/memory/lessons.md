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
