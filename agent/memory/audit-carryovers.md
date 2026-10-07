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
    status: pending
    fix_applied_date: null
    verified_in_audit: 2
    notes: code fix is in place; the running process must be restarted (kill 17956, relaunch `python server.py 8090`) to pick it up. After restart all 6 history series + analysis populate
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
    status: pending
    fix_applied_date: null
    verified_in_audit: 3
    notes: deliberately NOT shortcut in audit-3/review — a blanket window label would misstate the per-series x-axis. Correct fix threads a per-series window through drawSpark. Left open, not half-done
