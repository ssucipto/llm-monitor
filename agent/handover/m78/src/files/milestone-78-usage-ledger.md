# Milestone 78: Usage ledger (token usage of the orchestrator and the local executor)

**Milestone ID**: M78  
**Status**: in progress  
**Priority**: 1  
**Basis**:
- Homelab B-89 T14 (`D:\Project\Homelab\agent\tasks\b89-delegation-protocol\t14-llm-monitor-usage-ledger.md`);
- ADR-022 D-89-1 A' (Homelab `agent/memory/decisions.md`): the monitor measures and the agent reads only the API;
- audits #93/#94 (Homelab, local).

**Executor**: Strata IQ3_S via the Homelab delegation pipeline (`agent/delegation/`), class `readonly-source` (T1 probation); the orchestrator (Claude) writes the specs and contract tests

## Overview

The monitor gains a **usage ledger**: the token usage of the orchestrator (Claude Code) and of the local executor (Hermes running
Strata) per time window, repo and session. It is served on `127.0.0.1:8090` under the Homelab delegation protocol's usage contract
(`agent/design/local.delegated-execution.md` § Metering, in the Homelab repo). The agent never reads transcripts itself; this
dashboard does, and it keeps **numbers only**.

## Objectives

1. `llm-monitor/usage_ledger.py` (new) holds:
   - ingest of Claude Code usage (`~/.claude/projects/**/*.jsonl`, byte cursor, dedupe on message id + request id);
   - ingest of Hermes usage (`%LOCALAPPDATA%\hermes\state.db`, read-only);
   - storage in its own `usage.sqlite3` (WAL, busy timeout);
   - the contract queries `summary()` and `sessions()`.
2. `server.py`:
   - a daemon ingest thread (60 s, ≤ 5 s of work per tick);
   - `GET /api/usage` (a catch-up ingest of ≤ 10 s first, `partial` when it ran out) and `GET /api/usage/sessions`;
   - HTTP 400 on a bad window.
3. A "Usage" panel in the dashboard: today, 7 days, per repo, orchestrator vs executor, and the weighted unit. A missing source shows "unavailable".
4. Tests:
   - `tests/usage/` (stdlib), run by `run-e2e-tests.sh` through `py -3.12`, else `python3`;
   - synthetic fixtures only (public repo);
   - a content-leak test.
5. Lint: M78 handovers are linted with the Homelab vendored lint (`D:/Project/Homelab/agent/delegation/tools/vendor/handover-write/scripts/lint-handover.ps1 -Repo C:/Project/llm-monitor`). This repo's own `agent/scripts/lint-handover.ps1` (M77) checks against the local skill and stays as it is; the Homelab audit #94 PB-04 idea of replacing it would have broken it (it looks for `..\SKILL.md` beside itself).
6. README "Usage ledger" section (what is read, what is never read, where it is stored), CHANGELOG, `.gitignore` for `usage.sqlite3*`.

## Contract (the summary)

    GET /api/usage?from=ISO&to=ISO[&repo=PATH][&session=ID]
    -> {window:{from,to}, orchestrator:{input,output,cache_write,cache_write_5m,cache_write_1h,cache_read,messages,sessions,models}|null,
        executor:{input,output,cache_write,cache_read,reasoning,sessions,models}|null,
        weighted:{orchestrator|null, executor|null, weights:{input:1, cache_write_5m:1.25, cache_write_1h:2.0, cache_read:0.1, output:5}},
        sources:{claude_code:"ok"|"missing"|"error: ...", hermes:...}, partial:bool, generated_at:ISO}
    GET /api/usage/sessions?from&to[&repo][&session] -> [{source, role:"orchestrator"|"executor", id, start, end, model, repo, input, output, cache_write, cache_read}]

## Handovers (`agent/handover/m78/`; generated with the Homelab tools, captures in Homelab `agent/delegation/runs/`)

| # | Steps | Tier |
|---|---|---|
| H1 | records: this milestone, progress.yaml, `.gitignore`; the contract `tests/usage/test_usage_ledger.py` (24 cases), `expected.txt`, `run-tests.py` | T0 (exact text) |
| H2 | `llm-monitor/usage_ledger.py` as 3 CODE TASK steps (A: iso/parse_window/connect/ingest_hermes; B: ingest_claude; C: norm_repo/summary/sessions); mutation proof with 5 mutants (local bench); `run-tests.py` twice | T1 (readonly-source, probation) |
| H3 | `server.py`: ingest thread, `/api/usage`, `/api/usage/sessions` (exact); the Usage panel (exact); `run-e2e-tests.sh` line; README, CHANGELOG; live checks on 8090 after `restart-llm-monitor.ps1` | T0 |

## Acceptance

- The contract suite passes (one PASS per case), and every mutant is killed.
- Live: `/api/usage` for the H19 window gives executor 39576/9461/741458 (the Homelab audit #91 constants).
- Live: one finished Claude session's orchestrator sum equals that session's `/cost` within 2 % (the owner runs `/cost`).
- `/api/stats` p95 latency (20 calls) is unchanged within 20 %.
- The B-88 transcripts (24–25 Oct) are ingested before Claude Code's cleanup removes them (by 2026-11-20).
