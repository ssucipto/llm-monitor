---
skill: local.handover-executor
version: 1
tier: B-local
updated: 2026-10-17
---

# Skill: handover to an executor (Zed, local models)

## When this applies

Any handover to an executor: any request that says "handover to Zed", or hands work to a local model such as the Strata Coder. Also applies when Claude hands work to another agent in this project.

Pointer: `AGENTS.md` (Local rules) points here. Every handover must pass `agent/scripts/lint-handover.ps1` (exit 0) before the executor starts.

Machine-wide copy: the global skills `handover-write` and `handover-execute` (`%USERPROFILE%\.agents\skills`, source `C:\Project\hermes-workspace\zed-global`, ADR-8 there) carry the same rules block for every Zed project. Keep the two blocks identical. The global lint adds L13 (every step states Expected) and L14 (at most 10 steps); handovers here should pass both lints.

## Rules

<!-- HANDOVER-RULES v1 BEGIN -->
RULES (apply to every step; a violation means STOP and report):
R1. Budget probes: at most two variants per question. If the same probe gives an empty or identical result twice, stop probing and state the verdict.
R2. Helper scripts go in agent/scratch-<milestone>/. Run once. Delete after the output is recorded. Never put probes in agent/tasks/ or agent/milestones/.
R3. Evidence for every claim: a PASS/FAIL/PASS line must be followed by the command and its output, in a fenced block. A claim with no output is marked NOT RUN with a reason.
R4. File time vs process time: before recording a verification, record the file LastWriteTime and the process StartTime. If the file is newer, restart the process and re-run.
R5. Parse AND run: after each edit, parse the file, then run it once on a safe path (free spare port, test fixture, dry run).
R6. Two identical failures in a row: stop that step, write NOT RUN with the reason, and continue only with steps that do not depend on it.
R7. Stop only by PID, after checking the command line matches the target. Never stop a process by name (taskkill, Stop-Process -Name, pkill, kill).
R8. One file per step. Name the file in the step. Do not edit other files in that step.
R9. "Supervised", "fixed", "verified" are claims. They need the evidence from R3 and R4. Without it, write "served but unsupervised", "unverified", or NOT RUN.
R10. Check git claims before writing them (for example "tracked" or "committed"): run the git command and paste it.
R11. Do not commit or push unless the handover says so.
R12. If a step needs a permission the handover does not give, stop and ask in one line.
<!-- HANDOVER-RULES v1 END -->

## Environment notes (Zed, Windows, restricted shell)

These are verified facts from this project. Do not assume anything else.

- Bare `false` / `true` in PowerShell are commands, not booleans. Write `$false` / `$true`. Parsing does not catch this; a runtime test does.
- In permission-protected terminal commands, `$` interpolation can be blocked. Put variable-using code in a `.ps1` file and run it with `-File`.
- Git Bash (MSYS) mangles `/flag` arguments (for example `schtasks /delete`), and `cmd /c "<path>"` can open an interactive shell.
- Scheduled tasks in the admin store (`C:\Windows\System32\Tasks`) cannot be changed from a restricted shell (Access denied 0x80070005). Ask the user to run the elevated command.
- `Start-Process cmd.exe /c "..."` with `-ArgumentList` fails for redirects. Use a `.cmd` file.
- Windows locks a file while any process holds it; a `>>` append then blocks.
- `ThreadingHTTPServer` allows a second bind on the same port unless `allow_reuse_address = False`.
- Children started with `Start-Process` leave the scheduled task's job, so `Stop-ScheduledTask` alone stops only the supervisor (audit-27, tested 18:07). The supervisor therefore puts its wrapper and server in its own kill-on-close job: since audit-27, stopping or killing the supervisor stops its server too (tested 18:13 and 18:16). Do not remove the job code.
- The boot task (S4U) runs in session 0. From the desktop, its processes show no command line, path or start time, and `Stop-Process` on them is "Access is denied" (tested 18:09). Identify them through `%LOCALAPPDATA%\LLMMonitor\service-<port>.state.json`; stop them only through `stop-<port>.request` (which `restart-llm-monitor.ps1` writes).
- A supervisor that finds our server with no live supervisor above it (an orphan) stops it by PID and takes over (tested 18:06 on 8098, 18:14 on 8090).
- PSScriptAnalyzer and the parser do not catch a bare boolean. Use the gate's G1b check (syntax tree: a bare `true`/`false` is a command call) and a runtime smoke test.
- A "verified fact" in this list needs the test that proved it. The first version of this list said `Stop-ScheduledTask` stops the child server; it did not (audit-27).

## Model fit

- Mechanical edits with an exact anchor: any model.
- Process state, supervision, concurrency, or anything that touches running services: a stronger model, or a line-by-line review before the result is accepted.
- If you are unsure which line to change, stop and write the question in the receipts. Do not guess.

## Required sections of a handover

A handover that the lint accepts must contain:

1. Front matter with keys `handover_version`, `handoff_mode`, `from_executor`, `to_executor`, `date`, `status` (and `git_commit` when the repo state matters).
2. The rules block, copied verbatim from the `## Rules` section above (version v1).
3. `## Permission` — what may be restarted or stopped, named by port. Name the forbidden ports too.
4. `## Steps` — one file per step, named in backticks.
5. `## Stop rules`.
6. `## Do NOT`.
7. `## What to send back` — with a receipts path under `agent/tasks/`.

## Template

```markdown
---
handover_version: 1
handoff_mode: executor
from_executor: claude
to_executor: zed
date: YYYY-MM-DD
status: active
git_commit: <output of git rev-parse HEAD>
---

# Handover: <title>

## Rules
<paste the rules block R1–R12 from this skill, between the HANDOVER-RULES markers>

## Permission
- Allowed: <action, port, script>
- Not allowed: <port or action>

## Steps
1. `<file>` — <one change>. Check: <command>. Expected: <output>.
2. ...

## Stop rules
- Two identical failures: stop that step, write NOT RUN.
- <milestone-specific stop rules>

## Do NOT
- Do not commit or push.
- Do not kill by name.
- <milestone-specific>

## What to send back
- Receipts: `agent/tasks/<milestone>/<receipts>.md`
- Each step: PASS / FAIL / NOT RUN, with the command and its output.
```

## Changelog

- v1 2026-10-17: initial (M77 T2).
- v1 2026-10-17 (audit-27): environment notes corrected (task stop vs job, session 0, orphan takeover, G1b method). Rules block unchanged, so handovers built on v1 stay valid (lint L4).
