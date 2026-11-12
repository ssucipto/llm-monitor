# Session Memory
# Format: YAML blocks, last 3 loaded per session, auto-compacted at 15 entries
# DO NOT edit manually — updated by /acp-commit

- date: 2026-11-12
  executor: hermes
  branch: main
  tasks:
    - "M82/M83 commit+push close-out (user go-ahead)"
    - "a33-37 status verification (already fixed by M82-T2)"
    - "GPU temp/PCIe counter probe (M81 follow-up) -> audit-40"
    - "a25-02 reboot-test closure on real receipts"
    - "housekeeping: recurring_tasks fields, wiki check, scratch folders"
  done:
    - "committed+pushed the M82/M83 tree as cacbc1b (feat, 17 files) + a6b988f (fix(ci), 10 files); pushed 97ccbe1..a6b988f to origin/main; version 0.3.0 -> 0.4.0 with CHANGELOG entry; M83 task rows corrected not_started -> completed 2026-11-06"
    - "fixed the CI harness for git-bash on Windows: MSYS paths were handed to native python everywhere (acp.ci.sh died on ci.yml; review-measure recall 16.7% with analyzers dead silently via 2>/dev/null; run-e2e-tests.sh crashed on py). _native_path() cygpath helper added in acp.integrity-output.sh + acp.ci.sh/ci-validate.sh/review-measure/run-e2e-tests; fixed mktemp.XXXXXX.ts probe bug in acp.ci-steps.sh (latent: CI sets ACP_REVIEW_PERF_BASELINE_MS and skips it); ci-validate.sh CRLF -> LF"
    - "gates after fixes, all from bash: acp.ci.sh --fast PASS 6/6 · --static PASS 3/3 · run-e2e-tests.sh 5 passed (ui browser 31/31 + static 20/20, telemetry 52+25+29, usage) · acp-validate.ts PASS 0 warnings · shellcheck --severity=error clean on all touched scripts (3 SC2034 in review-scan proven pre-existing by checking HEAD copy in place)"
    - "a33-37 verified CLOSED, not re-implemented: carryover says fixed 2026-11-06 (M82-T2) and server.py gather_log() autodiscovers strata-*.log via engine-active.txt; the stale next_step predated the carryover update — removed"
    - "audit-40 (GPU temp/PCIe probe): driver 32.0.32015.7029 dated 2026-11-10-18 is current; no NVML, no MSAcpi_ThermalZoneTemperature instances, no AMD WMI namespace, no ADL SDK, GFXINFO unloadable -> verdict: no counter source on Windows, honest '--' stays; carryover a40-01 wontfix-until-trigger"
    - "a25-02 CLOSED on real receipts: machine rebooted 2026-11-11 22:54:28; service-8090.state.json shows supervisor pid 3656 in SESSION 0 started 22:54:39 (+11 s post-boot, pre-login), server pid 9040 at 22:54:41, heartbeat alive 39 h; service-8090.log lines 461-462 + the 23:08:57 first-login 'already served, exit 0' line; :8090 HTTP 200 with pid 9040 confirmed 2026-11-12"
    - "housekeeping: weekly-code-review recurring task fields populated honestly (last_run 2026-10-28 = review-015, status overdue -> surfaces via step 4.5); wiki/architecture.md was already filled by the M82 session (stale note corrected); the nine empty agent/scratch-* folders no longer exist on disk"
  deferred: []
  key_fact: "A reboot test can be closed without rebooting anything: LastBootUpTime + the state file's supervisor_session:0 timestamp + the first-login 'already served' log line is a complete receipt chain, and it was sitting in %LOCALAPPDATA%/LLMMonitor for a day while the carryover still said pending. Records drift faster than code — re-check every 'still open' claim against the machine-readable source before repeating it."
  correction_a40-02: "M83 records say second adapter 'GTX 1660 6GB'; live /api/stats and Win32_VideoController enumerate RX 7900 XTX + RX 6800 XT (DEV_73BF), no NVIDIA device present. VRAM-descending sort unaffected."

- date: 2026-11-06
  executor: antigravity-coordinator
  branch: main
  tasks:
    - task-83-t1
    - task-83-t2
    - task-83-t3
    - task-83-t4
  done:
    - dual-live-speed-gauges-in-header-with-dedicated-decode-bar-and-scale-label
    - dynamic-decode-p95-ceiling-calculation-with-hysteresis
    - engine-branding-cleanup-from-strata-coder-to-strata
    - multi-gpu-vram-descending-sorting-selecting-rx-7900-xtx-as-primary
    - multi-gpu-hardware-formatting-displaying-both-rx-7900-xtx-and-gtx-1660
    - modern-hud-navigation-pill-bar-preserving-all-16-panel-anchor-ids
    - audit-37-investigation-and-audit-38-pre-impl-readiness-reports
    - audit-39-post-impl-audit-and-review-017-coderabbit-style-report
    - 100-percent-pass-across-ui-telemetry-usage-suites-and-acp-ci-fast-gates
  deferred: []
  key_fact: "On multi-adapter rigs, OS enumeration order can place smaller or secondary display cards ahead of primary compute accelerators. Sorting detected adapters by VRAM descending guarantees that the compute card (24 GiB RX 7900 XTX) drives primary metrics and derived VRAM calculations, while formatting the full array surfaces complete system topology. In the UI, dual live bars with distinct color gradients (cyan/purple for decode, emerald/green for prefill) provide immediate visual feedback during inference."

- date: 2026-11-06
  executor: antigravity-coordinator
  branch: main
  tasks:
    - task-82-t1
    - task-82-t2
    - task-82-t3
    - task-82-t4
  done:
    - autonomous-15s-telemetry-background-daemon-with-lock-and-cooldown
    - live-strata-log-autodiscovery-and-tailing-per-engine-active-txt
    - strata-architectural-knobs-surfaced-in-api-and-engine-card
    - gate-service-session0-pid-resolution-and-empty-state-listening-socket-handling
    - cross-volume-drive-agnostic-server-commandline-matching
    - test-telemetry-days-dynamic-utc-month-anchor-drift-fix
    - test-telemetry-analysis-sqlite-delete-commit-and-daemon-assertions
    - audit-34-investigation-report-and-audit-35-pre-impl-report
    - audit-36-post-impl-audit-and-review-016-coderabbit-style-report
    - acp-ci-fast-tier-pass-6-of-6-gates
  deferred: []
  key_fact: "Telemetry ingestion ceased when client browser closed because telemetry() was only triggered on GET /api/stats. Adding a 15s daemon thread with _TELEMETRY_LOCK and rate limiting guarantees 24/7 background telemetry rows without UI dependence or lock contention. Furthermore, non-elevated Get-NetTCPConnection queries mask Session-0 listening sockets as OwningProcess 0 with empty State, requiring state-file fallback and 0.0.0.0:0 checks."

- date: 2026-10-29
  executor: zed
  branch: main
  tasks: ["service restart (:8090)", "M81 follow-up close-out: acp-validate (full) + acp-sync + acp-update + acp-commit + git-commit + push"]
  done:
    - "cycled the :8090 monitor through its scheduled task: stopped supervisor PID 34952 then listener PID 26648, each only after printing its Win32_Process command line; verified DOWN (no listener on 8090, HTTP connect failed) before Start-ScheduledTask brought it back as supervisor 38012 / server 25328 with GET / and /api/stats both 200"
    - "the supervisor-first order was required, not stylistic: the supervisor respawns the server, so killing only the :8090 listener gets undone in seconds. Stop-ScheduledTask alone reported Status: Ready while the child still held the port, so the port check is the real evidence"
    - "Strata's process matched the server.py name pattern and was excluded by its command line (--port 8081); :8080 gateway PID 14852 and :8081 PID 17396 verified still listening afterwards"
    - "validate beyond the trimmed validator: acp-validate.ts PASS (version 0.3.0 == CHANGELOG, no dangling pointers, no status drift, 0 warnings) and acp-validate.test.mjs 1/1; manual step 2g clean (sessions 17 / lessons 24 / patterns 9 / audit-carryovers 95 entries, 0 duplicate-key entries; progress.yaml parses strictly); steps 1 and 2d clean (all agent/ dirs present, 5 recurring tasks schema-valid)"
    - "constraints.yml has NO hooks block, so the ADR-20 hook-binding half of step 2g is inert in this repo — recorded rather than reported as a pass"
    - "threw away two false findings from my own probe before reporting them: a parity probe demanded .github/prompts + .cursor/commands + .claude/commands wrappers, but those directories do not exist at all here (this repo ships only .opencode/commands), and its sessions-key regex was wrong because date: sits on the - date: line itself. The repo's authoritative validator passes clean"
    - "sync: README agrees with server.py on all six endpoints (/api/stats, /api/export, /api/export.csv, /api/timeseries, /api/usage, /api/usage/sessions); DB_MAX_ROWS 20000 and the ~90 day DB_DAILY_MAX prune match the docs; framework version 6.40.0 consistent across AGENTS.md, CLAUDE.md, copilot-instructions.md and manifest.yaml"
    - "noted, NOT fixed: recurring_tasks have last_run/next_due/status all commented out, so the step 4.5 overdue check can never fire here; agent/wiki/architecture.md is still the unfilled bootstrap template; nine empty agent/scratch-* folders from earlier milestones are still on disk"
    - "progress.yaml: recent_work entry for the service cycle + full validate/sync, documentation.last_updated stamped 2026-10-29; no routing tasks exist in this repo (only route-template.md) so there was nothing to auto-stamp completed"
  deferred:
    - "a33-37 (Strata/llama log tailing) -> its own task, unchanged"
    - "recurring_tasks cadence fields are commented out -> either populate last_run/next_due or drop the block so the overdue check stops being inert"
    - "nine empty agent/scratch-* folders + agent-scratch-old-server.py left in place (not ours to delete unasked)"
  key_fact: "A scheduled task's Status: Ready tells you nothing about its children. The evidence that a service is down is the absence of a listener on its port plus a failed HTTP request, and the stop order must be supervisor-then-listener or the respawn undoes the kill. Also: a probe that reports 75 errors can be the bug - when every finding is 'missing wrapper directory', check whether the convention applies to this repo at all before believing it."

- date: 2026-10-29
  executor: zed
  branch: main
  tasks: ["M81 close-out: acp-validate (full) + acp-sync + acp-update + acp-commit + git-commit + push"]
  done:
    - "ran /acp-validate to its command doc, not just scripts/acp-validate.ts. The .ts in this repo implements only version/pointers/status; steps 1, 2, 2c-2g, 5, 9, 10, 11 were run separately (agent/scratch-m81-close/v2g.py + vrest.py, deleted after use)"
    - "found and fixed 3 real defects the trimmed validator cannot see, all in tracked records: patterns.md did not parse as YAML at all (the M81 guards list starts with a quoted word, so YAML read the item as a double-quoted scalar - rewritten as >- folded items); audit-carryovers.md line 726 had C:\\Project\\Strata inside a double-quoted scalar, and \\P is an unknown escape (backslashes doubled); agent/index/acp.core.yaml's path-null note was missing the required rationale: field"
    - "both memory files now whole-file parse; strict-YAML duplicate-key scan over sessions/lessons/patterns/audit-carryovers is clean; progress.yaml parses strictly; 5 recurring tasks schema-valid; namespaces clean; index 15/20 entries valid; 0 broken milestone links"
    - "acp-sync: no specs and no acp.meta-scan.sh in this repo, so the marker/traceability steps (1.3-1.6) had no data - recorded rather than faked. Documentation counters verified accurate (34 task docs, 10 milestone docs)"
    - "README drift fixed: GET /api/timeseries (shipped in M74) was never documented. Added with the eight UI ranges (the endpoint also accepts 12h), the four metric tabs and the exact payload shape read off db_timeseries; corrected my own first draft, which claimed nine ranges and a prefill mode that does not exist as a tab"
    - "noted, NOT fixed (out of scope): agent/wiki/architecture.md is still the unfilled bootstrap template from the bootstrap commit"
    - "progress.yaml: new recent_work entry for this close-out; sessions.md now 14 entries (under 15, no compaction); no routing tasks exist in this repo (only route-template.md), so there was nothing to auto-stamp completed"
  deferred:
    - "a33-37 (Strata/llama log tailing) -> its own task, unchanged"
    - "agent/wiki/* is still bootstrap template content (architecture.md last_verified: YYYY-MM-DD literal) -> needs a decision on whether the wiki layer is used at all here"
  key_fact: "A green scripts/acp-validate.ts does NOT mean /acp-validate passed. The .ts covers version + pointers + status only, so memory files that do not parse as YAML at all, and index entries missing required schema fields, sit invisible behind a PASS line. Run the command doc's steps, not just its TypeScript subset - and remember a double-quoted YAML scalar treats backslashes as escapes, so any Windows path inside one needs doubled backslashes (or a single-quoted/folded scalar)."

- date: 2026-10-29
  executor: zed
  branch: main
  tasks: ["review-015 rounds 3 and 4 (self-review of the round-2 and round-3 fixes)"]
  done:
    - "R3 server: weighted_prefill_rate returns None when the counters disagree (was a fake 0.0), when a decrease is invisible to prompt_ms (was 10,000.0 vs an honest 1,000) and when the rate exceeds PREFILL_CEILING_TOK_S (was 9,001,000.0); HOUR_SPAN_MAX_S = 3600 bounds the PRODUCED span rather than the row's age"
    - "R4 server: moved the disagreement guard into window_pct, where all six rate call sites share it - a 250% cache-hit rate was publishable. Pinned the HOUR_SPAN_MAX_S boundary both ways (3600 kept, 3601 dropped) so flipping > to >= is visible"
    - "R4 flake root-caused by measurement: agent/scratch-m81-rv3/flake.py sampled the page every 100 ms after a real fold click and saw span 123 -> 24 within ~100 ms in 3/3 runs; 123 is exactly ceil((480 + 12) / 4), the span for the panel while the fold was OPEN. The product self-heals; the TEST was confirming a mid-race state"
    - "Rejected a subagent's recommendation to re-drive layout passes in app.js: its 'persists indefinitely' claim is disproved by that probe, and my first attempt contained an in-pass check that re-read the measurement it had just written (the same unfailable-assertion trap as D-015-09). app.js layout engine unchanged"
    - "settle fix in the suite: SPANS_SIG flags a span that no longer brackets its tile's height (and a tile left at auto with height); settle_spans refuses to return while the marker is present. Proven deterministically by prove_stale.py, which forces span 123 on an 83px panel and shows the pre-fix rule accepts that as settled"
    - "R4-1 (high): the A5 payload guards had NO coverage - deleting both left the suite green. New browser check usage-payload-missing-keys; reverting either guard now fails with '--' and 'unavailable (Cannot read properties of undefined (reading claude_code))'"
    - "R4-2 (high): dayName() fixes aria-valuetext, the selected-day line and the offline fallback label, all of which read .date unguarded. The new check FAILED on shipped code ('undefined, day 11 of 11') before the fix existed"
    - "R4-3: the widened SERIES rule anchored ': 0' at end of line, so '? b.x : 0))' slipped through (rule_check.py). Anchor dropped; a : 0 fallback now fails chart-disclosure-honest"
    - "Corrected my own S3 docstring, which claimed the day path was immune because it charges no cumulative totals to a gap - false: day_aggregates publishes prompt/reused/output deltas over [base] + rows. No day-path change; that attribution is what a day rollup is for"
    - "HOUR_BASELINE_MAX_AGE_S recorded honestly as a scan limit, not a correctness rule: every baseline it admits also passes the span test, so deleting it turns no test red"
    - "R3-S7 kept as a FALSE POSITIVE (mutation against pre-round-2 code fails it with 3000.0, so it does discriminate); db_daily's conditional prefill_note is by design"
    - "counts: browser 28 -> 31, telemetry analysis 41 -> 50, static 20 unchanged; expected.txt bumped in the same commits. Six round-3 server mutations plus six round-4 mutations proven, all reverted (each driver prints restored: True)"
    - "the :8090 service was down at session start; Start-ScheduledTask -TaskName LLMMonitor brought it up (HTTP 200), so it now runs the round-3 server.py"
    - "commits 294e248 (server) and 2ffccbe (app + UI suite); the split verified bisectable by stashing the UI half and re-running the previous suite green at 28/28. NOT pushed - not authorised"
  deferred:
    - "a33-37 (Strata/llama log tailing) -> its own task, unchanged"
  key_fact: "A STABLE read is not a CORRECT read: two identical geometry reads only prove the page stopped working. A stale row span is perfectly stable, so a settle built on identical reads validates the mid-race layout instead of waiting past it - flag the invariant (span brackets height) in the signature, not just the values. And bound the quantity you actually publish (the span), never the proxy you thought about (the row's age)."

- date: 2026-10-28
  executor: zed
  branch: main
  tasks: ["review-015 round 2 (self-review of 36ec53a..66b8711)"]
  done:
    - "D-015-01 (high, a regression the previous commit introduced): fetchUsage read u after the for loop that declared it, so every successful usage fetch threw ReferenceError and the Sources row printed 'unavailable (u is not defined)'. Fixed with let last = null hoisted above the loop; the wrote guard was deleted as dead code because it is true on every reachable path"
    - "D-015-02 (high): my own weighted_prefill_rate filtered BOTH sides of the ratio to prompt_ms-bearing rows, deleting the NULL middle row cumulative_delta uses to segment counter resets, so the rate collapsed to a fake 0.0 - worse than the inflation it replaced. The shared thing is the TIME SPAN, not the row list"
    - "D-015-03: db_hour_aggregates still had an unbounded baseline after the day path was bounded; a one-hour window reported span_s = 173,400 (~48 h). HOUR_BASELINE_MAX_AGE_S = 3600"
    - "D-015-04: double-quoted 'day ${i + 1}' printed the raw placeholder; new static rule rejects any double-quoted literal containing a dollar-brace"
    - "D-015-05: the today day-branch omitted prefill_note and the test only asserted the string appeared somewhere; key added and the test now compares KEY SETS across all three day branches"
    - "D-015-06: per-child Detail wiring missed panels dragged in later; replaced by one delegated listener on .tiles--detail after verifying in the HTML spec that beforematch bubbles"
    - "D-015-07: the || 0 static rule had gone dead after the SERIES refactor (passed vacuously); re-pointed at the SERIES map. D-015-08 S1 fallback says 'rate n/a'; D-015-09 pins the rounding invariant instead of a fixture literal"
    - "new checks: browser chart-null-value-is-a-hole, usage-ledger-renders, detail-wiring-follows-the-region, per-bar hover title in history-bars, prefill line drawn to the disclosed peak; static gains the dollar-brace rule and the null-safe/offline/derived-wiring rules. Counts browser 28, static 20; telemetry 41/25/27"
    - "10 round-2 mutations proven. Lesson: mutation drivers must invoke the INDIVIDUAL suite files, not run-tests.py, which truncates a failing suite to its last 20 lines and made one probe report NOT PROVEN falsely"
    - "review-015 extended with the round-2 findings table and validation block; corrected its stale S-015-04 probe figure to the proven 3000.0 inflated vs 1000.0 honest"
    - "gates re-run green at 66b8711: ui 28/20 PASS · telemetry rc_all=0 · usage rc_all=0 · run-e2e-tests.sh 5 passed · acp.ci.sh --fast PASS 6/6 · acp-validate.ts PASS 0 warnings"
  deferred:
    - "push of the 12 local commits (3f3b368..66b8711) -> not authorised this session"
    - "a33-37 Strata/llama log tailing -> still needs its own task"
  key_fact: "a fix that restricts which rows feed a cumulative-delta aggregate can destroy the very evidence (a NULL middle row) that marks a counter reset; bound the TIME SPAN instead of filtering the row set, and prove the fix on a fixture whose counters reset"

- date: 2026-10-28
  executor: zed
  branch: main
  tasks: ["review-015 remediation (M81 diff, 3f3b368..HEAD)"]
  done:
    - "server S2 dead duplicate return deleted; S3 DAY_BASELINE_MAX_AGE_S bounds the day delta baseline so a multi-day outage no longer charges days of counter movement to one day (requests 3 not 5, prompt 800 not 1400) while G-34-03 still passes"
    - "server S4 weighted_prefill_rate() puts numerator and denominator on ONE row set: the prompt_ms rollout no longer inflates the rate (probe 3000.0 vs the honest 1000.0); S5 hour path rounds tok_s_weighted like db_analysis; S6 gap buckets carry prefill_bounded/prefill_note"
    - "app S1 an-requests stopped interpolating req_per_min raw, which rendered '12 · null/min' on the live DB's duplicate-timestamp windows; the count now stands alone rather than being faked to 0"
    - "app A1 lastStatsData assigned when the fetch succeeds, so a throwing render can no longer leave the offline chart fallback with nothing; A2 usage ledger writes via setText and only stamps + re-spans when text actually changed"
    - "app A3 legend peaks and every private scale derive from the exact drawn SERIES values, so 'scaled to peak' is literally true; A4 observed(b,v) treats a sampled-but-null value as a hole and no drawn series coerces with || 0 any more"
    - "app A5 caption and #hist-window guard days[].date (the new static check surfaced a second instance at app.js:1206 of the same class); A6 every history bar carries a hover <title>; A7 wireDetail derives from .tiles--detail children instead of a hardcoded id list"
    - "app A8 the right-edge date can no longer be vetoed (reachable at N=17, stride 3); A9 interpolated p95 (R-7) replaces the off-by-one index, moving the fixture-derived gauge scale 1,250 -> 1,291; A10-A13 axis-label fallback, bounded tag from the right object and on the peak-n/a branch, HUD labels say 'not reported'"
    - "one reviewer claim was a FALSE POSITIVE and is recorded as such: A1's second half alleged an unfailable __lastChartFetch stamp in fetchTimeseries' catch, but the stamp was already inside if (fallback)"
    - "new checks: browser chart-null-value-is-a-hole, and history-bars now requires one hover title per bar; static null-safe-readouts, offline-fallback-and-ledger, chart-disclosure-honest, detail-wiring-derived. Counts browser 25 -> 26, static 16 -> 20; tests/telemetry 35/22/25 -> 37/25/26, expected.txt bumped in the same commits"
    - "18 mutation probes run (4 server, 14 front end), each produced a targeted failure with the wrong value shown, all reverted: git diff HEAD -- app.js server.py empty and no MUTATION PROBE markers remain"
    - "the suite caught a regression I caused: gating queueLayout() on 'wrote' while still stamping __lastUsage left a content stamp with no matching layout pass, so view-toggle-spans failed. Fixed by stamping only when a pass follows"
    - "phase-1 scanner on the diff: 4 HIGH, all pre-existing and identical at the 3f3b368 baseline (fetchStats / wireDragDrop / init EH-01 and the deliberate localStorage catch) - zero new findings, left alone as out of scope"
    - "gates at HEAD: ui 26/20 PASS, telemetry rc_all=0, usage rc_all=0, run-e2e-tests.sh 5 passed, acp.ci.sh --fast PASS 6/6, acp-validate.ts PASS 0 warnings (canonical 0.3.0)"
    - "agent/reports/review-015-m81-diff.md written (gitignored per ADR-28); a33-37 still pending and unchanged"
  deferred:
    - "a33-37 Strata/llama log tailing -> needs its own task, still pending"
    - "push of the 10 local commits -> not authorised this session"
  key_fact: "the UI suite's geometry waits treat __lastUsage as a content stamp that a layout pass must post-date, so any code path that stamps it MUST also run a layout pass; gating the pass but keeping the stamp fails view-toggle-spans"

- period: 2026-10-07 to 2026-10-27
  compacted: true
  done:
  - 'M76/M77 service robustness (2026-10-17, zed + claude-opus/haiku executors): supervisor owns its children (kill-on-close job), state file + stop-request + orphan takeover, restart moves both tasks by port; S4U boot task registered and run-without-reboot tested (chain later closed on a real reboot 2026-11-11, see a25-02); install verified via native install-service.ps1 -WithBoot; audit-27 scored zed 59 / haiku 67 and its remediation landed (lint L8 shared-kill pattern, gates G7/G8/G10, ADR-LM-001); M77 tooling: local.handover-executor skill, lint-handover.ps1 with fixtures, gate-service.ps1 with bare-boolean check + smoke test'
  - 'M80 (2026-10-26, zed): masonry row-span engine (ROW_UNIT 4px, ResizeObserver), detail-region nested packing, tile hierarchy/elevation; agent/tests/ui rebuilt as stdlib-CDP suite 10/10 mutation-proven; audit-32 + review-014; after a delete_path incident destroyed untracked agent/ docs (restored from git + rebuild), agent/.gitignore now tracks agent/tests/** so a UI suite can never be lost again'
  - 'M81 measurement correctness (2026-10-26/27, zed): audit-33 (36 findings) + audit-34 pre-impl; GPU named via winreg Enum\CI join (a33-01); rates as window ratios, PREFILL_CEILING 5000 bounded in all aggregate paths, weighted tok_s/prefill via prompt_ms, ghost-idle suppression, SPAN_FLOOR 5.0, +100%-from-empty-prior fixed in three sites, published_day_prefill structural marker; tests/telemetry added (25+35+22 assertions); UI: header de-dup + liveness cluster, gauge-scale labels, history bars with keyboard scrub, nav groups, order versioning, requests fold, settle contracts (caught the real fetchUsage masonry-staleness flake 4->0); browser 25/25 static 16/16; production DB isolation proven (delta 0)'
  - 'Harness + M71-M74 (2026-10-07..15): installed acp-ci/review/integrity harness, validate version/pointer checks, fixed stale current_milestone M1->M75; M74 SVG timeseries, M73 throughput sparklines, M72 compact HUD, M71 history table; audit-7/-10 remediations (db prune days, rollup 90d cap, /api/export json+csv, sqlite indexes); VRAM derived from vram_free_mib (audit-5)'
  - 'Key facts preserved verbatim: foreach ($x in FuncCall) without parens iterates an EMPTY stream - assign first; Start-Process children leave the scheduled task''s job and an S4U chain is invisible from the desktop - the supervisor must own its children and expose a state file; gitignored ACP memory has NO backup - never pass a directory to delete tools; a closed <details> body keeps layout boxes (assert on the fold element); WMI AdapterRAM is a UInt32 cap, registry qwMemorySize is the trustworthy VRAM; a page-level fetch fixture survives navigation - remove it explicitly; a settle baseline captured AFTER the action passes vacuously; an assertion calling a pure helper instead of the code path under test is unfailable; suppress unrepairable aggregates with a structural marker, not an invented threshold; when a change shrinks a region, re-measure every count assertion over it in the same commit'
  note: 'Auto-compacted 2026-11-12 by /acp-commit (19 entries > 15): 11 oldest session entries (2026-10-07..2026-10-27) folded into this block. Full originals recoverable from git history at the pre-compaction commit.'
