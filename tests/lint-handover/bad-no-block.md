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
(rules block removed for this fixture)

## Permission
- Allowed: restart the 8090 dashboard with `restart-llm-monitor.ps1` (stops only its own server by PID).
- Not allowed: Strata on 8081 and the gateway on 8080.

## Steps
1. `llm-monitor\service-supervisor.ps1` - change the exit message. Check:
```
$ python -I -c "print('parse ok')"
parse ok
```
PASS: parse check
```
$ python -I -c "print('parse ok')"
parse ok
```

## Stop rules
- Two identical failures: stop that step and write NOT RUN.

## Do NOT
- Do not commit or push.

## What to send back
- Receipts: `agent/tasks/milestone-76-service-robustness/T7-receipts.md`

