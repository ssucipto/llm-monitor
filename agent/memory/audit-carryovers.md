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
    notes: GPU panel now exists (index.html gpu section: util/mem/temp gauges + power/pcie/device facts + gpu sparkline); renderGpu() draws it. Empty on AMD HIP by design — engine returns no gpu_* keys
  - id: a1-02
    audit: 1
    finding: fixed 2-col × 6-row grid area map pairs unequal panels → ragged bottoms and whitespace in sparse panels
    location: llm-monitor/style.css:201
    severity: high
    status: fixed
    fix_applied_date: 2026-10-07
    verified_in_audit: 3
    notes: layout is now a dense auto-flow grid (grid-auto-flow: row dense) with per-panel order by importance and align-items:start; the three history panels (telemetry/requests/log) span full width as a bottom band. No forced empty cells. Mobile resets span to 1
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
    status: pending
    fix_applied_date: null
    verified_in_audit: null
    notes: not a code defect; a tooling gap. Either install the harness or treat /acp-ci as N/A for this repo. Local gates (node --check, py_compile, review-scan) are the substitute
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
    notes: added GET /api/export (JSON: named poll_rows + days + meta{generated,window_days,poll_cols}) and /api/export.csv (header + rows). db_export always returns a str; build_export returns body or None. Data ships with field names + provenance = usable, not garbage
  - id: a7-05
    audit: 7
    finding: engine exposes per-request fields we do not capture (pcie_share, ram_blobs, file_blobs, file_mb, reasoning_recoveries, drafts_offered/accepted; totals.drafts_*)
    location: llm-monitor/server.py (db_record / poll schema)
    severity: low
    status: fixed
    fix_applied_date: 2026-10-08
    verified_in_audit: 8
    notes: implemented in audit-8. Added drafts_offered/drafts_accepted (from totals) + pcie_share (from requests[0]) to poll schema, ALTER loop, INSERT, and db_export poll_cols. Sourced from the SAME /metrics dict the poll already reads -> zero extra engine requests. Blob counts (ram_blobs/file_blobs/reasoning_recoveries) deliberately NOT added — not numeric time-series material. INSERT arity bug (22 vs 23 ?) caught by migration test, fixed.
