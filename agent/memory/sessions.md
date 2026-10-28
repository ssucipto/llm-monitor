# Session Memory
# Format: YAML blocks, last 3 loaded per session, auto-compacted at 15 entries
# DO NOT edit manually — updated by /acp-commit

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

- date: 2026-10-27
  executor: zed
  branch: main
  tasks: [task-81-t7, task-81-t8]
  done:
    - "a33-26 header de-duplicated: .topbar__meta is only the liveness cluster, #top-tok kept hidden for the id contract, prefill moved into the KPI strip; new static check header-unique-units asserts on visible unit LABELS so any future pair of header cells claiming the same thing fails"
    - "a33-27 gauge scale: #top-gauge-ceiling prints 'gauge to N', aria-label names reading and scale, ceiling = max(600, ceil(1.25 x p95)) with 20% hysteresis computed from the already-bounded series; static check gauge-scale-labelled rejects a hardcoded 2000"
    - "a33-28 liveness: #top-uptime from totals.since (unparseable -> '--', never NaN), #top-age from lastPollOkAtMs re-ticked every second, #top-build shows engine.build_info; browser check header-liveness pins since + build_info + a p95 of 1,000 and asserts the scale reads 1,250 and 2,000 appears nowhere"
    - "a33-35 closed: LLM_MONITOR_FIXTURE in server.py answers _get_json from agent/tests/ui/fixtures/engine.json; an unusable fixture raises SystemExit(2) rather than falling back to the live engine. New browser check fixture-engine-values asserts exact payload numbers and the rendered GPU panel; new static check engine-fixture-honoured proves a missing fixture stops the server"
    - "a32-02 closed: settle / settle_spans / settle_render / settle_usage / settle_chart replace every read-after-change sleep; app.js exposes __lastLayout, __lastRender, __lastChartFetch, __lastChartRender, __lastUsage; new static check geometry-read-settled fails if a fixed sleep returns between a viewport change and its settle"
    - "real flake found by the settles and fixed at the source: fetchUsage() rewrites and grows the Usage tile after load, so a masonry pass that merely post-dated a viewport change was stale ('tiles without a sufficient row span: [usage:66]'); queueLayout() in fetchUsage plus tile height in SPANS_SIG; flake.py 4 -> 0 failing runs of 4"
    - "isolation re-proven with the finished suite: production telemetry.sqlite3 poll 20,289 / day 20 before, after run 1 and after run 2 (delta 0 both times), identical pass counts across runs (browser 25/25, static 16/16)"
    - "expected.txt browser 24 -> 25, static 14 -> 16; nine mutation probes run this session and each produced a targeted failure, all reverted"
    - "records: M81 8/8 completed, version 0.2.1 -> 0.3.0 in progress.yaml and CHANGELOG.md together, task-81-t8 + milestone doc closed, a33-35 and a32-02 added as fixed carryovers with receipts"
    - "follow-up audit of T8's own work found three defects and all were fixed: an exception carved out of the new endpoint assertion (k != 'status'), mkdtemp dirs never removed by either suite (490 accumulated in %TEMP%), and check 15 starting the real server without LLM_MONITOR_DB so a regressed fixture guard would have written production poll rows"
    - "README.md gained a Test overrides table; LLM_MONITOR_DB / LLM_MONITOR_FIXTURE had never been documented"
  deferred:
    - "a33-37 Strata/llama log tailing -> needs its own task (still pending)"
    - "the striped no-data meter track still needs one human eyeball (Chrome pseudo-element paint is unobservable from CDP)"
    - ":8090 was refusing connections all session; the scheduled task was left untouched per machine rules, so T3/T4 server.py changes are not yet live on the dashboard"
    - "nothing pushed: main is 6 commits ahead of origin/main (27fcd7b, f253291, f87f201, 99be9f9, 19f6197 + this one) - push only when asked"
  key_fact: "A page-level fetch fixture (Page.addScriptToEvaluateOnNewDocument) SURVIVES navigation, so a later check that navigates to a different server silently inherits it - keep the identifier and call Page.removeScriptToEvaluateOnNewDocument. And a settle whose baseline is captured AFTER the action passes or fails on nothing: capture the before-value before the input."

- date: 2026-10-27
  executor: zed
  branch: main
  tasks: [task-81-t6]
  done:
    - "a33-29 DEFAULT_ORDER.tiles = live, throughput, context, cache, spec, analysis, charts, requests, gpu, power, hardware, usage, history; the <section> blocks physically moved in index.html so the pre-JS fallback matches the JS default"
    - "cache + spec moved out of the collapsed region into the main grid (engine readings); hardware moved in; region relabelled 'Reference - engine config, engine switch, system log'"
    - "a33-30 #requests stays a <section class=panel> and its count + table fold under an inner <details class=panel__fold open>; the existing ResizeObserver -> rAF pass re-spans on toggle (verified, not assumed)"
    - "a33-31 nav rebuilt as four labelled groups covering all 16 panels incl. #usage; links into the collapsed region marked; new static check toc-covers-panels (static 11 -> 12)"
    - "a33-32 per the audit-33 decision: persistOrder writes v: ORDER_VERSION (2); an older/version-less save gets the defaults + a visible note beside Save/Reset and is re-saved at v2; Reset clears the note; bumping ORDER_KEY rejected as silent data loss"
    - "audit-34 G-34-01 landed in the same commit as the DOM move: detail-packing tiles >= 4 -> >= 2, with cols >= 2 re-measured rather than assumed; G-34-02 verified (#detail is a grid item, so tiles = 13 panels + detail)"
    - "wireDetail's beforematch list narrowed to engine/switch/log so a find-in-page hit on cache or spec no longer opens Reference for an unrelated match"
    - "browser suite 21 -> 23 (requests-collapsible, layout-version-migration); seven mutations proven"
    - "records: a33-29/30/31/32 + g34-01 added as fixed carryovers, progress.yaml M81 6/8"
  deferred:
    - "M81 T7 header redesign, T8 steps 2-6 -> those tasks"
    - "a33-37 System log panel tails only Hermes llama.cpp logs while Strata's own log is never read -> needs its own task"
    - "a33-35 LLM_MONITOR_FIXTURE -> task-81-t8 step 2; a32-02 fixed sleeps -> task-81-t8 step 3"
    - "the striped no-data meter track still needs one human eyeball (Chrome pseudo-element paint is unobservable from CDP)"
    - ":8090 restart -> front-end files are served from disk so T5/T6 are visible on reload; the T3/T4 server.py changes are not"
  key_fact: "A closed <details> body is hidden by content-visibility on ::details-content, so its descendants keep their layout boxes — asserting on a table's getBoundingClientRect inside a fold fails on CORRECT code. The fold element's own height is the observable. And when a change shrinks a region, every count assertion over that region must be re-measured in the same commit (audit-34 G-34-01), not carried forward."

- date: 2026-10-27
  executor: zed
  branch: main
  tasks: [task-81-t5]
  done:
    - "a33-23 History sparkline (100x30, no axis) replaced by #hist-bars: 4 gridlines, unit-bearing axis title + unit suffix on the top gridline label, x ticks at stride round(N/6) with the last day always labelled, rect.hist-bar[data-day]; old sparkline <figure> hidden not deleted so its ids stay in the DOM"
    - "metric switch (requests / tokens / tok/s) reusing .chart-tab; a null tok_s draws NO bar rather than a zero-height bar"
    - "a33-24 scrub ends name first/last recorded day, tabindex=0 + Arrow/Home/End/PageUp/PageDown, aria-valuetext = 'YYYY-MM-DD, day i of N', .is-selected follows selection without a redraw, clicking a bar selects that day"
    - "a33-25 comparison rows relabelled 'Today vs Yesterday (UTC)' / week / month + a UTC-day-alignment note; 'Last request' and 'This hour' deliberately left untagged because they are not UTC-day buckets"
    - "browser suite 20 -> 21 (history-scrub-keyboard), expected.txt bumped"
    - "mutations proven: no bars (0 rects), blank axis title, no gridline unit suffix, no x ticks, caption without peak, scrub ends left at '--', empty aria-valuetext, forced histMetric on tab click, tabindex removed, keydown handler deleted, wrong date in aria-valuetext"
    - "records: a33-23/24/25 added as fixed carryovers (they were missing from the file), progress.yaml M81 5/8"
  deferred:
    - "M81 T6 block order + collapsible Requests + Detail re-categorisation, T7 header, T8 steps 2-6 -> those tasks"
    - "audit-34 G-34-01: test_ui_browser detail-packing asserts >=4 tiles; T6 shrinks the region to 3 and MUST update that assertion in the same commit"
    - "a33-37 System log panel tails only Hermes llama.cpp logs while Strata's own log is never read -> needs its own task"
    - "a33-32 saved-layout versioning decision -> must be surfaced to the user before T6 ships"
    - "a33-35 LLM_MONITOR_FIXTURE -> task-81-t8 step 2; a32-02 fixed sleeps -> task-81-t8 step 3"
    - ":8090 restart -> front-end files are served from disk so T5 is visible on reload, but the T3/T4 server.py changes are not"
  key_fact: "A check that reads a DOM readout AFTER a later keyboard event compares the wrong state: history-scrub-keyboard first captured #hist-selected after Home, so the aria-vs-visible agreement assertion had to sample at the ArrowLeft point instead. Cross-asserting two independent readouts (aria-valuetext vs the visible line) is what made naming the wrong date detectable."

- date: 2026-10-27
  executor: zed
  branch: main
  tasks: [task-81-t4]
  done:
    - "a33-18 chart axis states its unit and the unit follows the metric tab; every series that does not own the axis discloses its own peak in the legend, the axis owner is labelled 'left axis'"
    - "a33-19 day table gains prefill_max + prefill_bounded via the existing ALTER loop; db_finalize_days / db_daily / all three db_timeseries day branches thread them. Live copy: 7d/30d/90d prefill_max 4680.5 where it was None"
    - "a33-20 xStep = round(N/6) with the last bucket always labelled; new #chart-sum-window states 'range · N buckets of Xs · M with no samples'"
    - "a33-21 every bucket carries samples; series draw as contiguous runs so an unobserved stretch is a hole not a dip to zero; dashed gap markers, an in-chart note, and a tooltip that refuses to present zeros for an unobserved bucket"
    - "a33-22 the summary strip is scoped to its window; chart-sum-prefill-hint stopped printing 'mean / peak' when no peak exists"
    - "new published_day_prefill: a day frozen before the bound holds an impossible mean whose poll rows are pruned, so it publishes no prefill figure with note 'pre-bound record'; keyed structurally (a mean with no max can only be an older build) rather than by inventing a second threshold"
    - "found and fixed a T3 gap the audit never saw: db_export's poll_cols omitted prompt_ms, breaking the export-stays-re-derivable contract"
    - "new tests/telemetry/test_telemetry_timeseries.py (25 assertions incl. a real old-schema migration proof); browser suite 15 -> 18; static suite 10 -> 11 (fallback-bucket-shape)"
    - "mutations proven: axis title blanked, gap count perturbed, unobserved buckets mapped to 0 (points at y=265), legend hide/scale disabled, pre-bound rule off (9833 reached the panel), fallback bucket missing samples, day prefill_max ALTER removed, export column dropped"
    - "records: a33-18/19/20/21/22 closed with evidence, a33-35 annotated as partially mitigated by direct DB seeding, progress.yaml M81 4/8"
  deferred:
    - "M81 T5 history chart + scrubber, T6 block order + collapsible Requests + Detail re-categorisation, T7 header, T8 steps 2-6 -> those tasks"
    - "a33-21's other half: the bucket sizes themselves (3h/6h/12h still use 60 s buckets) are unchanged, and a33-12's ThreadingHTTPServer write race is still open"
    - "audit-34 G-34-01: test_ui_browser detail-packing asserts >=4 tiles; T6 shrinks the region to 3 and MUST update that assertion in the same commit"
    - "a33-37 System log panel tails only Hermes llama.cpp logs while Strata's own log (6.2 MB, live today) is never read -> needs its own task"
    - "a33-32 saved-layout versioning decision -> must be surfaced to the user before T6 ships"
    - "a32-02 fixed sleeps -> task-81-t8 step 3; a25-02 reboot test -> still user-gated"
    - ":8090 restart -> its day table has neither new column, so until the supervisor restarts it the day ranges show no prefill peak (NULL) rather than a wrong one"
  key_fact: "Suppressing an unrepairable historical aggregate needs a structural marker, not a threshold: since bounded_prefill returns mean and max together or neither, 'a stored mean with no stored max' can only be a pre-fix row, so no second invented cutoff is needed. And seeding the test DB directly (rather than the live engine) makes value assertions exact — two of the five new browser checks depend on nothing that runs on :8080."

- date: 2026-10-27
  executor: zed
  branch: main
  tasks: [task-81-t3]
  done:
    - "a33-08 hit/accept rates are now the span's own ratios (window_pct over cumulative counters) in db_analysis, db_hour_aggregates and day_aggregates; legacy *_pct_mean keys kept so /api/stats stays additive"
    - "a33-09 every published rate carries its window label (mean_window session, peak_window last 60 min) printed inline by app.js"
    - "a33-10 PREFILL_CEILING_TOK_S 5000 from 20,165 live samples; bounded_prefill in all three aggregate paths + sparkline holes + '· bounded' tag; raw samples stay in the DB so /api/export is still honest"
    - "a33-11 tok_s_weighted and prefill_weighted (new additive prompt_ms poll column) replace unweighted means of instantaneous rates"
    - "a33-13 day_aggregates ghost-idle suppression; a33-14 SPAN_FLOOR_S 5.0 replaces the 1e-9 sentinel and makes the dead span guard live"
    - "a33-16 +100%-from-empty-prior fixed in THREE sites, not the two the audit listed (History table + both Compact HUD trend rows), guarded by a new static check no-empty-prior-percent"
    - "a33-17 first unit tests for db_analysis / day_aggregates / db_hour_aggregates: tests/telemetry (35 + 22 assertions) wired into usage-tests.yml and run-e2e-tests.sh"
    - "found and fixed a defect the audit never saw: db_hour_aggregates published prefill_weighted as a permanent None stub because its SELECT omitted prompt_ms"
    - "nine mutations proven across the two suites (window ratio x2, prefill_weighted stub, span sentinel, day baseline, ghost-idle guard, day bound, hour bound, +100% literal)"
    - "records: a33-08/09/10/11/13/14/16/17 closed with evidence, a33-37 recorded as a new pending carryover, progress.yaml M81 3/8"
  deferred:
    - "M81 T4 chart axes, T5 history chart + scrubber, T6 block order + collapsible Requests + Detail re-categorisation, T7 header, T8 steps 2-6 -> those tasks"
    - "audit-34 G-34-01: test_ui_browser detail-packing asserts >=4 tiles; T6 shrinks the region to 3 and MUST update that assertion in the same commit"
    - "a33-37 System log panel tails only Hermes llama.cpp logs while Strata's own log (6.2 MB, live today) is never read -> needs its own task"
    - "a33-12 sample density depends on open tab count; the ThreadingHTTPServer write race that makes duplicate timestamps is NOT fixed (only its arithmetic consequence is)"
    - "a33-32 saved-layout versioning decision -> must be surfaced to the user before T6 ships"
    - "a32-02 fixed sleeps -> task-81-t8 step 3; a25-02 reboot test -> still user-gated"
    - "restart of :8090 (PID 10496, older than these edits) -> supervisor owns it; its poll table has no prompt_ms column yet, so prefill_weighted is legitimately None there until it restarts"
  key_fact: "A per-poll mean of a session-cumulative ratio is not a window rate — the error varies per snapshot, so it cannot be corrected with a constant. And an assertion that calls a pure helper instead of the code path under test is unfailable: 'bounded prefill in the hour path' only became mutation-provable once it asserted on db_hour_aggregates' own returned record."

- date: 2026-10-26
  executor: zed
  branch: main
  tasks: [audit-33, audit-34, task-81-t1, task-81-t2, task-81-t8-step-1]
  done:
    - "audit-33 (36 findings) on visual presentation + measurement correctness; every claim re-verified against live /api/stats, live /metrics, the registry, the live SQLite DB or a direct experiment"
    - "M81 planned: milestone doc + 8 task docs + progress.yaml block; audit-34 pre-impl pass (8 findings) amended it before any code"
    - "a33-01 GPU named wrong: detect_host_hardware() (stdlib winreg join of Enum\PCI instances to display-class subkeys, ConfigFlags filter) names the live card; 1.3 ms, once at import; name_source os/engine/rated and name_conflict added"
    - "a33-02/03/04/05/07/36 front end: setGauge null renders -- with a striped is-none track, never 0; HUD power gauge (was reading a nonexistent rated_w) fixed via a peak_w alias; HUD context printed 7417.0% for a real 74.2%; HUD VRAM scales by mem_source; stale sparklines cleared"
    - "a33-34 test isolation: LLM_MONITOR_DB override; production poll rows unchanged across a full suite run (20,357 -> 20,357)"
    - "a32-01 closed with evidence: Actions run 40304874790 logs 'ok test_ui_browser.py: 10/10', no NOTRUN"
    - "five new checks (browser 13 / static 9), each mutation-proven against the exact original symptom"
  deferred:
    - "M81 T3 telemetry maths (window-correct hit/accept ratios, prefill outliers, day_aggregates ghost-idle, tests/telemetry) -> task-81-t3"
    - "M81 T4/T5/T6/T7 charts, history, block order + collapsible Requests, header -> those tasks"
    - "audit-34 G-34-01: test_ui_browser detail-packing asserts >=4 tiles; T6 shrinks the region to 3 and MUST update that assertion in the same commit"
    - "a32-02 fixed sleeps -> task-81-t8 step 3 (new checks settle instead of sleeping; older ones still sleep)"
    - "a25-02 reboot test -> still user-gated"
    - "restart of the :8090 server -> supervisor owns it; until then the running dashboard keeps serving the pre-fix GPU name"
  key_fact: "The engine's hardware_static.gpu_name is not a measurement: Strata indexes the Windows display device class in class order, so a leftover driver entry for a removed card (ConfigFlags 32) outranks the installed one. WMI AdapterRAM is a UInt32 cap and must never be used as VRAM total; the registry's qwMemorySize is the trustworthy size."

- date: 2026-10-26
  executor: zed
  branch: main
  tasks: [task-80-t1, task-80-t2, task-80-t3, task-80-t4, task-80-t5]
  done:
    - masonry-row-span-engine (ROW_UNIT 4px, layoutTiles/layoutAll/queueLayout, ResizeObserver)
    - detail-region-full-width + nested .tiles--detail packing (audit-30 F-30-01)
    - tile hierarchy/elevation + opacity-only entrance + 1100px KPI strip order (F-30-05..08)
    - agent/tests/ui/test_ui_browser.py rebuilt stdlib-CDP suite, 10/10 incl. save/reset/drag
    - mutation-proven save-button, masonry-spans, columns-adapt, wide-full-width, detail-packing, reload-restores-order
    - audit-32 (12 findings) and review-014 written; fixed the stale M78 task statuses; closed the dangling active_handoff
    - new browser checks detail-packing, view-toggle-spans, reload-restores-order; removed a false-pass in the reload check
    - records: CHANGELOG 0.2.1, README Layout section, progress.yaml M79+M80, a30-01/a30-02
    - recovery: agent/ restored from git + rebuilt 405 tracked and ~25 untracked docs
    - agent/.gitignore now tracks agent/tests/** so a UI suite can never be lost again
  deferred:
    - a25-02-reboot-test -> still user-gated (unchanged since M76)
    - a32-01-browser-suite-execution-in-ci -> read one Actions run log for 'ok test_ui_browser.py: 10/10'
    - a32-02-fixed-sleeps-in-browser-suite -> settle helper if a false failure is ever seen
    - push-to-remote -> user decision
    - lint-handover L9 fixture paths -> fixed with a labelled T7-receipts placeholder (original unrecoverable)
  key_fact: "gitignored ACP memory (agent/reports, milestones, tasks, sessions, and even untracked test code) has NO backup: one delete_path aimed at a scratch folder destroyed a whole session's work. Never pass a directory to delete tools; the app dir is llm-monitor/llm-monitor so 'llm-monitor/agent' is NOT 'agent'."

- date: 2026-10-17
  executor: zed
  branch: main
  tasks: [task-76-t4, task-76-t7]
  done:
    - fixes-1-5-supervisor-verified (parse + run :8090/8095-8099, HTTP 200)
    - restart-script-empty-array-fix ($owners = Get-OurOwners before foreach)
    - t7-step7-dup-supervisor-exit-0
    - install-verification (user ran install-service.ps1 -WithBoot natively; supervisor-log proof 06:06:45)
    - cleanup-probe-scripts-deleted (~230 files, scratch emptied, spare-port artifacts removed)
    - validate-findings-fixed (M76/M77 status drift -> completed/100)
    - handoff-claude-m76-install-verification written + HANDOFF-LATEST + progress.yaml active_handoff
  deferred:
    - a25-02-reboot-test -> task-76-t6 (user-gated)
  key_fact: "foreach ($x in FuncCall) without parentheses runs the call as a statement and iterates an EMPTY stream — Stop-Process -Id got an empty array; assign first ($owners = Get-OurOwners)"

- date: 2026-10-17
  executor: claude-opus-5-5
  branch: main
  tasks:
    - audit-27-m76-m77-zed-haiku-scoring
    - review-013-m76-m77-code-qualities
    - audit-27-remediation
  done:
    - scored-zed-59-haiku-67
    - gate-g10-checked-stops-and-cleanup
    - shared-kill-pattern-lint-l8-gate-g8
    - lint-head-parameter-and-exact-fixture-sets
    - gate-g7-wider-g1b-syntax-tree
    - restart-stop-request-both-tasks-port-fix
    - supervisor-kill-on-close-job-state-file-stop-request-orphan-takeover
    - s4u-boot-task-run-without-reboot
    - t7-steps-8-9-10-13-pass
    - records-milestones-changelog-readme-agents-skill-carryovers
    - adr-lm-001
    - handoff-zed-audit27-verification
  deferred:
    - reboot-test-decision-b → a25-02 (user)
    - independent-verification-of-audit-27-fixes → handoff-zed-audit27-verification-2026-10-17.md
    - commit-of-m76-m77-audit-27-work → user decision
  key_fact: "Children started with Start-Process leave the scheduled task's job, and an S4U (session 0) chain is invisible and unstoppable from the desktop. The supervisor must own its children (kill-on-close job) and expose a state file and a stop request."

- date: 2026-10-17
  executor: claude-haiku-5-5
  branch: main
  tasks:
    - m76-t0-supervision-restore
    - m76-t3-supervisor-end-log
    - m76-t3-supervisor-simplify
    - m76-t5-restart-rename
    - m77-t0-restore-supervision
    - m77-t1-lessons-labels
    - m77-t2-local-skill
    - m77-t3-taxonomy-route
    - m77-t4-lint-handover
    - m77-t5-gate-service
    - m77-t6-agents-pointer
    - m77-t7-leftovers-carryovers
  done:
    - restored-8090-supervision-owner-chain-verified
    - supervisor-logs-own-end-and-busy-workaround-removed
    - supervision-test-kill-by-pid-restart-11s
    - rotation-to-dot-1-proven-on-spare-port
    - lessons-labels-mapped-to-taxonomy-keys
    - local-handover-executor-skill-written
    - taxonomy-handover-executor-entry-added
    - lint-handover-with-fixtures-and-tests
    - gate-service-with-bare-boolean-check-and-smoke-test
    - agents-md-pointer-and-readme-update-caveat
    - carryover-closures-a25-01-a26-01-03-c22-01-02-04-cr-006
    - progress-active-handoff-cleared
    - analyser-review-of-m77-scripts
  deferred:
    - reboot-test-decision-b-user-gated → a25-02
    - orphan-server-when-supervisor-force-killed → a26-04
    - trap-path-terminating-error-untested → a26-05
    - commit-of-m76-m77-work-not-requested → user decision
  key_fact: "Analyser and parser both pass a bare boolean ($x = false); gate needs a regex check plus a runtime smoke test. Protocol loads lessons by trigger or priority high, not by task_type."

- period: 2026-10-07 to 2026-10-15
  executors: [strata-coder, antigravity-coordinator]
  note: "weekly summary — compacted 10 oldest entries per /acp-commit"
  done:
    - installed-acp-ci-review-integrity-harness (2026-10-15)
    - acp-validate-version-and-pointer-checks, fixed stale current_milestone M1->M75 (2026-10-12)
    - m74-interactive-svg-timeseries-8-timeframes-4-metric-modes (2026-10-12)
    - m73-average-and-peak-throughput-prefill-sparkline (2026-10-12)
    - m72-compact-hud-multi-tab-popout-overlay (2026-10-12)
    - m71-total-tokens-per-request-history-comparison-table (2026-10-12)
    - audit-10-remediations-db-prune-truncation-fix-sqlite-indexes (2026-10-11)
    - decode-speed-surfaced-header-chip-redundant-row-removed (2026-10-08)
    - r3-01-sparkline-per-series-window-label-header-tok (2026-10-08)
    - a7-05-drafts-and-pcie-share-poll-schema-23-col-insert-arity-fix (2026-10-08)
    - audit-7-db-prune-days-rollup-90d-cap-api-export-json-csv (2026-10-08)
    - gpu-2nd-pass-vram-card-relative-gpu-mem-hint-zero-guard-fix (2026-10-08)
    - gpu-vram-derived-from-vram-free-mib-audit-5 (2026-10-07)
    - prefill-gauge-sticky-header-a2-01-telemetry-verified-live (2026-10-07)
    - db-path-resolve-fix-telemetry-status-surfaced (2026-10-07)
  key_facts:
    - "On the AMD HIP driver the engine has NO gpu_* counters; engine.vram_free_mib is live and card-relative, so VRAM is the one recoverable GPU reading (used = fixed card total - free)."
    - "DB_PATH must be .resolve()d — sqlite resolves relative paths against the process cwd."
    - "Static assets are served from disk per request; front-end edits need no server restart, only build_stats changes do."
    - "Engine keeps only 60 samples/series + 12-30 request records and has NO /log endpoint — our SQLite DB is the only durable record."
    - "poll-schema ALTER migrations: INSERT arity bugs are caught by migration tests, not py_compile."
    - "db_prune must prune day rollups too; cap 90d (three months) via db_prune_days."
    - "Windows/Git-Bash process-spawn overhead is ~5-10x a Linux CI host; perf budgets must be host-calibrated (budget=max(2000, 3x measured floor))."


