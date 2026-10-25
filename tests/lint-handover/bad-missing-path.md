---
handover_version: 1
handoff_mode: executor
from_executor: claude
to_executor: zed
date: 2026-10-17
status: active
git_commit: 86ad22bc8d62b9f89e91daf90728b0baefae10d1
---

# Handover: fixture

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

## Permission
- Allowed: restart the 8090 dashboard with `restart-llm-monitor.ps1` (stops only its own server by PID).
- Not allowed: Strata on 8081 and the gateway on 8080.

## Steps
1. `agent/nope-does-not-exist.md` - change the thing. Check: none.

## Stop rules
- Two identical failures: stop that step and write NOT RUN.

## Do NOT
- Do not commit or push.

## What to send back
- Receipts: `agent/tasks/milestone-76-service-robustness/T7-receipts.md`

