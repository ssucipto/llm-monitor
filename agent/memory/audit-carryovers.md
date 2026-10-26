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
