# Audit Carryovers
#
# Schema: one entry per actionable finding that a future session must act on.
# status: pending | fixed | wontfix
# fix_applied_date: date the fix landed in the codebase (null until then)
# verified_in_audit: audit number that confirmed the fix (null until then)
# Surface rule (copilot-instructions Step 4): entries with status: pending are
# surfaced at session start; all-fixed files are skipped silently.

carryovers:
  - id: a1-01
    audit: 1
    finding: GPU readings (gpu_util, gpu_temp, gpu_mem_used/total, gpu_pcie_rx_mb) plumbed in payload but never rendered; engine's own monitor shows them as cards
    location: llm-monitor/server.py:817
    severity: high
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 2
    notes: "GPU panel now exists (index.html gpu section: util/mem/temp gauges + power/pcie/device facts + gpu sparkline); renderGpu() draws it. Empty on AMD HIP by design — engine returns no gpu_* keys"
  - id: a1-02
    audit: 1
    finding: fixed 2-col × 6-row grid area map pairs unequal panels → ragged bottoms and whitespace in sparse panels
    location: llm-monitor/style.css:201
    severity: high
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 3
    notes: "layout is now a dense auto-flow grid (grid-auto-flow: row dense) with per-panel order by importance and align-items:start; the three history panels (telemetry/requests/log) span full width as a bottom band. No forced empty cells. Mobile resets span to 1"
  - id: a1-03
    audit: 1
    finding: footer endpoint list omits /status and /props that the backend now probes
    location: llm-monitor/index.html:240
    severity: low
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 2
    notes: footer now lists /health /metrics /status /slots /props /v1/models
  - id: a1-04
    audit: 1
    finding: dead CSS selector :focus-active (not a real pseudo-class) on the skip link
    location: llm-monitor/style.css:65
    severity: low
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 2
    notes: no :focus-active remains in style.css
  - id: a1-05
    audit: 1
    finding: orphan .controls__hint rule — no matching element in index.html
    location: llm-monitor/style.css:601
    severity: low
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 2
    notes: no .controls__hint rule remains
  - id: a1-06
    audit: 1
    finding: thr-source concatenates decode + prefill sources in one fact row
    location: llm-monitor/app.js:186
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 2
    notes: split into thr-source + thr-prefill-source, each with its own label
  - id: a1-07
    audit: 1
    finding: requests table omits available per-request fields (reused, prompt_ms/decode_ms, pcie_share, drafts)
    location: llm-monitor/app.js:317
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 2
    notes: table now has Re + Draft columns; renderRequests draws reused and drafts accept %
  - id: a1-08
    audit: 1
    finding: sparklines have no baseline/min reference — flat line ambiguous between zero and low
    location: llm-monitor/app.js:211
    severity: low
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 2
    notes: drawSpark caption now shows peak AND min
  - id: a1-09
    audit: 1
    finding: requests_kept (239 records kept, 12 shown) not surfaced on Requests panel
    location: llm-monitor/server.py:695
    severity: low
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 2
    notes: requests-count now shows 'N recent · M kept'
  - id: a2-01
    audit: 2
    finding: running dashboard process (PID 17956 on :8090) predates the DB_PATH fix and still has telemetry disabled — trends and Telemetry panel empty until it is restarted
    location: llm-monitor/server.py:59
    severity: high
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 2
    notes: the running :8090 process was restarted; live /api/stats now returns telemetry {ok:true, rows:240} with daily rollups and periods populated, so all history series draw
  - id: r1-01
    audit: review-001
    finding: ACP CI harness not installed in this consumer project — agent/configurables/ci.yml, scripts/, e2e/, tests/, run-e2e-tests.sh, .github/workflows/ all absent, so /acp-ci --fast cannot run
    location: agent/configurables/ci.yml
    severity: high
    status: fixed
    fix_applied_date: 2026-10-15
    verified_in_audit: null
    notes: harness installed — scripts/{package.json,acp-validate.ts,acp-validate.test.mjs,ci-validate.sh}, e2e/acp.integrity*.test.sh, run-e2e-tests.sh, agent/configurables/ci.yml. acp.ci.sh --full = all 10 steps PASS. Also authored missing acp.review-scan-ts.py + acp.taint-scan.py and fixed the tab/CR emit contract, review-measure exit handling, e2e FP-baseline grep, and per-finding spawn cost
  - id: r3-01
    audit: 3
    finding: sparkline captions say "recent history" without the sampling window; history_bucket_s (75s) applies only to the requests series, while tok_s/power_w/cpu are per-poll (~5s), so a single blanket label would be inaccurate
    location: llm-monitor/app.js:249
    severity: low
    status: fixed
    fix_applied_date: 2026-10-08
    verified_in_audit: 8
    notes: drawSpark now takes a per-series windowMs and states the real x-axis (per-sample interval + span) in the caption. tok_s/power_w/cpu/vram pass REFRESH_MS (5s); requests passes historyBucketMs (set from data.history_bucket_s*1000, default 75s); hist passes 86400000 (per-day). No blanket label — each series states its own window.
  - id: a4-01
    audit: 4
    finding: drag froze over hero/gaps/footer and cross-container drops failed — pointermove/up were bound to the container, not the page
    location: llm-monitor/app.js:246
    severity: high
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 4
    notes: pointermove/pointerup/keydown(Escape) now on document; hitContainer() rect hit-test per move picks the target container
  - id: a4-02
    audit: 4
    finding: drop point ambiguous — nothing showed where a released panel would land
    location: llm-monitor/app.js:placeSlot
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 4
    notes: dashed .drop-slot inserted at the candidate slot and other panels FLIP-part around it; slot detached until placed (no hidden attr)
  - id: a4-03
    audit: 4
    finding: a plain click (no movement) left the preview slot in the DOM
    location: llm-monitor/app.js:commitDrag
    severity: low
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 4
    notes: slotEl.remove() precedes the !moved early return
  - id: a4-04
    audit: 4
    finding: FLIP fallback leaked an inline transition that double-animated subsequent moves
    location: llm-monitor/app.js
    severity: low
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 4
    notes: fallback removed (Element.animate is universal in target browsers); transition scoped to .panel.dragging only
  - id: a4-05
    audit: 4
    finding: ~28h poll-window cap made weekly/monthly history impossible — nothing survived pruning
    location: llm-monitor/server.py
    severity: high
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 4
    notes: tiny per-day rollup table finalized at each day boundary BEFORE pruning (db_finalize_days); DB_DAILY_MAX=400 covers 13+ months
  - id: a4-06
    audit: 4
    finding: day/window deltas went negative (e.g. -263 req) when engine counters reset on restart
    location: llm-monitor/server.py:627
    severity: high
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 4
    notes: cumulative_delta splits at each decrease and sums segments; first segment contributes only its own movement; applied in day_aggregates, db_analysis, req_per_min
  - id: a4-07
    audit: 4
    finding: req_per_min NameError after removing the old delta() helper (caught only by live-DB test)
    location: llm-monitor/server.py:838
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 4
    notes: req_per_min now computed from cumulative_delta(window, 6) / span * 60
  - id: a5-01
    audit: 5
    finding: VRAM used/total null despite live engine.vram_free_mib (367 MiB free); panel ignored the recoverable reading
    location: llm-monitor/server.py:1055
    severity: high
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 5
    notes: derive used = VRAM_TOTAL_MIB(24576) - vram_free; labelled derived. live /api/stats gpu.mem_pct=98.5, mem_used=24209, mem_total=24576
  - id: a5-02
    audit: 5
    finding: GPU util gauge blank; no counter on driver, but activity inferable from engine state
    location: llm-monitor/server.py:1057
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 5
    notes: util_pct falls back to power.activity from GPU_ACTIVITY table, util_source=modelled. 0.0 while engine idle is correct
  - id: a5-03
    audit: 5
    finding: GPU power card blank while the Power card already models gpu_w
    location: llm-monitor/app.js:483
    severity: low
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 5
    notes: renderGpu falls back to power.gpu_w with · modelled tag; gpu.power_w stays null so the two cards share one source
  - id: a5-04
    audit: 5
    finding: device name printed "1 GPU(s)"; gpu_name null but the machine is fixed
    location: llm-monitor/server.py:1080
    severity: low
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 5
    notes: rated fallback to POWER_MODEL gpu_name; bug was hw.get(gpu_count) — gpu_count lives in hardware_static, not hardware. name_source=rated
  - id: a5-05
    audit: 5
    finding: GPU sparkline blank; engine keeps no gpu_* history series
    location: llm-monitor/server.py:1200
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 5
    notes: vram_pct series built from own poll rows (db gained vram_used/vram_total cols + ALTER migration); history.vram_pct present, history_available=true
  - id: a5-06
    audit: 5
    finding: gpu temp / PCIe RX have no counter and no honest proxy on this AMD HIP driver
    location: llm-monitor/server.py (gpu dict)
    severity: low
    status: wontfix
    fix_applied_date: null
    verified_in_audit: 5
    notes: engine sources hardware via psutil (hardware_static.psutil=true, no GPU API on Windows); amdgfxinfo64.dll won't load standalone (WinError 1114), no GFXINFO_* exports in System32/DriverStore. NOT ACTIONABLE — stays -- honestly
  - id: a7-01
    audit: 7
    finding: day rollup table never pruned — db_prune only deletes poll rows, so the day table grows unbounded on disk
    location: llm-monitor/server.py:645
    severity: high
    status: fixed
    fix_applied_date: 2026-10-08
    verified_in_audit: 7
    notes: added db_prune_days (DELETE day WHERE d < today - DB_DAILY_MAX), called in telemetry() after db_finalize_days; day rows are tiny so a full-scan DELETE is trivial
  - id: a7-02
    audit: 7
    finding: retention was 400 days (~13 months), not the requested 3 months
    location: llm-monitor/server.py:68
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-08
    verified_in_audit: 7
    notes: DB_DAILY_MAX 400 -> 90 (~3 months); bounds both the finalize write-loop floor and db_prune_days, so exactly ~90 days retained and overwritten
  - id: a7-03
    audit: 7
    finding: no way to share/export collected data to an agent for review/dogfooding/troubleshooting
    location: llm-monitor/server.py:serve
    severity: high
    status: fixed
    fix_applied_date: 2026-10-08
    verified_in_audit: 7
    notes: "added GET /api/export (JSON: named poll_rows + days + meta{generated,window_days,poll_cols}) and /api/export.csv (header + rows). db_export always returns a str; build_export returns body or None. Data ships with field names + provenance = usable, not garbage"
  - id: a7-05
    audit: 7
    finding: engine exposes per-request fields we do not capture (pcie_share, ram_blobs, file_blobs, file_mb, reasoning_recoveries, drafts_offered/accepted; totals.drafts_*)
    location: llm-monitor/server.py (db_record / poll schema)
    severity: low
    status: fixed
    fix_applied_date: 2026-10-08
    verified_in_audit: 8
    notes: implemented in audit-8. Added drafts_offered/drafts_accepted (from totals) + pcie_share (from requests[0]) to poll schema, ALTER loop, INSERT, and db_export poll_cols. Sourced from the SAME /metrics dict the poll already reads -> zero extra engine requests. Blob counts (ram_blobs/file_blobs/reasoning_recoveries) deliberately NOT added — not numeric time-series material. INSERT arity bug (22 vs 23 ?) caught by migration test, fixed.
  - id: c21-01
    audit: 21
    finding: Windows service task (LLMMonitor, ONLOGON) never registered — install-service.bat cannot run from this MSYS/Git-Bash shell (schtasks /create -> Access denied); feature inert until user runs installer in a native Windows shell
    location: llm-monitor/install-service.bat
    severity: high
    status: fixed
    fix_applied_date: 2026-10-15
    verified_in_audit: 21
    notes: "launcher runtime logic verified natively (Start-Process served :8090 -> HTTP 200). Registration now DONE by the user in a native PowerShell shell (outside this restricted tool shell) — install-service.bat reported SUCCESS and schtasks /query /tn LLMMonitor confirms the task exists (Status: Ready, Logon Mode: Interactive only, ONLOGON trigger). Only the post-login :8090 load remains for the user to eyeball."
  - id: c22-01
    audit: 22
    finding: "service is one-shot per event — launcher spawns server.py once and never self-heals, so any mid-session death leaves the dashboard dark until the next login/boot (observed: :8090 dead, no live process, no traceback)"
    location: llm-monitor/llm-monitor-start.bat
    severity: high
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: 27
    notes: "Supervisor restarts the server with backoff; owner chain and restarts re-verified live in audit-27 (gate G3, three restarts, kill-by-PID restart in M77 T0). Provenance corrected in audit-27 (a27-10): the earlier verified_in_audit value named audit-26, a pre-impl audit that ran before the fix."
    m76_note: Implemented in M76 (supervisor restarts with backoff + lifecycle log); awaiting user review — keep pending until T7 fully passes.
  - id: c22-04
    audit: 23
    finding: ONLOGON + ONSTART both fire on login+boot -> double-launch; a naive port-probe guard races because serve_forever binds the port after the process starts, so a second doomed server.py can still spawn
    location: llm-monitor/install-service.bat:21-24
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: 27
    notes: "Bind guard (allow_reuse_address = False) plus supervisor port check; duplicate supervisor exits 0 (already served), re-verified 18:14:54 against a session-0 chain. Provenance corrected in audit-27 (a27-10): the earlier verified_in_audit value named audit-26, a pre-impl audit that ran before the fix."
    m76_note: Implemented in M76 via bind guard (allow_reuse_address=False → WinError 10048 on duplicate) + supervisor port-state check; awaiting user review — keep pending until T7 fully passes.
  - id: c22-02
    audit: 22
    finding: no log rotation — service.out.log/service.err.log append an access-log line every poll (~5s) with no bound, growing unbounded over uptime
    location: llm-monitor/llm-monitor-start.bat
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: 27
    notes: "Rotation to .1 proven on the LIVE file in audit-27 at 18:15:22: rotated service-8090.err.log (over 5242880 bytes), .1 = 6000000 bytes. Rotation runs when the supervisor starts a server. Provenance corrected in audit-27 (a27-10): the earlier verified_in_audit value named audit-26, a pre-impl audit that ran before the fix."
    m76_note: Implemented in M76 — log_request override logs only 4xx/5xx; supervisor rotates >5MB by rename (.1), never truncates; busy-file guard added so it coexists with the old launcher's held handles. Awaiting user review — keep pending until T7 fully passes.
  - id: c22-03
    audit: 22
    finding: do_GET API branch has no per-request try/except — a malformed request or handler exception can kill a worker and take down the whole server
    location: llm-monitor/server.py:1615
    severity: low
    status: wontfix
    fix_applied_date: null
    verified_in_audit: 23
    notes: "RE-AUDIT 23 — did NOT reproduce. Live malformed requests return clean 404/200 (../../etc/passwd->404, api/stats?x=%zz->200, timeseries?range=BOGUS->404) and server stays alive. Defensive-only; leaving wontfix unless the project require_error_handling rule is enabled."
  - id: a25-01
    audit: 25
    finding: "T4 not done — live LLMMonitor task still runs the old one-shot launcher (llm-monitor-start.bat) with PT72H limit; install-service.ps1 unregister is Access denied from restricted shells"
    location: llm-monitor/install-service.ps1
    severity: high
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: 27
    notes: "Task replacement done by the user 2026-10-17 06:06; audit-27 gate G4: LLMMonitor action = service-supervisor.ps1, limit PT0S. The earlier value review-012 was wrong: review-012 found the server unsupervised."
  - id: a25-02
    audit: 25
    finding: "DECISION B (S4U boot task) unimplementable/unverified — New-ScheduledTaskTrigger -AtStartup registration is Access denied from this shell and the reboot test never ran"
    location: agent/milestones/milestone-76-service-robustness.md
    severity: medium
    status: pending
    fix_applied_date: null
    verified_in_audit: 25
    notes: "DECISION B. Still pending: the startup trigger needs a real reboot with the user present. audit-27 ran the S4U task without a reboot (Start-ScheduledTask LLMMonitorBoot, 18:08 and 18:14): python.exe and LOCALAPPDATA resolve in session 0, the chain serves 8090, the gate attests it via the state file, sign-in exits already served, and the desktop restart moves it back via the stop request."

  - id: a26-01
    audit: review-012
    finding: "The dashboard on :8090 (PID 17760, started 01:20:45) has no running supervisor. Its supervisor (PID 22060) exited without a log line. Nothing restarts the server if it dies."
    location: llm-monitor/service-supervisor.ps1, agent/reports/handoff-claude-m76-install-verification-2026-10-17.md
    severity: high
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: 27
    notes: "Supervision restored (M77 T0); audit-27 gate G3 PASS on a complete chain. Provenance corrected in audit-27 (a27-10): the earlier verified_in_audit value named audit-26, a pre-impl audit that ran before the fix."

  - id: a26-02
    audit: review-012
    finding: "service-supervisor.ps1 still has the per-port and busy-file workaround (Test-BusyFile, fsutil) that was only needed while the old launcher held the shared logs"
    location: llm-monitor/service-supervisor.ps1
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: 27
    notes: "Busy-file workaround removed (no Test-BusyFile, fsutil or Claim-SharedLogs in service-supervisor.ps1; read in audit-27). Provenance corrected in audit-27 (a27-10): the earlier verified_in_audit value named audit-26, a pre-impl audit that ran before the fix."

  - id: a26-03
    audit: review-012
    finding: "Leftover test files in %LOCALAPPDATA%\\LLMMonitor: probe.out.log (0 bytes) and probe.err.log (from 2026-10-16)"
    location: "%LOCALAPPDATA%\\LLMMonitor"
    severity: low
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: 27
    notes: "probe.out.log and probe.err.log deleted; audit-27 gate G7 (wider check) PASS. Provenance corrected in audit-27 (a27-10): the earlier verified_in_audit value named audit-26, a pre-impl audit that ran before the fix."

  - id: a26-04
    audit: 26
    finding: "A force-killed supervisor leaves its server running with no supervisor (orphan). Observed 2026-10-17: stopping the supervisor on 8098 left its server listening."
    location: llm-monitor/service-supervisor.ps1
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "audit-27: the supervisor puts its wrapper and server in a kill-on-close job (a killed supervisor takes its server with it: 18:13 test, server alive after supervisor kill: False), and a new supervisor takes over an orphan of ours (18:06 on 8098, 18:14 on 8090). Awaiting independent verification (Zed handoff)."

  - id: a26-05
    audit: 26
    finding: "The supervisor's terminating-error trap (logs 'supervisor end (terminating error ...)') was not exercised by any test"
    location: llm-monitor/service-supervisor.ps1
    severity: low
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: 27
    notes: "Exercised in audit-27 on a scratch copy with an injected throw (8097): exit 1 and log line supervisor end (terminating error: audit-27 trap test)."

  - id: CR-006
    audit: review-010
    finding: "audit-carryovers.md YAML did not parse: unquoted notes/finding values containing ': ' (lines 19, 28, 262, 280, 283 before the fix)"
    location: agent/memory/audit-carryovers.md
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: 27
    notes: "Values quoted; the whole file parses with yaml.safe_load (audit-27). Provenance corrected in audit-27 (a27-10): the earlier verified_in_audit value named audit-26, a pre-impl audit that ran before the fix."

  - id: a27-01
    audit: 27
    finding: "Gate G10 stops the 8098 listener and its parent by PID without a command-line check (R7); stops the server before its supervisor; leaves run-server-8098.cmd and service-8098.* behind"
    location: agent/scripts/gate-service.ps1:157
    severity: high
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "G10 refuses a busy 8098, stops supervisor then server then wrapper only after a command-line match, removes the 8098 files; gate -SmokeTest PASS 18:16. Awaiting independent verification (Zed handoff)."

  - id: a27-02
    audit: 27
    finding: "Lint L8 and gate G8 miss piped and long-form name kills (Get-Process python | Stop-Process, -ProcessName, spps, kill -Name), the form of the 2026-10-16 incident"
    location: agent/scripts/lint-handover.ps1:160
    severity: high
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "One kill pattern in lint L8 and gate G8 (pipelines, -Name/-ProcessName, spps, kill, taskkill, pkill, killall, wmic); 9 incident forms matched, PID stops not matched; fixture bad-pipe-kill.md. Awaiting independent verification (Zed handoff)."

  - id: a27-03
    audit: 27
    finding: "Lint fixtures pin git_commit to HEAD 86ad22b; L2 compares with live HEAD, so run-tests.ps1 fails after the next commit"
    location: tests/lint-handover/good.md:8
    severity: high
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "lint-handover.ps1 -Head; run-tests.ps1 passes the fixture commit and asserts the exact set of failing checks; added a HEAD-drift case. 11/11 OK. Awaiting independent verification (Zed handoff)."

  - id: a27-04
    audit: 27
    finding: "Restart script ignores LLMMonitorBoot; after a reboot (DECISION B) the boot supervisor keeps running old code and races the new task; Stop-ScheduledTask failure is masked by SilentlyContinue"
    location: restart-llm-monitor.ps1:45
    severity: high
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "restart-llm-monitor.ps1: early refusal, stop request, stops both tasks with a logged warning on failure, stops leftover supervisors then servers by PID after a match, logs to service-<port>.log. Tested from the boot (session-0) state at 18:15:00. Awaiting independent verification (Zed handoff)."

  - id: a27-05
    audit: 27
    finding: "G7 checks only t7* and probe.* names and reported PASS while probe-10s.ps1 and probe-register-new.ps1 remain in the M76 task folder; agent/scratch-m77 left behind"
    location: agent/scripts/gate-service.ps1:117
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "G7 now flags any non-.md file in agent/tasks and agent/milestones, any agent/scratch-* folder, probe/spare-port/stop-request files. Stray probes and scratch-m77 deleted 18:05. Awaiting independent verification (Zed handoff)."

  - id: a27-06
    audit: 27
    finding: "A task stop leaves no end line in service-<port>.log (17:37:26, 17:43:08); review-012 F3 only fixed for deliberate exits"
    location: llm-monitor/service-supervisor.ps1:28
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "Every stop now leaves a line: restart: lines from the restart script, supervisor end (stop requested) for a graceful stop. Awaiting independent verification (Zed handoff)."

  - id: a27-07
    audit: 27
    finding: "Orphan server (a26-04) is never healed: the next supervisor sees 'ours' and exits, leaving it unsupervised"
    location: llm-monitor/service-supervisor.ps1:91
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "Kill-on-close job plus orphan takeover (see a26-04). Awaiting independent verification (Zed handoff)."

  - id: a27-08
    audit: 27
    finding: "README, restart warning and supervisor header name service.log/service.err.log; the code always writes service-<port>.*"
    location: llm-monitor/README.md
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "README service section, restart warning and supervisor header name service-<port>.* files; old shared files described as no longer written. Awaiting independent verification (Zed handoff)."

  - id: a27-09
    audit: 27
    finding: "Record drift: milestone files say planned with unchecked criteria; progress.yaml M76/M77 notes and counts stale; CHANGELOG 0.1.12 says installer not applied and misses later fixes"
    location: agent/progress.yaml
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "Milestone files, progress.yaml M76/M77 and recent_work, CHANGELOG 0.1.12 rewritten to match code and evidence. Awaiting independent verification (Zed handoff)."

  - id: a27-10
    audit: 27
    finding: "Carryovers closed as verified_in_audit audit-26 (a pre-impl audit, before the fixes); a25-01 cites review-012; mixed formats; c22-02 closed without the live-file rotation proof its plan required"
    location: agent/memory/audit-carryovers.md
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "verified_in_audit corrected for c22-01/02/04, a25-01, a26-01/02/03, CR-006 (independent live re-verification in audit-27). Awaiting independent verification (Zed handoff)."

  - id: a27-11
    audit: 27
    finding: "S4U context (LLMMonitorBoot) never run: python.exe and LOCALAPPDATA resolution unproven; can be checked without a reboot"
    location: llm-monitor/service-supervisor.ps1:15
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: 27
    notes: "S4U context run without a reboot (18:08, 18:14): python.exe and LOCALAPPDATA resolve; log written to the user profile. The reboot trigger itself stays under a25-02."

  - id: a27-12
    audit: 27
    finding: "Supervisor rewrites run-server-<port>.cmd before checking the port, so a duplicate supervisor edits the batch file a live cmd.exe is executing"
    location: llm-monitor/service-supervisor.ps1:86
    severity: low
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "Write-RunCmd now runs only just before Start-Process; the trap test showed no run file written by an exiting supervisor. Awaiting independent verification (Zed handoff)."

  - id: a27-13
    audit: 27
    finding: "Lint L9 rejects valid absolute and %VAR% paths; L12 requires 8081 but not 8080"
    location: agent/scripts/lint-handover.ps1:169
    severity: low
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "L9 checks absolute and %VAR% paths as they are; L12 requires 8080 and 8081. Generated absolute-path fixture and bad-no-8080.md. Awaiting independent verification (Zed handoff)."

  - id: a27-14
    audit: 27
    finding: "install-service.bat says no administrator rights needed while forwarding -WithBoot"
    location: llm-monitor/install-service.bat:3
    severity: low
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "install-service.bat header names the elevated shell for -WithBoot. Awaiting independent verification (Zed handoff)."

  - id: a27-15
    audit: 27
    finding: "log_request filter relies on str(HTTPStatus) being the number (Python >= 3.11); an int comparison is version-proof"
    location: llm-monitor/server.py:1645
    severity: low
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "log_request compares int(code) >= 400; checked with int and HTTPStatus inputs (404, 404, 500 logged; 200, 304, - not). Awaiting independent verification (Zed handoff)."

  - id: a27-16
    audit: 27
    finding: "File converted CRLF to LF; diff shows 677 changed lines for 125 real ones"
    location: agent/memory/audit-carryovers.md
    severity: low
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "File rewritten with CRLF line endings, as in HEAD. Awaiting independent verification (Zed handoff)."

  - id: a27-17
    audit: 27
    finding: "Receipts say 5 analyser warnings, gate output says 13; zed-to-claude handover starts with stray text"
    location: agent/tasks/milestone-77-handover-rules/M77-receipts.md
    severity: low
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "Correction recorded in M77-receipts (audit-27 section); stray prefix removed from handover-2026-10-17-zed-to-claude.md. Awaiting independent verification (Zed handoff)."

  - id: a27-18
    audit: 27
    finding: "restart-llm-monitor.ps1 -Port <n> stopped and restarted the 8090 task, then waited on the other port"
    location: restart-llm-monitor.ps1:45
    severity: high
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "Tasks are used only for the port in their action; other ports get a supervisor started directly. 18:06 test on 8098 left the 8090 chain unchanged. Awaiting independent verification (Zed handoff)."

  - id: a27-19
    audit: 27
    finding: "Stop-ScheduledTask stopped only the supervisor; the server survived as an orphan (18:07). Under DECISION B the session-0 chain hid its command lines and Stop-Process was Access denied (18:09), so restarts after a reboot were impossible from the desktop"
    location: llm-monitor/service-supervisor.ps1
    severity: high
    status: fixed
    fix_applied_date: 2026-10-17
    verified_in_audit: null
    notes: "Kill-on-close job (task stop now stops the server: 18:16), state file attestation (gate G3, restart, logon supervisor) and stop request (restart from the session-0 state at 18:15:00). Awaiting independent verification (Zed handoff)."

  - id: a30-01
    audit: 30
    finding: "the collapsible Detail region was crammed into one grid column, so its six secondary panels stacked in a single narrow stack instead of using the available width"
    location: llm-monitor/style.css:.detail
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-26
    verified_in_audit: null
    notes: "M80-T2: .detail spans the grid (grid-column: 1 / -1) and .tiles--detail is its own auto-fill minmax(280px,1fr) masonry grid; wide-full-width asserts the region spans the full width. Entry reconstructed 2026-10-26 after the original was lost in an accidental directory delete"

  - id: a30-02
    audit: 30
    finding: "no functional verification existed for the dashboard: nothing ever pressed Save/Reset or dragged a panel, so the M79 layout claims were unverified (closes the audit-29 recommendation)"
    location: agent/tests/ui/
    severity: high
    status: fixed
    fix_applied_date: 2026-10-26
    verified_in_audit: null
    notes: "M80-T4: agent/tests/ui/test_ui_browser.py drives the real page over CDP with a stdlib websocket client - page-clean, masonry-spans, wide-full-width, columns-adapt, save-button, reset-button, drag-persists; four of them mutation-proven. Wired into run-e2e-tests.sh and usage-tests.yml. Entry reconstructed 2026-10-26 after the original was lost in an accidental directory delete"

  - id: a32-01
    audit: 32
    finding: "the browser suite is wired into CI but its execution there has never been observed; if no browser were found it would print NOTRUN and the run would report PASS with a SKIP, so seven functional gates could sit unexecuted on every push"
    location: .github/workflows/usage-tests.yml
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-26
    verified_in_audit: 33
    notes: "CLOSED with evidence. Read the Actions log for run 40304874790 (commit 3f3b368, usage-tests job): 'ok test_ui_browser.py: 10/10' and '[tests/ui] PASS' appear twice (once in the ui step, once in the acp.ci --full step). No NOTRUN/SKIP line. The browser suite really executes on GitHub, so all ten functional gates gate every push"

  - id: a32-02
    audit: 32
    finding: "the browser suite reads geometry after fixed time.sleep() waits (3.0 s after navigate, 0.5-0.8 s per viewport change) instead of an observable settle condition, so a slow runner can produce a flaky read"
    location: agent/tests/ui/test_ui_browser.py
    severity: low
    status: pending
    fix_applied_date: null
    verified_in_audit: null
    notes: "Left deliberately in audit-32 (F-32-09): the waits are generous and the checks assert on computed style, not animation. Worth a settle helper (poll until two consecutive identical geometry reads) if a false failure is ever seen in CI"
  - id: a33-01
    audit: 33
    finding: "the dashboard names the wrong graphics card and labels it measured: engine hardware_static.gpu_name says AMD Radeon RX 6800 XT on a PC whose live adapter is an RX 7900 XTX"
    location: llm-monitor/server.py:1462
    severity: high
    status: fixed
    fix_applied_date: 2026-10-26
    verified_in_audit: 33
    notes: "M81-T1. server.py now resolves the GPU name through detect_host_hardware() (stdlib winreg, once at import) ahead of the engine's value, labels name_source os/engine/rated (never 'measured'), and exposes name_conflict so the disagreement is visible. Live /api/stats on spare port 8124: gpu.name 'AMD Radeon RX 7900 XTX', name_source 'os', name_conflict 'AMD Radeon RX 6800 XT', vram total 24560 from the OS. Both panels (gpu-name, hw-gpu) read the same resolved value. Root cause is upstream: /c/Project/Strata/serve/telemetry.py:360 windows_display_adapters indexes the display device class by HIP order, and this PC keeps a leftover driver entry for a removed card. Proof it is stale: Enum\\PCI instance ConfigFlags 32 (not present) on DEV_73BF vs 0 on DEV_744C, which is the ID WMI reports live. Stdlib fix measured on this host: join Enum\\PCI to the class subkeys through the instance Driver value, filter ConfigFlags 0x20/0x02 -> 1.3 ms, returns RX 7900 XTX + 24560 MiB. Planned as M81-T1"
  - id: a33-02
    audit: 33
    finding: "setGauge coerces null to 0, so the GPU Temp gauge prints a definite 0% where no driver counter exists"
    location: llm-monitor/app.js:108
    severity: high
    status: fixed
    fix_applied_date: 2026-10-26
    verified_in_audit: 33
    notes: "M81-T2. setGauge now writes '--' plus an empty (indeterminate) meter for null; HUD power reads the new rated_w alias of peak_w so its gauge is no longer stuck at 0; HUD VRAM scales by mem_source like the GPU panel; source labels report 'none' instead of inventing one. Proven by a new browser check null-gauge-not-zero (fixture injected with Page.addScriptToEvaluateOnNewDocument) and MUTATION-PROVEN: restoring the old coercion fails it with \"the null fixture never reached the Temp row, it reads '0%'\". Distinct from a5-04 (wontfix): that was about the missing counter, this is about rendering its absence. Also fixes the Compact HUD power gauge, which reads pw.rated_w while build_stats emits peak_w, so it is permanently zero (app.js:1755). Planned as M81-T2"
  - id: a33-08
    audit: 33
    finding: "Telemetry hit-rate and accept-rate window means average session-cumulative ratios per poll, so the panel shows a session ratio under a window label"
    location: llm-monitor/server.py:1240
    severity: high
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T3. db_analysis, db_hour_aggregates and day_aggregates now publish hit_pct_window / accept_pct_window computed as the span's own delta ratio (window_pct over the cumulative reused/prompt and drafts_accepted/drafts_offered counters). The legacy *_pct_mean keys are still emitted so no consumer breaks; app.js reads the _window values with a fallback. Measured on a copy of production history over spare port 8125: hit_pct_mean 94.17 vs hit_pct_window 99.01, accept 78.41 vs 80.49 (the direction and size vary by snapshot, as the audit predicted). Mutation-proven twice: restoring the mean-of-cumulatives fails the analysis assertion (95.0 where 50.0 is expected) and the hour-path assertion; in the day path it fails hit_mean (95.0 vs 10%) and the frozen day row"
  - id: a33-09
    audit: 33
    finding: "three different windows share two labels: Average tok/s is session, Peak tok/s is the last hour, and the sparkline caption's peak is ~2 minutes"
    location: llm-monitor/server.py:1380
    severity: high
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T3. build_stats publishes throughput.mean_window ('session') and peak_window ('last N min', derived from the analysis window actually used), and app.js prints each inline next to its number, so a rate can no longer detach from its window. The sparkline keeps its own caption window (r3-01); the three windows are now visibly different instead of pretending to agree. Live: mean_window session / peak_window last 60 min"
  - id: a33-10
    audit: 33
    finding: "physically impossible prefill readings are stored and charted: poll rows hold 1,354,360 / 1,210,150 / 1,205,830 tok/s on a card that decodes at 35-70"
    location: llm-monitor/server.py:1400
    severity: high
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T3. PREFILL_CEILING_TOK_S = 5000 derived from 20,165 live samples (p50 345, p90 1,093, p99 103,412, max 1,905,830; all 1,114 samples above 3,000 came from busy polls; the natural break is 2,000-3,000 with only 65 rows, so 5,000 excludes 1,047 = 5.19%). bounded_prefill() applies to db_analysis, db_hour_aggregates and day_aggregates; build_stats picks prefill from an honesty-ordered candidate list (live -> last_req -> engine) where the first physically possible value wins, and published sparkline samples over the ceiling become holes with history.prefill_bounded + prefill_bounded_n. Every published aggregate carries a '· bounded' tag. Raw samples stay in the DB: /api/export still shows what the engine reported. Live after the fix: prefill_max 208.4 (was 173,582), prefill_bounded True, history 30 of 240 samples bounded. Mutation-proven: replacing bounded_prefill with a plain mean in day_aggregates yields prefill_mean 302,762.5 and fails two assertions; the same probe in db_hour_aggregates lets prefill_max 1,210,150 through"
  - id: a33-11
    audit: 33
    finding: "idle staleness inflates every rate mean: throughput.now falls back to the last request's rate when idle, so one finished request is re-sampled once per poll"
    location: llm-monitor/server.py:1382
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T3 (part of the averaging fix). tok_s_weighted = output_delta / span and prefill_weighted = tokens read / prompt_ms delta are rates over the span, so idle polls stop dragging them; busy_polls and window_s are published alongside so the reader can see how much of the window was work. Live: tok_s_mean 33.08 vs tok_s_weighted 21.37 — the unweighted mean sat ~55% high. prefill_weighted needs the new prompt_ms poll column, so it is None for rows written before the migration rather than guessed"
  - id: a33-13
    audit: 33
    finding: "day_aggregates never got M75's ghost-idle suppression, so a 0-request day rolled up a stale per-poll rate that then fed the week/month weighted means in db_periods"
    location: llm-monitor/server.py:693
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T3. day_aggregates gates tok_s_mean, tok_s_max, prefill_mean and prefill_max on (requests > 0 or total_tokens > 0), mirroring db_analysis. db_finalize_days now freezes a quiet day with honest nulls, which changes what the week/month weighted means inherit. Mutation-proven: replacing the guard with `if True` fails 'a quiet day contributes no ghost tok/s to the month's weighted mean' (44.45 where None is expected)"
  - id: a33-14
    audit: 33
    finding: "duplicate-timestamp rows already exist in the DB, and span = max(1e-9, last-first) lets a zero-length window divide by the sentinel; the 'if span > 0' guard in db_hour_aggregates was dead code"
    location: llm-monitor/server.py:1212
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T3. SPAN_FLOOR_S = 5.0, tied to app.js REFRESH_MS, replaces the 1e-9 sentinel in db_analysis and db_hour_aggregates; req_per_min, tok_s_weighted and prefill_weighted are None when the span is under one sampling period, so the guard is live. Live DB: 20,119 rows / 20,101 distinct timestamps. Mutation-proven: restoring the sentinel plus the old `span > 0` guard makes req_per_min come back as 0.0 instead of None in both suites. The ThreadingHTTPServer write race that creates the duplicates is NOT fixed (a33-12 territory); this closes the arithmetic consequence"
  - id: a33-16
    audit: 33
    finding: "+100% printed for an empty prior window is a fake percentage"
    location: llm-monitor/app.js:1049
    severity: low
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T3. All three sites now print 'new (+N tok)' with the colour kept when the prior period is empty: the History comparison table, and BOTH Compact HUD trend rows (hour and today). The audit only listed app.js:1049-1052 and :1067-1069; the two HUD sites at what is now :1910 and :1929 were the same defect and are closed too. Guarded by a new static check no-empty-prior-percent that greps app.js for a hardcoded +100% literal, so the pattern cannot come back silently"
  - id: a33-17
    audit: 33
    finding: "no unit tests cover db_analysis, day_aggregates or the hourly bridging invariant"
    location: tests/
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T3. New tracked suite tests/telemetry (mirrors the tests/usage convention exactly: run-tests.py + expected.txt, one PASS line per assertion, count enforced): test_telemetry_analysis.py 35 and test_telemetry_days.py 22. In-memory/temp SQLite built by the real db_init() with synthetic poll rows — no engine, no production DB. Wired into .github/workflows/usage-tests.yml and run-e2e-tests.sh (now prints 5 e2e tests passed). The suite asserts the live poll schema equals what it inserts and db_record's column arity, so a migration cannot leave it testing a shape the server no longer writes"
  - id: a33-37
    audit: 33
    finding: "the System log panel tails only Hermes llama.cpp logs while the engine actually running is Strata, so the panel shows nothing from the live engine"
    location: llm-monitor/server.py:41
    severity: medium
    status: pending
    fix_applied_date: null
    verified_in_audit: null
    notes: "Recorded during M81-T3 work, not fixed. LOG_FILES lists watchdog.log / autostart.log / server.log.err, whose last writes are 2026-10-25 and 2026-10-09, while engine-active.txt says strata. The live engine log is C:\Project\Strata\strata-iq3_s.log: 6,196,001 bytes, refreshed the same day, containing 'conversation cache:' x8534, 'resident RAM:' x5360, 'KV streaming:' x5360, 'expert tiers:' x5360, 'decode expert cache hit rate:' x5355, 'lookup chain:' x5315, 'suffix drafts:' x4391, WARNING x5. Strata exposes no /log, /logs or /events (all 404), so tailing the file is the only route. Fix: include the active engine's log path per engine-active.txt alongside the launcher tails. Not planned into M81; needs its own task"
  - id: a33-34
    audit: 33
    finding: "the browser UI suite writes synthetic poll rows into the production telemetry.sqlite3 on every run"
    location: agent/tests/ui/test_ui_browser.py:178
    severity: high
    status: fixed
    fix_applied_date: 2026-10-26
    verified_in_audit: 33
    notes: "M81-T8 step 1, pulled forward. DB_PATH now honours LLM_MONITOR_DB (mirroring the USAGE_DB convention) and both UI suites pass a temp path. Measured: production poll rows 20,357 before a full suite run and 20,357 after (delta 0), where one spare-port server + one /api/stats previously moved 20,280 -> 20,282. New static check telemetry-db-isolation asserts the poll rows landed in the test file. Original evidence: Proven by experiment 2026-10-26: starting llm-monitor/server.py on spare port 8123 and issuing one /api/stats moved the production DB from 20,280 to 20,282 poll rows. DB_PATH (server.py:68) has no env override, unlike USAGE_DB/CLAUDE_ROOT/HERMES_DB at :72-74. Fix: LLM_MONITOR_DB override plus a row-count-unchanged assertion. Planned as M81-T8 step 1, pulled ahead of the value-dependent checks"
  - id: a33-36
    audit: 33
    finding: "the Compact HUD context card renders 7417.0% where the real figure is 74.2%, and its two token rows always show --"
    location: llm-monitor/app.js:1788
    severity: high
    status: fixed
    fix_applied_date: 2026-10-26
    verified_in_audit: 33
    notes: "Found while fixing a33-02, not in the original 35. context.pct is already a percentage (server.py multiplies by 100) and renderHud multiplied again; hud-ctx-val/hud-ctx-hint read ctx.used_tokens and ctx.max_tokens, keys build_stats never emits (the payload keys are used and max). M81-T2 corrected both to the real keys and one scaling, matching what the full dashboard already did. Measured against the live payload before the change: pct 74.17 rendered as 7417.0%"
  - id: a33-18
    audit: 33
    finding: "the chart y-axis unit changes meaning without saying so: one axis labelled from total_tokens while the decode/prefill/request lines are scaled by their own private maxima, and no unit appears on the axis at all"
    location: llm-monitor/app.js:1338
    severity: high
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T4. The left axis now belongs to exactly one series and says which: an axis title element (.chart-axis-title) plus the unit suffix on the top gridline label, both changing with the metric tab (all/tokens -> tokens, throughput -> tok/s, requests -> req). Every series that does NOT own the axis discloses its own scale in the legend ('scaled to peak 66.6 tok/s'), and the axis-owning one is labelled 'left axis', so no line's height is left unexplained. Proven by the browser check chart-axis-labelled, which also switches the metric tab and asserts the unit changed; mutation-proven by blanking the axis title (check fails with title '')"
  - id: a33-19
    audit: 33
    finding: "prefill_max is always null for 7d/30d/90d so the prefill series silently vanishes at long ranges; db_daily never reads a prefill_max column because the day table has none"
    location: llm-monitor/server.py:951
    severity: high
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T4. The day table gains prefill_max AND prefill_bounded through the existing ALTER loop, db_finalize_days writes both, db_daily and all three day-bucket branches of db_timeseries read them. Live copy (spare port 8126): 7d/30d/90d now report prefill_max available=True max=4680.5 where it was None before. Migration proven by opening a file created with the pre-migration schema through db_init: both columns appear and the old row reads back NULL rather than a copied mean. A day frozen before the bound holds an impossible mean (7,238 / 9,834 / 10,230 tok/s on this PC) whose poll rows are already pruned, so it cannot be recomputed: published_day_prefill suppresses that day's prefill entirely with note 'pre-bound record', keyed structurally (a mean with no max can only come from an older build, since bounded_prefill returns both or neither) rather than by inventing a second threshold. /api/export still ships the raw stored value"
  - id: a33-20
    audit: 33
    finding: "bucket counts are inconsistent across ranges and nothing on the chart states what each bucket covers"
    location: llm-monitor/app.js:1373
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T4. xStep is now round(N/6) with the last bucket always labelled, so every range gets ~6 evenly spaced labels and the right edge is dated. A new #chart-sum-window element states the scope of every number in the strip: '7d · 7 buckets of 1 d · 9 with no samples'. Proven by chart-gap-marked, which asserts 'buckets of' appears in the strip; mutation-proven by perturbing the count the strip prints (the check compares the strip's count against the in-chart note's and fails on the mismatch)"
  - id: a33-21
    audit: 33
    finding: "3h/6h/12h keep 60-second buckets while only ~240 poll rows exist for 24 h of history, so sparse buckets print as gaps that read as engine idle rather than no samples"
    location: llm-monitor/server.py:831
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T4 (the arithmetic/rendering half). Every bucket now carries samples: len(b_rows) for poll ranges and the stored polls count for day ranges, and the payload carries n_buckets + empty_buckets. The renderer draws each series as one polyline per contiguous run of observed buckets (a lone observed bucket becomes a dot), so an unobserved stretch is a hole instead of a dip to zero; gap buckets get dashed vertical markers, an in-chart note 'N buckets had no samples', and a tooltip that says nothing was recorded rather than showing zeros. Live: 1h empty=60/60 on a fresh copy, 90d empty=69/90. Proven by chart-gap-marked and chart-series-breaks-at-gap (seeds a deliberate 20-minute hole in the test DB and asserts no series point sits on the plot floor); mutation-proven by mapping unobserved buckets to 0, which puts points at y=265 and fails it. NOT addressed: the bucket sizes themselves are unchanged, and the ThreadingHTTPServer write race that creates duplicate timestamps is still open (a33-12)"
  - id: a33-22
    audit: 33
    finding: "the chart's own summary strip has no timeframe label, so its totals are unscoped"
    location: llm-monitor/index.html:304
    severity: low
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T4. New #chart-sum-window stat in the strip, rendered from range/n_buckets/bucket_s/empty_buckets so it is derived from the payload rather than the button state. Also closed the related honesty gap the audit noted in passing: chart-sum-prefill-hint used to print 'mean / peak' whether or not a peak existed; it now prints 'mean · peak N · bounded', or 'mean · peak n/a' when no peak was recorded. Covered by chart-gap-marked (asserts the window string) and chart-no-impossible-prefill"
  - id: a33-23
    audit: 33
    finding: "the History sparkline is unreadable by design: up to 90 daily values drawn into a 100x30 CSS pixel figure with no y-axis, no gridlines and no date ticks"
    location: llm-monitor/index.html:391
    severity: high
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T5. #hist-bars (viewBox 0 0 900 170) replaces it: 4 gridlines, a unit-bearing axis title plus the same unit suffix on the top gridline label, x ticks at stride round(N/6) with the last day always labelled (MM-DD), and rect.hist-bar[data-day] per recorded day. A .chart-tab metric switch offers requests (req/day), tokens (tokens/day) and tok/s; a null tok_s draws no bar rather than a zero-height bar, so an absent metric is never shown as a zero. Caption states 'N recorded days - first -> last - peak X unit - M days with no <label>'. The old sparkline figure is hidden, not deleted, so hist-area/hist-spark/hist-head stay in the DOM for the id contract (static checks 2/3/5). Proven by history-bars; mutation-proven by drawing no bars (0 rects), blanking the axis title, removing the gridline unit suffix, dropping the x ticks and stripping the peak from the caption"
  - id: a33-24
    audit: 33
    finding: "the scrubber has no day labels: #scrub is a bare track and marker that never says which day sits under the marker nor what range it spans"
    location: llm-monitor/index.html:399
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T5. .scrub__ends names the first and last recorded day (#hist-scrub-first / #hist-scrub-last), filled by selectDay. The track declares role=slider, so it must be keyboard operable: tabindex=0 plus a keydown handler for ArrowLeft/Right/Up/Down, Home, End, PageUp/PageDown (page keys step a week). aria-valuetext reads 'YYYY-MM-DD, day i of N' so a screen reader gets the date rather than an index, and the highlighted bar (.is-selected) follows the selection without redrawing the chart. Clicking any bar selects that day (wireHistBars, delegated on the persistent svg element so it survives redraws). Proven by history-scrub-keyboard; mutation-proven by removing tabindex ('the slider is not keyboard reachable'), deleting the keydown handler ('End did not reach the last day') and naming the wrong date in aria-valuetext ('aria and the visible readout name different days')"
  - id: a33-25
    audit: 33
    finding: "the comparison table mixes units in one row: Current Tokens / Previous Tokens / Token Change / Requests / tok/s sit side by side with no window statement per row"
    location: llm-monitor/index.html:377
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T5. Rows are relabelled 'Today vs Yesterday (UTC)', 'This week vs Last week (UTC)' and 'This month vs Last month (UTC)', and a one-line note (.history-table__note, #hist-table-note) states that the periods are UTC-day aligned - the buckets are UTC epoch days (server.py _iso_day) while other timestamps render local (fmtSince -> toLocaleString, a33-15). 'Last request' and 'This hour' are deliberately NOT tagged UTC: they are not UTC-day buckets, so labelling them UTC would be a new lie. The row structure (volume and rate in one row) is kept; the fix is that each row now names its window"
  - id: a33-29
    audit: 33
    finding: "default order does not reflect importance: hardware (gpu, power) sits above the request stream and the analysis, and the Usage ledger sits above Requests"
    location: llm-monitor/app.js:167
    severity: high
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T6. DEFAULT_ORDER.tiles is now live, throughput, context, cache, spec, analysis, charts, requests, gpu, power, hardware, usage, history - engine performance first, activity second, hardware third, reference material last (audit-33's recorded grouping). Cache and speculative decode moved out of the collapsed region into the main grid because they are engine readings; hardware moved the other way. The <section> blocks physically moved in index.html too, so the pre-JS fallback order and the drag baseline match the JS default. Proven by layout-version-migration, which reads DEFAULT_ORDER out of the shipped app.js and asserts the live DOM matches it element for element, then asserts tiles[:5] is the engine-performance group. Mutation-proven by permuting BOTH the JS list and the markup (keeping all 13 ids so static check 4 stays green): 'the default order does not lead with engine performance'"
  - id: a33-30
    audit: 33
    finding: "Requests is not collapsible: index.html:241-263 is a plain <section> and the only <details> in the document is #detail"
    location: llm-monitor/index.html:241
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T6 (collapse INSIDE the panel, as audit-33 decided). #requests stays <section class=\"panel requests tile--wide\"> so static check 4 still counts 16 panels and ORDER_SIG still sees the same element; its count + table moved under an inner <details class=\"panel__fold\" open> whose summary mirrors .detail__summary (rotating chevron) so one affordance is learned. The masonry pass needed no new code: layoutTiles already gives a zero-height child gridRowEnd:auto and the ResizeObserver on children re-spans on toggle - verified, not assumed. Proven by requests-collapsible, which clicks the real summary, waits for the rAF layout pass, then asserts the fold collapses to under 40px, the panel loses >40px, and the row span still brackets the new height within gap + 2 units. Mutation-proven by removing the panel__fold class ('no details.panel__fold inside #requests'), shipping the fold closed ('does not ship open with its contents painted') and emptying the summary. Note: a table's getBoundingClientRect is NOT a valid observable for a closed <details> - Chrome hides the body via content-visibility on ::details-content while descendants keep their boxes, so the first draft of this check failed on correct code"
  - id: a33-31
    audit: 33
    finding: "the nav (.toc) does not match the sections: it lists six panels that live inside the collapsed #detail and omits #usage, so 6 of 15 anchors need two clicks and one panel is unreachable"
    location: llm-monitor/index.html:64
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T6. The nav is rebuilt as four labelled groups in the new default order - Engine performance (live, throughput, context, cache, spec, analysis), Activity (charts, requests, history, usage), Hardware (gpu, power, hardware), Reference (engine, switch, log) - so all 16 panels are reachable and #usage is no longer missing. The three links that point inside the collapsed region carry .toc__link--detail with a trailing ellipsis, so the two-click cost is visible rather than feeling like a dead link. Kept as static markup (not JS-generated) so it works before app.js runs; drift is prevented by a new static check toc-covers-panels (12th static check), which fails on any nav link that is not a panel and on any panel with no nav link. wireDetail's beforematch list was narrowed to the three panels that still live in the region, so a find-in-page hit on cache or spec no longer opens Reference for an unrelated match"
  - id: a33-32
    audit: 33
    finding: "re-ordering DEFAULT_ORDER collides with saved layouts: restoreOrder honours localStorage['llm-monitor-order'], so new defaults never reach an existing user"
    location: llm-monitor/app.js:243
    severity: medium
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T6, following the decision recorded in audit-33: version the save, re-arrange once, keep Reset. persistOrder now writes v: ORDER_VERSION (2). restoreOrder honours a save whose v matches exactly; a save with an older or missing v gets DEFAULT_ORDER plus a visible note (#layout-note, role=status, beside Save/Reset with a Dismiss button) and is immediately re-saved at the current version. Pre-M79 {masonry, band} saves arrive version-less and take the same path. Reset also clears the note, since it is the action the note points at. Rejected (as in the audit): bumping ORDER_KEY, which discards the user's order with no notice. Proven by layout-version-migration: it plants a deliberately reversed version-less save, reloads, asserts the DOM matches the new defaults rather than the planted order, asserts the note is visible and mentions the layout, and asserts the re-saved payload carries v: 2 and the default tiles. Mutation-proven by replacing the version gate with 'if (true)' ('a stale saved layout was honoured instead of the new defaults') and by removing the noteLayoutReplaced call ('the replaced layout was not announced')"
  - id: g34-01
    audit: 34
    finding: "the M81 plan breaks detail-packing, a currently-passing browser check: test_ui_browser asserts dgeo['tiles'] >= 4 while the Detail region shrinks to engine/switch/log, of which #log is hidden='until-found' (zero height, skipped), leaving only 2 measurable tiles"
    location: agent/tests/ui/test_ui_browser.py:468
    severity: high
    status: fixed
    fix_applied_date: 2026-10-27
    verified_in_audit: null
    notes: "M81-T6, landed in the same commit as the DOM move as the audit required. The assertion is now >= 2 with a comment naming why two is correct (cache and spec are engine readings and moved to the main grid; #log is intentionally collapsed). The cols >= 2 assertion was re-measured rather than assumed: at 1240px the region holds engine + switch as measurable tiles and they pack in separate columns, so it passes unchanged. G-34-02 was checked at the same time: #detail is itself a grid item inside .tiles, so the new tiles list legitimately carries 13 panels plus #detail; the save-button check survives because it compares sorted container-scoped lists, and the new layout-version-migration check reads containers directly via ORDER_SIG rather than counting .tiles > .panel across both grids"
  - id: a33-35
    audit: 33
    finding: "browser checks read whatever engine is live on :8080, so any assertion about values rather than structure is inherently flaky"
    location: agent/tests/ui/test_ui_browser.py:178
    severity: medium
    status: pending
    fix_applied_date: null
    verified_in_audit: null
    notes: "M81 needs value-dependent checks (null-gauge-not-zero, history-bars, chart-axis-labelled). Add LLM_MONITOR_FIXTURE so _get_json serves a fixture and the temp DB is seeded from it. Planned as M81-T8 step 2. Partially mitigated by M81-T4 without needing the fixture: chart-series-breaks-at-gap and chart-no-impossible-prefill seed the LLM_MONITOR_DB test file directly, so their expected values are exact and independent of whatever engine is live. The remaining engine-dependent value checks (the gauge family) still rely on the Page.addScriptToEvaluateOnNewDocument fetch fixture rather than a server-side one"
