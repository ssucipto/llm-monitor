/* Local LLM Monitor
 *
 * Loaded as type="module", so it is deferred: the DOM is parsed before this runs.
 * Data comes from the backend's /api/stats endpoint (see server.py), which in turn
 * reads the live engine on port 8080 (/health, /metrics, /slots, /v1/models) plus
 * the Hermes workspace state files and log tails. If that endpoint is unreachable,
 * the badge flips to "Stale" and the page keeps its last rendered state.
 * The element IDs in index.html are the contract between backend and front end.
 */

// ---------- Configuration ----------
const REFRESH_MS = 5000;
const SPARK_SAMPLES = 24;
const STATS_ENDPOINT = "api/stats";
// Per-sample width of the server-bucketed requests series (history_bucket_s seconds).
// Set from the payload each poll so drawSpark can label the requests x-axis honestly;
// the per-poll series (tok_s/prefill/power/cpu/vram) use REFRESH_MS instead.
let historyBucketMs = 75 * 1000;

// ---------- Helpers ----------
const $ = (id) => document.getElementById(id);

function reducedMotion() {
  return matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Re-assigning animation-name starts a fresh animation, which is how the sparkline
// gets redrawn on every poll (a transition cannot be re-triggered this way).
function restart(node, name, ms) {
  node.style.animation = `${name} ${ms}ms cubic-bezier(0.35, 0, 0.2, 1) both`;
}

// Stagger index for the CSS entrance/breathe choreography (style.css multiplies
// --i by a per-element delay).
function stagger(node, i) {
  node.style.setProperty("--i", String(i));
}

// Severity of a reading. higherBetter=true for reuse/accept rates (bigger is good);
// false for utilisation gauges (context, cpu, ram — smaller is good).
function severity(pct, higherBetter) {
  if (higherBetter) {
    if (pct >= 70) return "ok";
    if (pct >= 40) return "warn";
    return "bad";
  }
  if (pct >= 85) return "bad";
  if (pct >= 60) return "warn";
  return "ok";
}

function fmtInt(n) {
  return n === null || n === undefined ? "--" : Math.round(n).toLocaleString("en-US");
}

function fmtBytes(bytes) {
  if (!bytes) return "--";
  const gb = bytes / 1073741824;
  return `${gb.toFixed(1)} GB`;
}

function fmtNum(n, suffix = "", digits = 0) {
  if (n === null || n === undefined) return "--";
  return `${n.toFixed(digits)}${suffix}`;
}

function fmtTime(sec) {
  if (!sec) return "--";
  const d = new Date(sec * 1000);
  return d.toTimeString().slice(0, 8);
}

// Write a text value into an element by id, leaving "--" for missing data.
function setText(id, val) {
  const node = $(id);
  if (node) node.textContent = val === null || val === undefined ? "--" : val;
}

// The big readings ease from their previous value to the new one, so the number
// carries the delta between polls instead of snapping.
const displayed = {};

function tweenNumber(node, to, suffix, digits) {
  const from = displayed[node.id] ?? 0;
  displayed[node.id] = to;

  const commit = (v) => {
    node.textContent = `${v.toFixed(digits)}${suffix}`;
    node.setAttribute("value", v.toFixed(digits));
  };

  if (reducedMotion()) {
    commit(to);
    return;
  }

  const dur = 600;
  const start = performance.now();
  const step = () => {
    const t = Math.min((performance.now() - start) / dur, 1);
    commit(from + (to - from) * (1 - (1 - t) ** 3));
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// A gauge element (data value + sibling <meter>) driven by one percentage.
// M81-T2 (audit-33 a33-02): null means "no reading", and it must never render as 0. A 0 on a
// severity gauge is a claim about the machine — the GPU Temp row showed a definite 0% on a driver
// that exposes no temperature counter at all.
function setGauge(valueId, gaugeId, pct, higherBetter) {
  const value = $(valueId);
  const gauge = $(gaugeId);
  if (!value) return;

  if (pct === null || pct === undefined) {
    setText(valueId, "--");
    clearGauge(gaugeId);
    return;
  }

  tweenNumber(value, pct, "%", 0);
  if (gauge) {
    gauge.setAttribute("value", pct.toFixed(0));
    gauge.classList.remove("is-none");
  }

  value.classList.remove("is-ok", "is-warn", "is-bad");
  value.classList.add(`is-${severity(pct, higherBetter)}`);
}

// An absent reading must not look like a reading. Setting the meter's value to "" is only half
// of it: per HTML, an invalid/missing <meter> value falls back to the minimum, so the bar still
// paints as a zero-width fill — visually the same claim as 0. The is-none class draws a striped
// track over the element and blanks the fill pseudo-elements, so "no data" has its own look.
function clearGauge(gaugeId) {
  const gauge = $(gaugeId);
  if (!gauge) return;
  gauge.setAttribute("value", "");
  gauge.classList.add("is-none");
}

// The HUD sizes its <meter> elements directly (it has no paired data element), so it shares this
// one rule with setGauge rather than re-implementing the null case three times.
function setMeter(gaugeId, pct) {
  const gauge = $(gaugeId);
  if (!gauge) return;
  if (pct === null || pct === undefined) { clearGauge(gaugeId); return; }
  gauge.classList.remove("is-none");
  gauge.setAttribute("value", pct.toFixed(0));
}

// ---------- Drag-and-drop reordering ----------
// M79-T3: one .tiles grid replaces the old .masonry + .band containers. The grid
// reads document order, so a drag commits by moving the panel's DOM node.
// pointermove/pointerup live on the document (not the container) so a drag keeps
// tracking over gaps and footer, and the drop target is hit-tested per move.
// A dashed slot element is inserted at the would-be position and the other panels
// FLIP-part around it, so the drop point is unambiguous before releasing. The
// dragged panel eases toward the pointer (CSS transition while dragging) for a
// fluid follow. The arrangement auto-persists in localStorage on every commit
// (the latest positions are always recorded); the footer Save button confirms it
// explicitly and Reset restores the default order. ?reset=1 clears the save too.
// Old two-container saves ({masonry:[...], band:[...]}) migrate to the single
// list (masonry first, then band), so pre-M79 layouts survive the switch.
const ORDER_KEY = "llm-monitor-order";
// M81-T6 (a33-32): the arrangement is now part of the product, so a saved layout has to know
// which arrangement it was made under. A save carrying the current version is honoured exactly;
// an older or version-less save is replaced by the new defaults and the page says so (#layout-note).
// Rejected: bumping ORDER_KEY outright, which would throw away their order with no notice at all.
const ORDER_VERSION = 2;
const DEFAULT_ORDER = {
  // Engine performance first — what the model is doing right now, then what it has done, then
  // the hardware it is doing it on. Cache and speculative decode are engine readings, so they
  // moved up from the collapsed region; engine config, switch and log are reference material.
  tiles: ["live", "throughput", "context", "cache", "spec", "analysis", "charts",
          "requests", "gpu", "power", "hardware", "usage", "history"],
  detail: ["engine", "switch", "log"],
};
let drag = null;
let container = null;      // primary .tiles
let detailContainer = null; // .tiles--detail inside <details#detail>
let slotEl = null;

function containersList() {
  return [container, detailContainer].filter(Boolean);
}

// ---------- Masonry layout engine (M80-T1, audit-30 F-30-01..03) ----------
// .tiles is a grid with a fine row unit; each tile gets a row span equal to its
// own height plus one gap, so columns pack without gutters while DOM order (the
// drag contract) stays untouched — the engine only writes gridRowEnd.
// align-items:start in CSS keeps the tile box at content height, so measuring
// never depends on the previous span (no reset needed, no RO feedback loop).
const ROW_UNIT = 4;
function layoutTiles(c) {
  if (!c) return;
  const gap = parseFloat(getComputedStyle(c).columnGap) || 0;
  for (const el of c.children) {
    if (el === slotEl) continue; // slot span is set by placeSlot, at drag height
    const h = el.getBoundingClientRect().height;
    if (!h) {
      el.style.gridRowEnd = "auto"; // collapsed (closed details, until-found log)
      continue;
    }
    el.style.gridRowEnd = `span ${Math.max(1, Math.ceil((h + gap) / ROW_UNIT))}`;
  }
}

function layoutAll() {
  for (const c of containersList()) layoutTiles(c);
  // M81-T8 (a32-02): the UI suite must not guess when a layout pass has landed. Every
  // geometry wait polls this stamp (or compares two consecutive span reads) instead of
  // sleeping a fixed interval, so a slow runner cannot produce a flaky read.
  window.__lastLayout = Date.now();
}

let layoutQueued = false;
function queueLayout() {
  if (layoutQueued) return;
  layoutQueued = true;
  requestAnimationFrame(() => {
    layoutQueued = false;
    layoutAll();
  });
}

function persistOrder() {
  const order = { v: ORDER_VERSION };
  if (container) order.tiles = [...container.children].filter((el) => el !== slotEl).map((el) => el.id);
  if (detailContainer) order.detail = [...detailContainer.children].filter((el) => el !== slotEl).map((el) => el.id);
  localStorage.setItem(ORDER_KEY, JSON.stringify(order));
}

// The one visible half of the migration: a replaced layout must never look like the user's own
// order broke itself. The note sits beside Save/Reset so the way back is right next to the news.
function noteLayoutReplaced(reason) {
  const note = $("layout-note");
  if (!note) return;
  const text = $("layout-note-text");
  if (text && reason) text.textContent = reason;
  note.hidden = false;
}

function applyOrder(order) {
  // M79 object form {tiles:[...], detail:[...]}; the pre-M79 two-container form
  // {masonry:[...], band:[...]} migrates into tiles; a bare array is all-tiles.
  if (Array.isArray(order)) order = { tiles: order };
  else if (!order.tiles && (order.masonry || order.band)) {
    // Pre-M79 saves had no usage panel (it post-dates them); append it so a
    // migrated layout does not silently drop the tile.
    const tiles = [...(order.masonry || []), ...(order.band || [])];
    if (!tiles.includes("usage")) tiles.push("usage");
    order = { tiles };
  }
  for (const c of containersList()) {
    const ids = c === container ? order.tiles || [] : order.detail || [];
    const kids = [...c.children].filter((k) => k !== slotEl);
    const byId = new Map(kids.map((k) => [k.id, k]));
    const wanted = ids.map((id) => byId.get(id)).filter(Boolean);
    wanted.concat(kids.filter((k) => !wanted.includes(k)))
      .forEach((el) => c.appendChild(el));
  }
}

function restoreOrder() {
  if (/[?&]reset=1/.test(location.search)) {
    localStorage.removeItem(ORDER_KEY);
    return;
  }
  let saved;
  try {
    saved = JSON.parse(localStorage.getItem(ORDER_KEY) || "null");
  } catch (err) {
    saved = null;
  }
  if (!saved) return;
  if (saved.v === ORDER_VERSION) {
    applyOrder(saved);
    return;
  }
  // Pre-M79 saves ({masonry, band}) and pre-M81 saves (no v) both land here. They were made
  // under an arrangement this release changed, so they get the new defaults plus a notice —
  // silently keeping a stale order would make the change invisible to the person who asked for it.
  applyOrder(DEFAULT_ORDER);
  noteLayoutReplaced(
    "Your saved panel layout predates this release, so the new default arrangement was applied. " +
    "Drag panels to arrange them, then Save layout to keep your own order."
  );
  persistOrder();
}

function hitContainer(x, y) {
  for (const c of containersList()) {
    const r = c.getBoundingClientRect();
    if (r.width || r.height) {
      if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) return c;
    }
  }
  return null;
}

// A drag held over the collapsed Detail region opens it, so the drop target is
// real: while <details> is closed its content is display:none (zero rect) and a
// panel dropped "into" it would be invisible. The summary's own rect is used.
function openDetailForDrag(x, y) {
  const detail = $("detail");
  if (!detail || detail.open) return;
  const sum = detail.querySelector("summary");
  if (!sum) return;
  const r = sum.getBoundingClientRect();
  if (x >= r.left && x <= r.right && y >= r.top - 8 && y <= r.bottom + 8) detail.open = true;
}

// The candidate slot in `container` for a drop at (x, y): nearest sibling by
// centre, before/after decided by the sibling's vertical midpoint. The anchor
// is a real panel element (stable across slot insertions), so the preview can
// tell when the candidate actually changed.
function slotAnchor(container, x, y) {
  let best = null;
  let bestD = Infinity;
  for (const s of container.children) {
    if (s === slotEl || s === (drag && drag.panel)) continue;
    const r = s.getBoundingClientRect();
    if (!r.width || !r.height) continue; // collapsed panels (hidden=until-found)
    const d = (r.left + r.width / 2 - x) ** 2 + (r.top + r.height / 2 - y) ** 2;
    if (d < bestD) {
      bestD = d;
      best = s;
    }
  }
  if (!best) return null;
  const r = best.getBoundingClientRect();
  return { anchor: best, side: y > r.top + r.height / 2 ? "after" : "before" };
}

function placeSlot(x, y) {
  openDetailForDrag(x, y);
  const target = hitContainer(x, y) || (drag && drag.target);
  if (!target || !drag) return;
  drag.target = target;
  // audit-31 P-01: the preview slot must be as tall as the panel it previews —
  // its 46px min-height would collapse between tall masonry neighbours.
  const ph = drag.panel.getBoundingClientRect().height;
  if (ph) {
    const gap = parseFloat(getComputedStyle(target).columnGap) || 0;
    slotEl.style.gridRowEnd = `span ${Math.max(1, Math.ceil((ph + gap) / ROW_UNIT))}`;
  }
  const a = slotAnchor(target, x, y);
  if (!a) return;
  // Only re-part when the candidate slot actually changed, so the preview does
  // not restart its FLIP on every pointermove.
  if (target === drag.slotContainer && a.side === drag.slotSide && a.anchor === drag.slotAnchor) return;
  drag.slotContainer = target;
  drag.slotSide = a.side;
  drag.slotAnchor = a.anchor;
  const first = new Map();
  for (const k of target.children) first.set(k, k.getBoundingClientRect());
  if (a.side === "after") {
    if (a.anchor.nextSibling) target.insertBefore(slotEl, a.anchor.nextSibling);
    else target.appendChild(slotEl);
  } else {
    target.insertBefore(slotEl, a.anchor);
  }
  // Part the other panels smoothly around the new slot (FLIP again).
  if (!reducedMotion()) {
    for (const k of first.keys()) {
      if (k === slotEl || k === drag.panel) continue;
      const f = first.get(k);
      const l = k.getBoundingClientRect();
      const dx = f.left - l.left;
      const dy = f.top - l.top;
      if (!dx && !dy) continue;
      if (typeof k.animate === "function") {
        k.animate(
          [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
          { duration: 180, easing: "cubic-bezier(0.2, 0.85, 0.25, 1)" }
        );
      }
    }
  }
}

function wireContainer(container) {
  container.addEventListener("pointerdown", (e) => {
    if (drag || e.pointerType === "touch") return;
    const panel = e.target.closest(".panel");
    if (!panel || panel.parentElement !== container) return;
    if (e.target !== panel && e.target.tagName.toLowerCase() !== "h2") return;
    drag = { panel, target: container, x: e.clientX, y: e.clientY, dx: 0, dy: 0, moved: false, slotContainer: null, slotSide: null, slotAnchor: null };
    panel.classList.add("dragging");
    placeSlot(e.clientX, e.clientY);
  });
}

document.addEventListener("pointermove", (e) => {
  if (!drag) return;
  drag.dx = e.clientX - drag.x;
  drag.dy = e.clientY - drag.y;
  if (Math.abs(drag.dx) + Math.abs(drag.dy) > 4) drag.moved = true;
  drag.panel.style.transform = `translate(${drag.dx}px, ${drag.dy}px)`;
  placeSlot(e.clientX, e.clientY);
});

document.addEventListener("pointerup", (e) => {
  if (drag) commitDrag(e);
});

document.addEventListener("keydown", (e) => {
  if (drag && e.key === "Escape") cancelDrag();
});

function cancelDrag() {
  const { panel } = drag;
  drag = null;
  panel.classList.remove("dragging");
  panel.style.transform = "";
  if (slotEl) slotEl.remove();
}

function commitDrag(e) {
  const { panel, target } = drag;
  const { dx, dy } = drag;
  const moved = drag.moved;
  drag = null;
  panel.classList.remove("dragging");
  panel.style.transform = "";
  const ref = slotEl.nextSibling;
  slotEl.remove();
  if (!moved) return; // a plain click, not a drag — leave the order alone
  if (ref) target.insertBefore(panel, ref);
  else target.appendChild(panel);
  slotEl.style.gridRowEnd = ""; // audit-31 P-01: clear the drag-height span
  layoutAll(); // M80-T1: the moved panel re-spans into its new column

  // FLIP the resting panels, and glide the dragged one from its hover position
  // to its final slot, so the release reads as one continuous motion.
  if (!reducedMotion() && typeof panel.animate === "function") {
    panel.animate(
      [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
      { duration: 240, easing: "cubic-bezier(0.2, 0.85, 0.25, 1)" }
    );
  }
  persistOrder();
}

// ---------- Data source ----------
async function fetchStats() {
  const res = await fetch(STATS_ENDPOINT, { cache: "no-store" });
  if (!res.ok) throw new Error(`stats ${res.status}`);
  return res.json();
}

// ---------- Engine ----------
function renderEngine(engine, config) {
  const badge = $("engine-active");
  if (badge) {
    const svc = engine.service || engine.active;
    badge.textContent = svc;
    badge.classList.remove("strata", "vulkan", "down");
    if (!engine.port_open) badge.classList.add("down");
    else if (svc === "strata") badge.classList.add("strata");
    else badge.classList.add("vulkan");
  }
  setText("engine-service", engine.service);
  setText("engine-model", engine.model);
  setText("engine-build", engine.build_info);
  setText("engine-loaded", engine.loaded === true ? "loaded" : engine.loaded === false ? "not loaded" : "--");
  setText("engine-path", engine.model_path);

  // Engine configuration knobs: static for the session, so they read as facts
  // rather than gauges. Fractional knobs arrive as strings from the engine.
  const cfg = config || {};
  setText("cfg-pool", cfg.pool_workers);
  setText("cfg-pcie", cfg.pcie_frac);
  setText("cfg-spec", cfg.spec != null ? `${fmtInt(cfg.spec)} deep · MTP ${fmtInt(cfg.mtp_max)} · lookup ${fmtInt(cfg.lookup)}` : "--");
  setText("cfg-min-p", cfg.spec_min_p);
  setText("cfg-arena", cfg.arena_mib != null ? `${cfg.arena_mib} MiB` : "--");
  setText("cfg-elastic", cfg.vram_elastic != null ? (cfg.vram_elastic ? "on" : "off") : "--");
  setText("cfg-conv-slots", cfg.conversation_cache_slots);
  setText("cfg-min-free", cfg.conversation_cache_min_free_mib != null ? `${cfg.conversation_cache_min_free_mib} MiB` : "--");
}

// ---------- Live inference ----------
function renderLive(live, status) {
  const chip = $("live-chip");
  if (chip) {
    const active = status && status.busy;
    chip.textContent = status ? status.activity : "idle";
    chip.classList.remove("active", "idle");
    chip.classList.add(active ? "active" : "idle");
  }
  const state = $("live-state");
  const processing = live && live.state === "processing";
  if (state) {
    state.textContent = live ? live.state : "offline";
    state.classList.remove("processing", "idle");
    state.classList.add(processing ? "processing" : "idle");
  }
  setText("live-phase", live && live.phase);
  setText("live-prompt", live ? fmtInt(live.prompt_tokens) : "--");
  setText("live-generated", live ? fmtInt(live.generated) : "--");
  setText("live-elapsed", live && live.elapsed_s != null ? `${live.elapsed_s.toFixed(0)}s` : "--");
  setText("live-queued", live ? fmtInt(live.queued) : "--");
  setText("live-max", live ? fmtInt(live.max_tokens) : "--");
}

// ---------- Context ----------
function renderContext(ctx) {
  setGauge("ctx-pct", "ctx-gauge", ctx.pct, false);
  const label = ctx.source === "last" ? "last request" : ctx.source === "live" ? "live" : "used / max tokens";
  setText("ctx-hint", ctx.used != null && ctx.max ? `${fmtInt(ctx.used)} / ${fmtInt(ctx.max)} tokens · ${label}` : label);
  setText("ctx-slots", ctx.slots != null ? `${fmtInt(ctx.slots)} slot(s)` : "--");
  setText("ctx-kv-resident", ctx.kv_resident != null ? `${fmtInt(ctx.kv_resident)} tok` : "--");
  setText("ctx-max", ctx.max ? fmtInt(ctx.max) : "--");
}

// ---------- Throughput ----------
function renderThroughput(throughput, history, analysis, totals) {
  const now = $("thr-now");
  if (now) {
    const t = throughput && throughput.now;
    now.textContent = t != null ? `${t.toFixed(1)} tok/s decode` : "idle";
    now.classList.remove("is-ok", "is-warn", "is-bad");
  }
  const mean = throughput && throughput.mean;
  // M81-T3 (a33-09): the server names the window each figure covers, because
  // Average tok/s is a session figure while Peak tok/s is the last hour. Printing
  // the window inline stops two numbers reading as if they described the same span.
  const meanWin = (throughput && throughput.mean_window) || "session";
  setText("thr-mean", mean != null ? `${mean.toFixed(1)} tok/s \u00b7 ${meanWin}` : "--");

  const rec = analysis && analysis.recent;
  const peak = (throughput && throughput.peak) ?? (rec && rec.tok_s_max);
  const peakWin = (throughput && throughput.peak_window) || (rec && rec.window_s ? `last ${Math.round(rec.window_s / 60)} min` : "");
  setText("thr-peak", peak != null ? `${peak.toFixed(1)} tok/s${peakWin ? ` \u00b7 ${peakWin}` : ""}` : "--");

  const pre = throughput && throughput.prefill;
  setText("thr-prefill", pre != null ? `${pre.toFixed(0)} tok/s${throughput.prefill_bounded ? " \u00b7 bounded" : ""}` : "--");

  let preMean = throughput && (throughput.prefill_mean ?? throughput.recent_prefill_mean);
  if (preMean == null && rec && rec.prefill_mean != null) preMean = rec.prefill_mean;
  if (preMean == null && totals && totals.prompt_tokens && totals.prompt_ms && totals.prompt_ms > 0) {
    preMean = Math.max(0, totals.prompt_tokens - (totals.reused || 0)) / (totals.prompt_ms / 1000);
  }
  setText("thr-prefill-mean", preMean != null ? `${preMean.toFixed(0)} tok/s${analysis?.recent?.prefill_bounded ? " \u00b7 bounded" : ""}` : "--");

  const prePeak = (throughput && throughput.prefill_peak) ?? (rec && rec.prefill_max);
  setText("thr-prefill-peak", prePeak != null ? `${prePeak.toFixed(0)} tok/s` : "--");

  let ttft = throughput && throughput.prompt_latency_ms;
  if (ttft == null && totals && totals.requests && totals.prompt_ms) {
    ttft = totals.prompt_ms / totals.requests;
  }
  setText("thr-ttft", ttft != null ? (ttft >= 1000 ? `${(ttft / 1000).toFixed(2)}s` : `${ttft.toFixed(0)}ms`) : "--");

  const reqRate = (throughput && throughput.req_per_min) ?? (rec && rec.req_per_min);
  setText("thr-req-rate", reqRate != null ? `${reqRate.toFixed(1)} req/min` : "--");

  const psrc = throughput && throughput.prefill_source === "last" ? "last request"
    : throughput && throughput.prefill_source === "live" ? "live"
    : throughput && throughput.prefill_source === "engine" ? "engine" : "";
  const src = throughput && throughput.source === "last" ? "last request" : throughput && throughput.source === "live" ? "live" : "";
  setText("thr-source", src || "--");
  setText("thr-prefill-source", psrc || "--");

  drawSpark("thr", history && history.tok_s, "tokens/s", REFRESH_MS);
  drawSpark("prefill", history && history.prefill, "prefill tok/s", REFRESH_MS);
  drawSpark("req", history && history.requests, "requests", historyBucketMs);
}

// A sparkline drawn into any <prefix>-* group. The engine keeps no request-count or
// prefill history, so those series are derived server-side; a flat stretch is the
// whole point of the request chart — it means the engine sat idle.
function drawSpark(prefix, samples, unit, windowMs) {
  const line = $(`${prefix}-spark`);
  const area = $(`${prefix}-area`);
  const head = $(`${prefix}-head`);
  const halo = $(`${prefix}-halo`);
  const caption = $(`${prefix}-caption`);
  if (!line) return;

  const vals = (samples || []).filter((v) => v !== null && v !== undefined).slice(-SPARK_SAMPLES);
  if (vals.length < 2) {
    // audit-33 a33-07: clear the previous curve. Without this, a series that runs out of samples
    // keeps last poll's polyline painted under an "awaiting samples" caption, which reads as data.
    line.setAttribute("points", "");
    if (area) area.setAttribute("points", "");
    if (head) { head.setAttribute("cx", 0); head.setAttribute("cy", 30); }
    if (halo) { halo.setAttribute("cx", 0); halo.setAttribute("cy", 30); }
    if (caption) caption.textContent = `${unit}, awaiting samples`;
    return;
  }

  const max = Math.max(...vals, 1);
  const step = 100 / (SPARK_SAMPLES - 1);
  const offset = SPARK_SAMPLES - vals.length;
  const pts = vals.map((v, i) => [((i + offset) * step), 30 - (v / max) * 28]);
  const text = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`);
  line.setAttribute("points", text.join(" "));

  if (area) {
    const [xLast, yLast] = pts.at(-1);
    area.setAttribute("points", `${pts[0][0].toFixed(1)},30 ${text.join(" ")} ${xLast.toFixed(1)},30`);
    if (head) {
      head.setAttribute("cx", xLast.toFixed(1));
      head.setAttribute("cy", yLast.toFixed(1));
    }
    if (halo) {
      halo.setAttribute("cx", xLast.toFixed(1));
      halo.setAttribute("cy", yLast.toFixed(1));
    }
  }

  restart(line, "spark-draw", 1100);
  if (area) restart(area, "spark-fade", 900);
  if (caption) {
    const min = Math.min(...vals);
    // The x-axis window differs per series: tok_s/prefill/power_w/cpu/hit_pct/vram are
    // one sample per poll (~REFRESH_MS), while the requests series is bucketed server-side
    // into history_bucket_s intervals. State the real per-sample window so the caption
    // never mislabels a bucketed series as per-poll (r3-01).
    const per = windowMs || REFRESH_MS;
    const span = per * vals.length;
    const perLabel = per >= 60000 ? `${(per / 60000).toFixed(0)} min` : `${(per / 1000).toFixed(0)} s`;
    const spanLabel = span >= 60000 ? `≈${(span / 60000).toFixed(0)} min` : `≈${(span / 1000).toFixed(0)} s`;
    caption.textContent = `${unit}, last ${vals.length} samples · ${perLabel}/sample (${spanLabel}) · peak ${max.toFixed(0)} · min ${min.toFixed(0)}`;
  }
}

// ---------- Power ----------
function renderPower(power, history) {
  if (!power) return;
  setGauge("power-total", "power-gauge", power.pct_of_peak, false);
  setText("power-hint", power.pct_of_peak != null ? `${power.total_w} W · ${power.pct_of_peak}% of rated peak` : "of rated peak");
  setText("power-gpu", power.gpu_w != null ? `${power.gpu_w} W${power.gpu_measured_w != null ? " (measured)" : ""}` : "--");
  setText("power-cpu", power.cpu_w != null ? `${power.cpu_w} W` : "--");
  setText("power-peak", power.peak_w != null ? `${power.peak_w} W` : "--");
  // Say plainly whether the figure is a measurement or a modelled estimate, so a
  // modelled number is never read as a real power draw.
  const src = power.source === "measured" ? "measured"
    : power.source === "modelled" ? `modelled (${power.model && power.model.gpu_name})`
    : power.source === "unavailable" ? "unavailable" : "--";
  setText("power-source", src);
  drawSpark("pw", history && history.power_w, "watts", REFRESH_MS);
}

// ---------- GPU ----------
// Parity with the engine's own monitor, which draws gpu/gpu_mem/temp/power/pcie
// cards. On builds whose driver exposes no userspace counter (AMD HIP) the engine
// leaves every gpu_* key null, so the payload labels each reading by where it came
// from: measured (a real counter), derived (VRAM from the engine's live vram_free_mib),
// modelled (engine state), or rated (this machine's card). Nothing is presented as a
// measurement it cannot make.
// Where a GPU name came from, in words the operator can read. One table shared by the GPU panel
// and the Hardware panel so the two can never label the same source differently (M81-T1).
const NAME_SOURCE_TAG = { os: "via OS", engine: "via engine", rated: "rated" };

// A derived VRAM figure is in MiB (the engine reports vram_free_mib); a driver counter would
// report bytes. One rule, used by the GPU panel and the HUD alike, so they cannot drift.
function vramScale(gpu) {
  return gpu.mem_source === "derived" ? 1048576 : 1;
}

function renderGpu(gpu, history, power) {
  if (!gpu) return;
  const gpuCaption = $("gpu-caption");
  const state = $("gpu-state");
  if (state) {
    const measured = gpu.util_source === "measured" || gpu.mem_source === "measured"
      || gpu.power_source === "measured" || gpu.temp_c != null;
    const inferred = gpu.util_source === "modelled" || gpu.mem_source === "derived";
    state.textContent = measured ? "counters live"
      : inferred ? "modelled — no driver counters"
      : gpu.name ? "no counters on this driver" : "no gpu readings";
    state.classList.remove("measured");
    if (measured) state.classList.add("measured");
    // audit-33 a33-01: the engine names the wrong adapter on a PC with a leftover display-class
    // entry. We resolve the name off the OS and show the disagreement instead of picking silently.
    if (gpu.name_conflict) state.textContent += ` — engine says ${gpu.name_conflict}`;
  }
  setGauge("gpu-util", "gpu-util-gauge", gpu.util_pct, false);
  setGauge("gpu-mem", "gpu-mem-gauge", gpu.mem_pct, false);
  // A derived figure is in MiB (the engine reports vram_free_mib); a counter the
  // engine supplies would be bytes, so scale by the source rather than assume.
  const scale = vramScale(gpu);
  // Guard with != null, not truthiness: a fully-free card legitimately reports mem_used
  // === 0, which must render as "0 MiB / 24 GiB", not fall back to the placeholder.
  setText("gpu-mem-hint", gpu.mem_used != null && gpu.mem_total != null
    ? `${fmtBytes(gpu.mem_used * scale)} / ${fmtBytes(gpu.mem_total * scale)}${gpu.mem_source === "derived" ? " · derived" : ""}`
    : "used / total");
  // Temperature is a fraction of a 100 °C ceiling, so the gauge reads severity.
  setGauge("gpu-temp", "gpu-temp-gauge", gpu.temp_c != null ? Math.min(100, gpu.temp_c) : null, false);
  const gpuW = gpu.power_w != null ? gpu.power_w : (power && power.gpu_w);
  setText("gpu-power", gpuW != null
    ? `${gpuW} W${gpu.power_limit_w ? ` / ${gpu.power_limit_w} limit` : ""}${gpu.power_source === "modelled" ? " · modelled" : ""}`
    : "--");
  setText("gpu-pcie", gpu.pcie_rx_mb != null ? `${gpu.pcie_rx_mb.toFixed(1)} MB${gpu.pcie_gen ? ` · gen ${gpu.pcie_gen}/${gpu.pcie_gen_max ?? gpu.pcie_gen} · ${gpu.pcie_width ?? "--"}G` : ""}` : "--");
  // M81-T1 (a33-01): name + where the name came from. "(rated)" used to be the only tag; an
  // engine-supplied string is no longer shown as if it were measured, because it is not.
  setText("gpu-name", gpu.name
    ? `${gpu.name} ×${gpu.count ?? 1}${NAME_SOURCE_TAG[gpu.name_source] ? ` (${NAME_SOURCE_TAG[gpu.name_source]})` : ""}`
    : (gpu.count ? `${gpu.count} GPU(s)` : "--"));
  // VRAM is the one GPU reading this driver can supply, so prefer its series; a build
  // with real gpu_* counters (e.g. NVML) still gets the utilisation sparkline.
  const vramSeries = history && history.vram_pct;
  const utilSeries = history && history.gpu_util;
  if (vramSeries || utilSeries) {
    const isVram = !!vramSeries;
    drawSpark("gpu", isVram ? vramSeries : utilSeries,
      isVram ? "% vram used" : "% gpu util", REFRESH_MS);
  } else if (gpuCaption) {
    // No series to draw yet, so say why in the caption rather than leaving a blank
    // chart that reads as a flat zero.
    gpuCaption.textContent = gpu.history_available
      ? "vram in use, awaiting samples"
      : gpu.name
        ? `no gpu counters on ${gpu.name}`
        : "no gpu counters on this driver";
  }
}
function renderAnalysis(analysis, telemetry, totals) {
  const recent = analysis && analysis.recent;
  const previous = analysis && analysis.previous;
  if (!recent) {
    // Distinguish "the DB is off" from "the DB is warming up" — an empty trend with no
    // explanation is otherwise read as a quiet engine.
    setText("an-window", telemetry && telemetry.ok === false
      ? `telemetry off — ${telemetry.error}`
      : "awaiting history");
    ["an-requests", "an-tok", "an-prefill", "an-hit", "an-accept", "an-idle", "an-energy", "an-trend"].forEach((id) => setText(id, "--"));
    renderSession(totals);
    return;
  }
  setText("an-window", `last ${Math.round((recent.span_s || 0) / 60)} min`);
  setText("an-requests", recent.requests != null ? `${fmtInt(recent.requests)} · ${recent.req_per_min}/min` : "--");
  setText("an-tok", recent.tok_s_mean != null ? `${recent.tok_s_mean.toFixed(1)} mean · ${(recent.tok_s_max ?? 0).toFixed(1)} peak` : "--");
  setText("an-prefill", recent.prefill_mean != null ? `${recent.prefill_mean.toFixed(0)} tok/s${recent.prefill_bounded ? " \u00b7 bounded" : ""}` : "--");
  // M81-T3 (a33-08): the window's OWN ratio, not a mean of session-cumulative per-poll
  // ratios. hit_pct_mean answers "since the engine started", which is not what this
  // panel's label claims; on this PC that was 65.96% shown against a true 88.19%.
  const hitW = recent.hit_pct_window ?? recent.hit_pct_mean;
  const accW = recent.accept_pct_window ?? recent.accept_pct_mean;
  setText("an-hit", hitW != null ? `${hitW.toFixed(0)}%` : "--");
  setText("an-accept", accW != null ? `${accW.toFixed(0)}%` : "--");
  setText("an-idle", recent.idle_pct != null ? `${recent.idle_pct.toFixed(0)}% idle` : "--");
  setText("an-energy", recent.energy_wh != null ? `${recent.energy_wh} Wh` : "--");

  // Trend: compare this window to the one before it, so the reading says whether the
  // engine is working more or less than it was an hour ago. A prior window can
  // legitimately have 0 requests, so test for presence, not truthiness.
  if (previous && previous.requests != null && recent.requests != null) {
    const d = recent.requests - previous.requests;
    const arrow = d > 0 ? "▲" : d < 0 ? "▼" : "=";
    setText("an-trend", `${arrow} ${Math.abs(d)} requests vs prior window`);
  } else {
    setText("an-trend", "no prior window yet");
  }
  renderSession(totals);
}

// Lifetime totals for the running engine session — a "look back" line that stays
// useful even before the SQLite window has enough samples to analyse.
function renderSession(totals) {
  const t = totals || {};
  setText("an-session", `session totals — since ${fmtSince(t.since)} · ${fmtInt(t.requests)} requests · ${fmtInt(t.prompt_tokens)} prompt · ${fmtInt(t.output_tokens)} output`);
}

// The engine's `since` is an epoch (seconds or ms) or an ISO string depending on
// build; normalise both to a clock time, and fall back to the raw value if it is
// neither, so the line never reads "Invalid Date".
function fmtSince(v) {
  if (v === null || v === undefined) return "--";
  let d = null;
  if (typeof v === "number") {
    d = new Date(v < 1e12 ? v * 1000 : v);
  } else {
    d = new Date(v);
  }
  return d && !Number.isNaN(d.getTime()) ? d.toLocaleString() : String(v);
}

// ---------- Hardware ----------
function renderHardware(hw) {
  setGauge("hw-cpu", "hw-cpu-gauge", hw.cpu_pct, false);
  setGauge("hw-ram", "hw-ram-gauge", hw.ram_pct, false);
  setText("hw-ram-hint", hw.ram_used != null && hw.ram_total != null ? `${fmtBytes(hw.ram_used)} / ${fmtBytes(hw.ram_total)}` : "used / total");
  setText("hw-vram", hw.vram_free_mib != null ? `${hw.vram_free_mib} MiB free` : "--");
  setText("hw-disk", hw.disk_read_mb != null ? `${hw.disk_read_mb.toFixed(1)} / ${fmtNum(hw.disk_write_mb, "", 1)} MB` : "--");
  // M81-T1 (a33-06): this row used to read the engine's raw field, which could print "1 GPU(s)"
  // or name a card that is not installed. The server now resolves gpu_name the same way the GPU
  // panel gets it, so the two panels cannot disagree.
  setText("hw-gpu", hw.gpu_name
    ? `${hw.gpu_name} ×${hw.gpu_count ?? 1}${NAME_SOURCE_TAG[hw.gpu_name_source] ? ` (${NAME_SOURCE_TAG[hw.gpu_name_source]})` : ""}`
    : (hw.gpu_count ? `${hw.gpu_count} GPU(s)` : "--"));
  setText("hw-cpu-name", hw.cpu_name ? `${hw.cpu_name} · ${hw.cores}c/${hw.threads}t` : "--");
}

// ---------- Cache ----------
function renderCache(cache) {
  setGauge("cache-hit", "cache-gauge", cache.hit_rate != null ? cache.hit_rate * 100 : null, true);
  setText("cache-hint", "prompt-token reuse");
  setText("cache-kv", cache.kv_type);
  setText("cache-expert", cache.expert_slots != null ? fmtInt(cache.expert_slots) : "--");
  setText("cache-expert-mib", cache.expert_cache_mib != null ? `${cache.expert_cache_mib} MiB` : "--");
  setText("cache-reused", cache.reused_tokens != null ? `${fmtInt(cache.reused_tokens)} / ${fmtInt(cache.prompt_tokens)}` : "--");
  const conv = cache.conversation_cache || {};
  setText("cache-conv", conv.enabled ? `on · ${fmtBytes(conv.bytes)} · ${fmtInt(conv.parked)} parked` : conv.enabled === false ? "off" : "--");
  setText("cache-parks", conv.parks != null ? `${fmtInt(conv.parks)} / ${fmtInt(conv.restores)}` : "--");
  setText("cache-evictions", conv.evictions != null ? fmtInt(conv.evictions) : "--");
}

// ---------- Speculative decode ----------
function renderSpec(spec) {
  setGauge("spec-accept", "spec-gauge", spec.accept_rate != null ? spec.accept_rate * 100 : null, true);
  setText("spec-hint", "draft accept rate");
  setText("spec-drafts", spec.drafts_offered != null ? `${fmtInt(spec.drafts_accepted)} / ${fmtInt(spec.drafts_offered)}` : "--");
  setText("spec-mtp", spec.mtp_max != null ? `MTP ${spec.mtp_max} · lookup ${spec.lookup ?? 0}` : "--");
  setText("spec-min-p", spec.min_p != null ? `${spec.min_p}` : "--");
}

// ---------- Requests ----------
function renderRequests(requests, kept) {
  const tbody = $("request-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  requests.forEach((r, i) => {
    const tr = document.createElement("tr");
    stagger(tr, i);
    const cells = [
      fmtTime(r.time),
      r.duration_s != null ? `${r.duration_s.toFixed(1)}s` : "--",
      r.finish || "--",
      fmtInt(r.total_tokens ?? ((r.prompt_tokens ?? 0) + (r.output_tokens ?? 0))),
      fmtInt(r.prompt_tokens),
      r.prompt_read != null ? fmtInt(r.prompt_read) : "--",
      r.reused != null ? fmtInt(r.reused) : "--",
      fmtInt(r.output_tokens),
      r.decode_tok_s != null ? r.decode_tok_s.toFixed(1) : "--",
      r.hit_rate != null ? `${(r.hit_rate * 100).toFixed(0)}%` : "--",
      r.drafts_offered ? `${((r.drafts_accepted ?? 0) / r.drafts_offered * 100).toFixed(0)}%` : "--",
    ];
    cells.forEach((val, c) => {
      const td = document.createElement("td");
      if (c !== 2) td.className = "num";
      td.textContent = val;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });

  let countText = kept ? `${requests.length} recent · ${fmtInt(kept)} kept` : `${requests.length} recent`;
  if (requests.length >= 2) {
    const r0 = requests[0], r1 = requests[1];
    const t0 = r0.total_tokens ?? ((r0.prompt_tokens ?? 0) + (r0.output_tokens ?? 0));
    const t1 = r1.total_tokens ?? ((r1.prompt_tokens ?? 0) + (r1.output_tokens ?? 0));
    if (t0 != null && t1 != null) {
      const diff = t0 - t1;
      const pct = t1 > 0 ? ((diff / t1) * 100) : 0;
      const sign = diff >= 0 ? "+" : "";
      countText += ` · last vs prev: ${fmtInt(t0)} vs ${fmtInt(t1)} (${sign}${fmtInt(diff)} tok, ${fmtDelta(pct)})`;
    }
  } else if (requests.length === 1) {
    const r0 = requests[0];
    const t0 = r0.total_tokens ?? ((r0.prompt_tokens ?? 0) + (r0.output_tokens ?? 0));
    if (t0 != null) {
      countText += ` · last: ${fmtInt(t0)} tokens`;
    }
  }
  setText("requests-count", countText);
}

// ---------- Switch ----------
function renderSwitch(sw) {
  const active = $("switch-engine");
  if (active) {
    active.textContent = sw.engine_active || "--";
    active.classList.remove("strata", "vulkan", "down");
    if (sw.engine_active === "strata") active.classList.add("strata");
    else if (sw.engine_active === "vulkan") active.classList.add("vulkan");
    else if (sw.engine_active === "switching") active.classList.add("processing");
  }
  setText("switch-profile", sw.llama_active_profile);
  setText("switch-owner", sw.owner);
  setText("switch-pid", sw.pid);

  const list = $("switch-profiles");
  if (list) {
    list.innerHTML = "";
    (sw.profiles || []).forEach((name) => {
      const li = document.createElement("li");
      li.textContent = name;
      if (name === sw.llama_active_profile) li.className = "active";
      list.appendChild(li);
    });
  }
}

// ---------- System log ----------
function renderLog(entries) {
  const list = $("log-list");
  if (!list) return;
  list.innerHTML = "";

  entries.forEach((e, i) => {
    const li = document.createElement("li");
    li.className = `lvl--${e.level}`;
    stagger(li, i);

    if (e.iso) {
      const when = document.createElement("time");
      when.setAttribute("datetime", e.iso);
      when.textContent = new Date(e.iso).toLocaleTimeString();
      li.appendChild(when);
    }
    const src = document.createElement("span");
    src.textContent = `[${e.source}] `;
    li.appendChild(src);
    li.appendChild(document.createTextNode(e.msg));
    list.appendChild(li);
  });
}

// The log ships collapsed with hidden="until-found"; the browser removes the
// attribute when find-in-page or a fragment link reveals it. Mark that moment.
function wireLogReveal() {
  const log = $("log");
  if (!log) return;
  log.addEventListener("beforematch", () => {
    log.classList.add("revealed");
  });
}

// M79-T4: the Detail region opens itself when a TOC anchor or Ctrl-F (find-in-page)
// targets a panel inside it, so hidden-never-deleted stays navigable.
function wireDetail() {
  const detail = $("detail");
  if (!detail) return;
  // M81-T6: only the Reference panels live in this region now. Attaching these to a panel that
  // moved into the main grid would open the region for an unrelated find-in-page hit.
  for (const id of ["engine", "switch", "log"]) {
    const el = $(id);
    if (el) el.addEventListener("beforematch", () => { detail.open = true; });
  }
  window.addEventListener("hashchange", () => {
    const target = location.hash.slice(1);
    if (target && detail.querySelector(`#${CSS.escape(target)}`)) detail.open = true;
  });
  // A pending anchor present at load (deep link) also opens it.
  if (location.hash) {
    const target = location.hash.slice(1);
    if (target && detail.querySelector(`#${CSS.escape(target)}`)) detail.open = true;
  }
}

// ---------- Header liveness (M81-T7 / a33-28) ----------
// The badge only ever said whether *this tab* managed to poll. Nothing said how long the
// engine has been up or how old the numbers on screen are, which is what a reader actually
// wants when a figure looks wrong. Both are rendered here and re-ticked every second with
// the clock, so the age stays honest between polls.
let lastPollOkAtMs = 0;

function fmtDuration(ms) {
  if (!(ms >= 0)) return "--";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h ${String(m % 60).padStart(2, "0")}m`;
  return `${Math.floor(h / 24)}d ${h % 24}h`;
}

function renderLiveness(totals) {
  if (totals && totals.since != null) {
    const since = Number(totals.since);
    const startedAt = Number.isFinite(since) ? (since < 1e12 ? since * 1000 : since) : NaN;
    // Never print a bogus duration: an unparseable `since` prints "--".
    setText("top-uptime", Number.isFinite(startedAt) ? fmtDuration(Date.now() - startedAt) : "--");
  } else {
    setText("top-uptime", "--");
  }
  tickAge();
}

function tickAge() {
  setText("top-age", lastPollOkAtMs ? fmtDuration(Date.now() - lastPollOkAtMs) : "--");
}

// ---------- Clock ----------
function tickClock() {
  const now = new Date();
  const timeStr = now.toLocaleTimeString();
  const isoStr = now.toISOString();
  const clock = $("clock");
  if (clock) {
    clock.textContent = timeStr;
    clock.setAttribute("datetime", isoStr);
  }
  const hudClock = $("hud-clock");
  if (hudClock) {
    hudClock.textContent = timeStr;
    hudClock.setAttribute("datetime", isoStr);
  }
  tickAge();
}

// ---------- Live refresh ----------
function setBadge(error) {
  const badge = $("refresh-badge");
  badge.classList.toggle("is-error", !!error);
  badge.textContent = error ? "Stale" : "Live";
}

// Which engine endpoints the backend could reach this poll — a compact health
// readout so a partial outage is visible without opening the console.
function renderEndpoints(endpoints) {
  const node = $("endpoints-status");
  if (!node) return;
  const ep = endpoints || {};
  const mark = (ok) => ok ? "✓" : "✗";
  node.textContent = ["health", "metrics", "slots", "models", "status"]
    .map((k) => `${k} ${mark(ep[k])}`).join(" · ");
}

function renderHero(throughput, power, context, cache, status) {
  const tok = throughput && throughput.now;
  setText("hero-tok", tok != null ? `${tok.toFixed(1)}` : "--");
  const state = status && status.state;
  setText("hero-state", stateName(state));
  // M81-T7: the state cell gets the same orb the HUD uses, so the header reads its
  // state at a glance instead of only as a word.
  const orb = $("hero-orb");
  if (orb) {
    orb.className = "kpi__orb";
    if (state === "reading") orb.classList.add("is-reading");
    else if (state === "generating" || state === "processing") orb.classList.add("is-generating");
    else if (status && status.ok === false) orb.classList.add("is-down");
    else orb.classList.add("is-idle");
  }
  setText("hero-power", power && power.total_w != null ? `${power.total_w}` : "--");
  // Two decimals: the gauge rounds to whole percents, but the headline reading
  // should not hide a 0.4-point change in a 200k-token window.
  setText("hero-ctx", context && context.pct != null ? `${context.pct.toFixed(2)}` : "--");
  setText("hero-hit", cache && cache.hit_rate != null ? `${(cache.hit_rate * 100).toFixed(0)}` : "--");
}

// The prefill speed gauge lives in the sticky top bar as its own full-width band
// under the measurements (not the native <meter>, which cannot be gradient-lit or
// given a sliding knob). setPrefillGauge drives both the fill width and the knob
// position; a CSS transition on each eases them together so the meter rises and
// falls in realtime as the prefill rate changes. The reduced-motion block snaps it.
//
// M81-T7 (a33-27): the ceiling used to be a hardcoded 2000 tok/s. Live readings on this
// engine sit at p50 ~345 / p90 ~1,093, so the bar was pinned near zero and read as "nothing
// happening", while one bad sample still pegged it at 100%. The ceiling now tracks the
// recent peak of the published series. history.prefill is already bounded server-side at
// PREFILL_CEILING_TOK_S (M81-T3 / a33-10), so an impossible outlier can never set the scale.
const PREFILL_CEILING_MIN = 600;
let prefillCeilingValue = PREFILL_CEILING_MIN;

function prefillCeiling(samples) {
  const vals = (samples || []).filter((v) => v != null && v > 0).sort((a, b) => a - b);
  if (vals.length >= 5) {
    const p95 = vals[Math.min(vals.length - 1, Math.floor(0.95 * (vals.length - 1)))];
    const want = Math.max(PREFILL_CEILING_MIN, Math.ceil(p95 * 1.25));
    // Hysteresis: re-deriving the scale every poll would make bar movements meaningless,
    // so only adopt a ceiling that shifts the scale by more than 20%.
    if (Math.abs(want - prefillCeilingValue) / prefillCeilingValue > 0.2) {
      prefillCeilingValue = want;
    }
  }
  return prefillCeilingValue;
}

function setPrefillGauge(val, ceiling = PREFILL_CEILING_MIN) {
  const gauge = $("top-gauge");
  if (!gauge) return;
  // A null reading leaves the bar empty (a fill bar has no way to express "unknown"
  // except by claiming nothing, so it claims nothing) and says so in the label.
  const pct = val == null ? 0 : Math.max(0, Math.min(1, val / ceiling));
  const width = `${(pct * 100).toFixed(1)}%`;
  gauge.setAttribute("aria-valuenow", String(Math.round(pct * 100)));
  gauge.setAttribute(
    "aria-label",
    val == null
      ? `prefill speed gauge — no reading, scale to ${fmtInt(ceiling)} tok/s`
      : `prefill speed gauge — ${val.toFixed(0)} of ${fmtInt(ceiling)} tok/s`,
  );
  const fill = $("top-gauge-fill");
  if (fill) fill.style.width = width;
  const knob = $("top-gauge-knob");
  if (knob) knob.style.left = width;
}

function stateName(state) {
  return {
    reading: "Reading",
    generating: "Generating",
    processing: "Processing",
    queued: "Queued",
    idle: "Idle",
  }[state || ""] || "--";
}

// The prefill speed meter lives in the sticky top bar (not the hero) so it stays
// pinned at the top while the page scrolls. renderTopbar takes throughput too.
//
// M81-T7 (a33-26/27/28): the header used to print throughput.now twice (once here as
// "decode tok/s", once in the KPI strip) and the gauge had no visible label. The decode
// figure now lives only in the strip; #top-tok stays updated but hidden, so the id contract
// and any consumer of it survive. The prefill figure moved into the strip next to the text
// that names the gauge's scale.
function renderTopbar(engine, throughput, history) {
  const pre = throughput && throughput.prefill;
  const ceiling = prefillCeiling(history && history.prefill);
  setText("top-prefill", pre != null ? `${pre.toFixed(0)}` : "--");
  setPrefillGauge(pre, ceiling);
  setText("top-gauge-ceiling", `gauge to ${fmtInt(ceiling)}`);
  const tok = throughput && throughput.now;
  setText("top-tok", tok != null ? `${tok.toFixed(1)}` : "--");
  const host = $("top-identity");
  if (!host) return;
  const svc = engine.service || engine.active;
  const mark = $("top-mark");
  const engineEl = $("top-engine");
  const modelEl = $("top-model");
  setText("top-build", engine.build_info || "--");
  const known = svc === "strata" || svc === "vulkan";
  if (mark) {
    mark.innerHTML = brandMark(svc, engine.port_open);
    mark.classList.remove("strata", "vulkan", "down");
    if (!engine.port_open) mark.classList.add("down");
    else if (svc === "strata") mark.classList.add("strata");
    else if (svc === "vulkan") mark.classList.add("vulkan");
  }
  if (engineEl) {
    engineEl.textContent = known ? (svc === "strata" ? "Strata Coder" : "Vulkan llama.cpp") : String(svc || "unknown");
    engineEl.classList.remove("strata", "vulkan", "down");
    if (!engine.port_open) engineEl.classList.add("down");
    else if (svc === "strata") engineEl.classList.add("strata");
    else if (svc === "vulkan") engineEl.classList.add("vulkan");
  }
  if (modelEl) modelEl.textContent = engine.model || "--";
}

function brandMark(svc, portOpen) {
  if (!portOpen) return "";
  if (svc === "strata") {
    // Three stacked layers: the strata the engine reads its context from.
    return `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4 20 9 12 14 4 9Z"/><path d="M4 13 12 18 20 13" opacity=".55"/><path d="M4 17 12 22 20 17" opacity=".3"/></svg>`;
  }
  if (svc === "vulkan") {
    // The Vulkan triangle-ish mark rendered as a bold V over a ring.
    return `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9" opacity=".4"/><path d="M6 5 12 19 18 5"/></svg>`;
  }
  return "";
}

// ---------- History (daily rollups, period comparisons, day scrubber) ----------
let days = [];

function fmtDelta(v) {
  if (v === null || v === undefined) return "";
  const r = Math.round(v * 10) / 10;
  return r > 0 ? `+${r}%` : r < 0 ? `${r}%` : "±0%";
}

function cmp(cur, prev, key) {
  const a = cur && cur[key];
  const b = prev && prev[key];
  if (a === null || a === undefined || b === null || b === undefined || b === 0) return "";
  return ` (${fmtDelta(((a - b) / b) * 100)} vs prev)`;
}

function periodLine(p) {
  if (!p || !p.current) return "--";
  const c = p.current;
  const bits = [`${fmtInt(c.requests)} req`, `${fmtNum(c.tok_s_mean, " tok/s", 1)}`];
  if (c.energy_wh != null) bits.push(`${fmtNum(c.energy_wh, " Wh", 1)}`);
  const line = `${p.current_label} ${bits.join(" · ")}`;
  return `${line}${cmp(c, p.previous, "requests")}${cmp(c, p.previous, "tok_s_mean")}`;
}

function renderHistory(periods, daily, requests) {
  days = daily || [];
  setText("hist-window", days.length
    ? `${days.length} recorded day(s) · ${days[0].date} → ${days.at(-1).date}`
    : "awaiting history");

  const reqPeriod = (periods && periods.request) || (() => {
    const reqs = requests || [];
    if (!reqs.length) return null;
    const r0 = reqs[0];
    const r1 = reqs.length >= 2 ? reqs[1] : null;
    const t0 = r0 ? (r0.total_tokens ?? ((r0.prompt_tokens ?? 0) + (r0.output_tokens ?? 0))) : null;
    const t1 = r1 ? (r1.total_tokens ?? ((r1.prompt_tokens ?? 0) + (r1.output_tokens ?? 0))) : null;
    return {
      current: r0 ? { requests: 1, total_tokens: t0, tok_s_mean: r0.decode_tok_s } : null,
      previous: r1 ? { requests: 1, total_tokens: t1, tok_s_mean: r1.decode_tok_s } : null,
      current_label: "Last request",
      previous_label: "Previous request",
    };
  })();

  const th = periods && periods.token_history;
  const lastTok = (th && th.last_request != null)
    ? th.last_request
    : (reqPeriod?.current?.total_tokens ?? (requests && requests[0] ? (requests[0].total_tokens ?? ((requests[0].prompt_tokens ?? 0) + (requests[0].output_tokens ?? 0))) : null));

  setText("hist-tokens-request", lastTok != null ? `${fmtInt(lastTok)} tokens` : "--");
  setText("hist-tokens-hour", th && th.this_hour != null ? `${fmtInt(th.this_hour)} tokens` : (periods?.hour?.current?.total_tokens != null ? `${fmtInt(periods.hour.current.total_tokens)} tokens` : "--"));
  setText("hist-tokens-today", th && th.today != null ? `${fmtInt(th.today)} tokens` : (periods?.day?.current?.total_tokens != null ? `${fmtInt(periods.day.current.total_tokens)} tokens` : "--"));
  setText("hist-tokens-yesterday", th && th.yesterday != null ? `${fmtInt(th.yesterday)} tokens` : (periods?.day?.previous?.total_tokens != null ? `${fmtInt(periods.day.previous.total_tokens)} tokens` : "--"));
  setText("hist-tokens-week", th && th.this_week != null ? `${fmtInt(th.this_week)} tokens` : (periods?.week?.current?.total_tokens != null ? `${fmtInt(periods.week.current.total_tokens)} tokens` : "--"));
  setText("hist-tokens-month", th && th.this_month != null ? `${fmtInt(th.this_month)} tokens` : (periods?.month?.current?.total_tokens != null ? `${fmtInt(periods.month.current.total_tokens)} tokens` : "--"));

  const tbody = $("history-comparison-tbody");
  if (tbody) {
    tbody.innerHTML = "";
    const pairs = [
      // M81-T5 (a33-25): the day/week/month buckets are UTC epoch days (_iso_day), while
      // timestamps elsewhere on the page render local. Naming the alignment in the row keeps
      // "Today" from meaning two different things on one screen.
      { label: "Last request vs Previous", p: reqPeriod },
      { label: "This hour vs Last hour", p: periods?.hour },
      { label: "Today vs Yesterday (UTC)", p: periods?.day },
      { label: "This week vs Last week (UTC)", p: periods?.week },
      { label: "This month vs Last month (UTC)", p: periods?.month },
    ];
    pairs.forEach((row, i) => {
      const tr = document.createElement("tr");
      stagger(tr, i);
      const cur = row.p && row.p.current;
      const prev = row.p && row.p.previous;

      let tokenDelta = "--";
      let deltaClass = "";
      if (cur && prev && cur.total_tokens != null && prev.total_tokens != null) {
        if (prev.total_tokens === 0) {
          if (cur.total_tokens > 0) {
            // M81-T3 (a33-16): a percentage out of an empty prior period is not a
            // number — +100% implied the prior period was half this size. Say what
            // actually happened instead.
            tokenDelta = `new (+${fmtInt(cur.total_tokens)} tok)`;
            deltaClass = "is-warn";
          } else {
            tokenDelta = "\u00b10%";
          }
        } else {
          const d = ((cur.total_tokens - prev.total_tokens) / prev.total_tokens) * 100;
          tokenDelta = fmtDelta(d);
          deltaClass = d > 0 ? "is-warn" : d < 0 ? "is-ok" : "";
        }
      }

      let reqDelta = "--";
      if (cur && cur.requests != null) {
        reqDelta = fmtInt(cur.requests);
        if (prev && prev.requests != null && (cur.requests !== 1 || prev.requests !== 1)) {
          if (prev.requests === 0) {
            if (cur.requests > 0) {
              // M81-T3 (a33-16): same reason as the token delta above.
              reqDelta += ` (new, +${fmtInt(cur.requests)})`;
            }
          } else {
            const d = ((cur.requests - prev.requests) / prev.requests) * 100;
            reqDelta += ` (${fmtDelta(d)})`;
          }
        }
      }

      let tokDelta = "--";
      if (cur && cur.tok_s_mean != null) {
        tokDelta = fmtNum(cur.tok_s_mean, " tok/s", 1);
        if (prev && prev.tok_s_mean != null && prev.tok_s_mean > 0) {
          const d = ((cur.tok_s_mean - prev.tok_s_mean) / prev.tok_s_mean) * 100;
          tokDelta += ` (${fmtDelta(d)})`;
        }
      } else if (cur && cur.requests === 0) {
        tokDelta = "--";
      }

      const cells = [
        { text: row.label, num: false },
        { text: cur && cur.total_tokens != null ? fmtInt(cur.total_tokens) : "--", num: true },
        { text: prev && prev.total_tokens != null ? fmtInt(prev.total_tokens) : "--", num: true },
        { text: tokenDelta, num: true, cls: deltaClass },
        { text: reqDelta, num: true },
        { text: tokDelta, num: true },
      ];

      cells.forEach((c) => {
        const td = document.createElement("td");
        if (c.num) td.className = "num";
        if (c.cls) td.classList.add(c.cls);
        td.textContent = c.text;
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  drawSpark("hist", days.map((x) => x.requests), "req/day", 86400000);
  renderHistBars();
  selectDay(Math.min(scrubIdx, Math.max(0, days.length - 1)), true);
}

// M81-T5 (a33-23): the History panel drew up to 90 daily values into a 100x30 sparkline —
// no axis, no ticks, no way to read a value off it. This is a real bar chart: a labelled
// y-axis with a unit, dated x ticks, and a caption that states the range and the peak.
// One metric at a time on purpose (a33-18's lesson): requests, tokens and tok/s have
// different units and must never share an axis.
let histMetric = "requests";
const HIST_METRICS = {
  requests: { get: (d) => d.requests, unit: "req/day", label: "requests per day" },
  tokens: { get: (d) => d.total_tokens, unit: "tokens/day", label: "tokens per day" },
  // A quiet day rolls up a null mean since M81-T3; null must be an absent bar, never a
  // zero-height one that reads as "decoded nothing".
  tok_s: { get: (d) => d.tok_s_mean, unit: "tok/s", label: "mean decode speed" },
};

function renderHistBars() {
  const svg = $("hist-bars");
  if (!svg) return;
  const m = HIST_METRICS[histMetric] || HIST_METRICS.requests;
  while (svg.firstChild) svg.removeChild(svg.firstChild);

  const caption = $("hist-bars-caption");
  if (!days.length) {
    if (caption) caption.textContent = "awaiting history";
    return;
  }

  const W = 900, H = 170;
  const pad = { left: 58, right: 20, top: 16, bottom: 34 };
  const chartW = W - pad.left - pad.right;
  const chartH = H - pad.top - pad.bottom;
  const N = days.length;

  const vals = days.map(m.get);
  const known = vals.filter((v) => v != null && !Number.isNaN(v));
  const peak = known.length ? Math.max(...known) : 0;
  const axisMax = peak > 0 ? peak * 1.12 : 1;

  // y axis: 4 gridlines, labelled, unit on the top one and in the axis title.
  for (let s = 0; s <= 4; s++) {
    const frac = s / 4;
    const y = pad.top + chartH * (1 - frac);
    svg.appendChild(svgElem("line", {
      x1: pad.left, y1: y, x2: W - pad.right, y2: y, class: "chart-grid-line",
    }));
    const val = axisMax * frac;
    const txt = svgElem("text", {
      x: pad.left - 8, y: y + 4, class: "chart-axis-text", "text-anchor": "end",
    });
    let label = val >= 1e6 ? `${(val / 1e6).toFixed(1)}M`
      : val >= 1e3 ? `${(val / 1e3).toFixed(0)}k`
      : `${Math.round(val)}`;
    if (s === 4) label = `${label} ${m.unit}`;
    txt.textContent = label;
    svg.appendChild(txt);
  }
  const title = svgElem("text", {
    x: 6, y: pad.top - 4, class: "chart-axis-text chart-axis-title", "text-anchor": "start",
  });
  title.textContent = m.unit;
  svg.appendChild(title);

  // Bars. Below ~30 days a full-width bar would merge into a block, so the bar keeps a
  // gap and a minimum visible width for a non-zero value.
  const slot = chartW / N;
  const barW = Math.max(1, Math.min(slot * 0.8, 46));
  days.forEach((d, i) => {
    const v = vals[i];
    const cx = pad.left + slot * (i + 0.5);
    if (v == null || Number.isNaN(v)) return;
    const h = Math.max(v > 0 ? 1 : 0, (v / axisMax) * chartH);
    const rect = svgElem("rect", {
      x: (cx - barW / 2).toFixed(1),
      y: (pad.top + chartH - h).toFixed(1),
      width: barW.toFixed(1),
      height: h.toFixed(1),
      class: "hist-bar" + (i === scrubIdx ? " is-selected" : ""),
    });
    rect.dataset.day = String(i);
    svg.appendChild(rect);
  });

  // x ticks: at most ~6, always including the first and last recorded day.
  const stride = Math.max(1, Math.round(N / 6));
  const ticks = [];
  for (let i = 0; i < N; i += stride) ticks.push(i);
  if (ticks[ticks.length - 1] !== N - 1) ticks.push(N - 1);
  ticks.forEach((i) => {
    const cx = pad.left + slot * (i + 0.5);
    const t = svgElem("text", {
      x: cx.toFixed(1), y: H - 12, class: "chart-axis-text", "text-anchor": "middle",
    });
    // MM-DD keeps 90 days legible; the full ISO date is in the scrubber readout.
    t.textContent = (days[i].date || "").slice(5);
    svg.appendChild(t);
    svg.appendChild(svgElem("line", {
      x1: cx.toFixed(1), y1: pad.top + chartH, x2: cx.toFixed(1), y2: pad.top + chartH + 4,
      class: "chart-grid-line",
    }));
  });

  if (caption) {
    const unmeasured = N - known.length;
    caption.textContent =
      `${N} recorded day${N === 1 ? "" : "s"} · ${days[0].date} → ${days[N - 1].date} · ` +
      `peak ${fmtNum(peak, ` ${m.unit}`, peak >= 100 ? 0 : 1)}` +
      (unmeasured > 0 ? ` · ${unmeasured} day${unmeasured === 1 ? "" : "s"} with no ${m.label}` : "");
  }
}

function wireHistMetricTabs() {
  const tabs = document.querySelectorAll("#hist-metric-tabs .chart-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => {
        t.classList.remove("is-active");
        t.setAttribute("aria-selected", "false");
      });
      tab.classList.add("is-active");
      tab.setAttribute("aria-selected", "true");
      histMetric = tab.dataset.hmetric || "requests";
      renderHistBars();
    });
  });
}

// The scrubber: the marker's x-position picks a recorded day; the day's numbers
// (and its delta vs the day before) print beside it. Clicking the track jumps
// straight to a day; dragging slides it.
let scrubIdx = 0;

function selectDay(idx, force) {
  const track = $("scrub");
  const marker = $("scrub-marker");
  const sel = $("hist-selected");
  if (!track || !marker || !sel) return;
  if (!days.length) {
    marker.style.left = "0%";
    sel.textContent = "no recorded days yet — history builds as the engine runs";
    track.setAttribute("aria-valuenow", "0");
    track.removeAttribute("aria-valuetext");
    setText("hist-scrub-first", "--");
    setText("hist-scrub-last", "--");
    return;
  }
  scrubIdx = Math.max(0, Math.min(idx, days.length - 1));
  const pct = days.length === 1 ? 0 : (scrubIdx / (days.length - 1)) * 100;
  marker.style.left = `${pct}%`;
  track.setAttribute("aria-valuemax", String(days.length - 1));
  track.setAttribute("aria-valuenow", String(scrubIdx));

  const x = days[scrubIdx];
  // a33-24: an index is not a day. Screen readers (and the caption beside the track) need
  // the date itself, and the track ends must name the range it spans.
  track.setAttribute("aria-valuetext", `${x.date}, day ${scrubIdx + 1} of ${days.length}`);
  setText("hist-scrub-first", days[0].date || "--");
  setText("hist-scrub-last", days[days.length - 1].date || "--");

  // Keep the bar highlight in sync without redrawing the whole chart.
  const svg = $("hist-bars");
  if (svg) {
    svg.querySelectorAll(".hist-bar").forEach((r) => {
      r.classList.toggle("is-selected", r.dataset.day === String(scrubIdx));
    });
  }
  const prev = scrubIdx > 0 ? days[scrubIdx - 1] : null;
  const bits = [`${fmtInt(x.requests)} req`, `${fmtInt(x.total_tokens || 0)} tok`, `${fmtNum(x.tok_s_mean, " tok/s", 1)}`];
  if (x.energy_wh != null) bits.push(`${fmtNum(x.energy_wh, " Wh", 1)}`);
  if (x.hit_mean != null) bits.push(`hit ${Math.round(x.hit_mean)}%`);
  if (x.idle_pct != null) bits.push(`idle ${Math.round(x.idle_pct)}%`);
  let line = `${x.date} · ${bits.join(" · ")}`;
  if (prev && prev.requests) {
    const d = ((x.requests - prev.requests) / prev.requests) * 100;
    line += ` · ${fmtDelta(d)} req vs ${prev.date}`;
  }
  sel.textContent = line;
}

function wireScrub() {
  const track = $("scrub");
  if (!track) return;
  const pick = (e) => {
    if (!days.length) return;
    const r = track.getBoundingClientRect();
    if (!r.width) return;
    const frac = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    selectDay(Math.round(frac * (days.length - 1)), false);
  };
  let scrubbing = false;
  track.addEventListener("pointerdown", (e) => {
    scrubbing = true;
    pick(e);
  });
  track.addEventListener("pointermove", (e) => {
    if (scrubbing) pick(e);
  });
  track.addEventListener("pointerup", () => (scrubbing = false));

  // M81-T5: the element declares role="slider", which promises keyboard operation. Without
  // this, a keyboard or screen-reader user could not select a day at all.
  track.addEventListener("keydown", (e) => {
    if (!days.length) return;
    const last = days.length - 1;
    let next = null;
    if (e.key === "ArrowRight" || e.key === "ArrowUp") next = Math.min(last, scrubIdx + 1);
    else if (e.key === "ArrowLeft" || e.key === "ArrowDown") next = Math.max(0, scrubIdx - 1);
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = last;
    else if (e.key === "PageUp") next = Math.min(last, scrubIdx + 7);
    else if (e.key === "PageDown") next = Math.max(0, scrubIdx - 7);
    if (next === null) return;
    e.preventDefault();
    selectDay(next, false);
  });
}

// The panel's own hint says "click a day", and since the bars are now real elements that is
// worth honouring. Delegation on the persistent <svg> means one listener, not one per bar.
function wireHistBars() {
  const svg = $("hist-bars");
  if (!svg) return;
  svg.addEventListener("click", (e) => {
    const day = e.target && e.target.dataset ? e.target.dataset.day : undefined;
    if (day === undefined) return;
    selectDay(parseInt(day, 10), false);
  });
}

// ---------- Performance & Token Timeseries Charts ----------
let currentChartRange = "1h";
let currentChartMetric = "all";
let currentTimeseriesData = null;
let lastTimeseriesFetch = 0;
let lastStatsData = null;

function svgElem(tag, attrs = {}) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

function synthesizeFallbackTimeseries(range) {
  if (!lastStatsData) return null;
  const now = Date.now() / 1000;
  const isDay = range === "7d" || range === "30d" || range === "90d";
  const numBuckets = range === "15m" ? 30 : range === "24h" ? 48 : 60;
  const buckets = [];

  if (isDay && lastStatsData.daily && lastStatsData.daily.length) {
    const daysArr = lastStatsData.daily;
    const limit = range === "7d" ? 7 : range === "30d" ? 30 : 90;
    const slice = daysArr.slice(-limit);
    for (const d of slice) {
      buckets.push({
        t: d.d * 86400,
        time: `${d.date}T00:00:00Z`,
        label: d.date.slice(5),
        // M81-T4: the fallback path must carry the same fields the API emits, or the
        // gap-aware renderer treats every fallback bucket as unobserved and draws nothing.
        samples: d.polls || 0,
        requests: d.requests || 0,
        prompt_tokens: d.prompt_tokens || 0,
        reused: d.reused || 0,
        output_tokens: d.output_tokens || 0,
        total_tokens: d.total_tokens || 0,
        tok_s_mean: d.tok_s_mean,
        tok_s_max: d.tok_s_max,
        prefill_mean: d.prefill_mean,
        prefill_max: d.prefill_max ?? null,
      });
    }
  } else if (lastStatsData.history && lastStatsData.history.requests) {
    const reqs = lastStatsData.history.requests || [];
    const toks = lastStatsData.history.tok_s || [];
    const prefs = lastStatsData.history.prefill || [];
    const n = Math.max(reqs.length, toks.length, numBuckets);
    for (let i = 0; i < n; i++) {
      const r = reqs[i] || 0;
      const t = toks[i];
      const p = prefs[i];
      const dt = new Date((now - (n - 1 - i) * 60) * 1000);
      buckets.push({
        t: now - (n - 1 - i) * 60,
        time: dt.toISOString(),
        label: dt.toTimeString().slice(0, 5),
        // One history sample = one poll, so this bucket was observed.
        samples: 1,
        requests: r,
        prompt_tokens: r * 800,
        reused: 0,
        output_tokens: r * 150,
        total_tokens: r * 950,
        tok_s_mean: t != null ? t : null,
        tok_s_max: t != null ? t * 1.15 : null,
        prefill_mean: p != null ? p : null,
        prefill_max: p != null ? p * 1.2 : null,
      });
    }
  }
  if (!buckets.length) return null;

  const validToks = buckets.map(b => b.tok_s_mean).filter(v => v != null);
  const validPref = buckets.map(b => b.prefill_mean).filter(v => v != null);

  return {
    range,
    span_s: isDay ? buckets.length * 86400 : buckets.length * 60,
    bucket_s: isDay ? 86400 : 60,
    n_buckets: buckets.length,
    empty_buckets: buckets.filter((b) => !b.samples).length,
    buckets,
    summary: {
      total_requests: buckets.reduce((s, b) => s + b.requests, 0),
      total_tokens: buckets.reduce((s, b) => s + b.total_tokens, 0),
      prompt_tokens: buckets.reduce((s, b) => s + b.prompt_tokens, 0),
      output_tokens: buckets.reduce((s, b) => s + b.output_tokens, 0),
      reused_tokens: buckets.reduce((s, b) => s + b.reused, 0),
      tok_s_mean: validToks.length ? Math.round((validToks.reduce((s, v) => s + v, 0) / validToks.length) * 10) / 10 : null,
      tok_s_max: validToks.length ? Math.max(...validToks) : null,
      prefill_mean: validPref.length ? Math.round((validPref.reduce((s, v) => s + v, 0) / validPref.length) * 10) / 10 : null,
      prefill_max: validPref.length ? Math.max(...validPref) : null,
    },
  };
}

async function fetchTimeseries(range = currentChartRange, force = false) {
  if (!force && currentTimeseriesData && currentTimeseriesData.range === range && (Date.now() - lastTimeseriesFetch < 5000)) {
    return;
  }
  currentChartRange = range;
  try {
    const res = await fetch(`api/timeseries?range=${encodeURIComponent(range)}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    currentTimeseriesData = data;
    lastTimeseriesFetch = Date.now();
    // M81-T8 (a32-02): the fetch and its render are stamped separately because the fetch is
    // throttled — a wait on the render alone could be satisfied by the next /api/stats
    // re-render of stale data.
    window.__lastChartFetch = Date.now();
    renderTimeseriesChart(data, currentChartMetric, currentChartRange);
  } catch (err) {
    const fallback = synthesizeFallbackTimeseries(range);
    if (fallback) {
      currentTimeseriesData = fallback;
      window.__lastChartFetch = Date.now();
      renderTimeseriesChart(fallback, currentChartMetric, currentChartRange);
    }
  }
}

function fmtBucket(s) {
  // Human size of one bucket, so "60 buckets of 30 s" can be read off the strip.
  if (s >= 86400) return `${Math.round(s / 86400)} d`;
  if (s >= 3600) return `${Math.round(s / 3600)} h`;
  if (s >= 60) return `${Math.round(s / 60)} min`;
  return `${Math.round(s)} s`;
}

function renderTimeseriesChart(data, metric = currentChartMetric, range = currentChartRange) {
  if (!data || !data.buckets) return;
  const buckets = data.buckets;
  const sum = data.summary || {};

  setText("chart-sum-reqs", fmtInt(sum.total_requests));
  setText("chart-sum-tokens", fmtInt(sum.total_tokens));
  setText("chart-sum-breakdown", `${fmtInt(sum.prompt_tokens)} / ${fmtInt(sum.output_tokens)}`);
  setText("chart-sum-tok", sum.tok_s_mean != null ? `${sum.tok_s_mean.toFixed(1)} tok/s` : "--");
  setText("chart-sum-tok-hint", sum.tok_s_max != null ? `mean · peak ${sum.tok_s_max.toFixed(1)}` : "mean / peak");
  setText("chart-sum-prefill", sum.prefill_mean != null ? `${sum.prefill_mean.toFixed(0)} tok/s` : "--");
  // a33-19: "mean / peak" used to be printed whether or not a peak existed. Days rolled
  // up before the prefill_max column has none, and saying so is better than a blank.
  setText("chart-sum-prefill-hint",
    sum.prefill_max != null
      ? `mean · peak ${sum.prefill_max.toFixed(0)}${sum.prefill_bounded ? " · bounded" : ""}`
      : (sum.prefill_mean != null ? "mean · peak n/a" : "mean / peak"));
  // a33-20: every number above is scoped to this window, so the window is stated.
  setText("chart-sum-window",
    `${data.range} · ${data.n_buckets ?? buckets.length} buckets of ${fmtBucket(data.bucket_s)}`
    + (data.empty_buckets ? ` · ${data.empty_buckets} with no samples` : ""));

  const gGrid = $("chart-grid");
  const gAreas = $("chart-series-areas");
  const gLines = $("chart-series-lines");
  const gPoints = $("chart-series-points");
  if (!gGrid || !gAreas || !gLines || !gPoints) return;

  gGrid.innerHTML = "";
  gAreas.innerHTML = "";
  gLines.innerHTML = "";
  gPoints.innerHTML = "";

  const W = 900;
  const H = 300;
  const pad = { left: 55, right: 25, top: 25, bottom: 35 };
  const chartW = W - pad.left - pad.right;
  const chartH = H - pad.top - pad.bottom;
  const N = buckets.length;
  const getX = (i) => pad.left + (N > 1 ? (i / (N - 1)) * chartW : chartW / 2);
  const getY = (val, maxVal) => pad.top + chartH * (1 - Math.max(0, Math.min(1, (val || 0) / maxVal)));

  if (N === 0) {
    const emptyText = svgElem("text", {
      x: W / 2,
      y: H / 2,
      "text-anchor": "middle",
      fill: "var(--text-dim)",
      "font-size": "14",
    });
    emptyText.textContent = "No data recorded for this timeframe";
    gGrid.appendChild(emptyText);
    return;
  }

  const maxTok = Math.max(1, ...buckets.map(b => b.tok_s_max || b.tok_s_mean || 0));
  const maxPrefill = Math.max(1, ...buckets.map(b => b.prefill_max || b.prefill_mean || 0));
  const maxTokens = Math.max(1, ...buckets.map(b => b.total_tokens || 0));
  const maxReqs = Math.max(1, ...buckets.map(b => b.requests || 0));

  // M81-T4 (a33-18): one axis, several private scales was the unreadable part. The
  // left axis belongs to ONE series (the primary) and says which; every other drawn
  // series states its own peak in the legend, so no line's height is left unexplained.
  const METRIC_UNIT = { throughput: "tok/s", tokens: "tokens", requests: "req", all: "tokens" };
  const unit = METRIC_UNIT[metric] || "";
  const seriesPeak = {
    // Raw maxima for display, without the Math.max(1, …) axis floors above: a series
    // with no data must read "no data", not "scaled to peak 1".
    tok: Math.max(0, ...buckets.map(b => (b.tok_s_max ?? b.tok_s_mean) ?? 0)),
    prefill: Math.max(0, ...buckets.map(b => (b.prefill_max ?? b.prefill_mean) ?? 0)),
    tokens: Math.max(0, ...buckets.map(b => b.total_tokens || 0)),
    reqs: Math.max(0, ...buckets.map(b => b.requests || 0)),
  };

  let primaryMax = 100;
  if (metric === "throughput") {
    primaryMax = Math.max(maxTok * 1.15, 10);
  } else if (metric === "tokens") {
    primaryMax = Math.max(maxTokens * 1.15, 10);
  } else if (metric === "requests") {
    primaryMax = Math.max(maxReqs * 1.2, 5);
  } else {
    primaryMax = Math.max(maxTokens * 1.15, 100);
  }

  const gridSteps = 4;
  for (let s = 0; s <= gridSteps; s++) {
    const frac = s / gridSteps;
    const y = pad.top + chartH * (1 - frac);
    const line = svgElem("line", {
      x1: pad.left,
      y1: y,
      x2: W - pad.right,
      y2: y,
      class: "chart-grid-line",
    });
    gGrid.appendChild(line);

    const val = primaryMax * frac;
    let labelText = "";
    if (metric === "throughput") {
      labelText = `${val.toFixed(0)}`;
    } else if (metric === "requests") {
      labelText = `${Math.round(val)}`;
    } else if (metric === "tokens" || metric === "all") {
      labelText = val >= 1e6 ? `${(val / 1e6).toFixed(1)}M` : val >= 1e3 ? `${(val / 1e3).toFixed(0)}k` : `${Math.round(val)}`;
    }
    // a33-18: the top gridline carries the unit so the number can never be read as a
    // bare count. The axis title element below states it again in words.
    if (s === gridSteps && labelText) labelText = `${labelText} ${unit}`;
    const txt = svgElem("text", {
      x: pad.left - 8,
      y: y + 4,
      class: "chart-axis-text",
      "text-anchor": "end",
    });
    txt.textContent = labelText;
    gGrid.appendChild(txt);
  }

  // Axis title, so the unit is stated in words and not only as a suffix.
  const axisTitle = svgElem("text", {
    x: 6,
    y: pad.top - 10,
    class: "chart-axis-text chart-axis-title",
    "text-anchor": "start",
  });
  axisTitle.textContent = metric === "all" ? `tokens (left axis)` : unit;
  gGrid.appendChild(axisTitle);

  // M81-T4 (a33-21): a bucket with no polls is an observation gap, not a quiet engine.
  const gaps = buckets.filter((b) => !b.samples).length;
  if (gaps) {
    buckets.forEach((b, i) => {
      if (b.samples) return;
      const x = getX(i);
      gGrid.appendChild(svgElem("line", {
        x1: x, y1: pad.top, x2: x, y2: pad.top + chartH,
        class: "chart-gap-line",
      }));
    });
    const gapNote = svgElem("text", {
      x: W - pad.right,
      y: H - 22,
      class: "chart-axis-text chart-gap-note",
      "text-anchor": "end",
    });
    gapNote.textContent = `${gaps} bucket${gaps > 1 ? "s" : ""} had no samples`;
    gGrid.appendChild(gapNote);
  }

  // M81-T4 (a33-20): a fixed stride of floor(N/6) gave every range a different label
  // density and never dated the right edge. Derive the stride for ~6 labels and always
  // include the last bucket.
  const xStep = Math.max(1, Math.round(N / 6));
  const xIdx = [];
  for (let i = 0; i < N; i += xStep) xIdx.push(i);
  if (xIdx[xIdx.length - 1] !== N - 1 && N - 1 - xIdx[xIdx.length - 1] >= xStep * 0.5) xIdx.push(N - 1);
  xIdx.forEach((i) => {
    const b = buckets[i];
    const x = getX(i);
    const txt = svgElem("text", {
      x: x,
      y: H - 10,
      class: "chart-axis-text",
      "text-anchor": "middle",
    });
    txt.textContent = b.label;
    gGrid.appendChild(txt);
  });

  // M81-T4 (a33-21): a polyline that dips to 0 over an unobserved bucket reads as
  // "the engine was idle" when the truth is "no tab was open". Each series is drawn
  // as one polyline per contiguous run of observed buckets, and its area closes only
  // within a run.
  const drawSeries = (values, maxVal, { stroke, width, dash, areaFill }) => {
    let run = [];
    const flush = () => {
      if (run.length === 1) {
        // A lone observed bucket still deserves a mark rather than vanishing.
        gPoints.appendChild(svgElem("circle", {
          cx: run[0].x, cy: run[0].y, r: "2.5", fill: stroke,
        }));
      } else if (run.length > 1) {
        const pts = run.map((p) => `${p.x},${p.y}`).join(" ");
        if (areaFill) {
          const first = run[0], last = run[run.length - 1];
          gAreas.appendChild(svgElem("path", {
            d: `M ${first.x},${(pad.top + chartH).toFixed(1)} L ${pts} L ${last.x},${(pad.top + chartH).toFixed(1)} Z`,
            fill: areaFill,
          }));
        }
        const attrs = { points: pts, fill: "none", stroke, "stroke-width": width, "stroke-linejoin": "round" };
        if (dash) attrs["stroke-dasharray"] = dash;
        gLines.appendChild(svgElem("polyline", attrs));
      }
      run = [];
    };
    values.forEach((v, i) => {
      if (v == null) { flush(); return; }
      run.push({ x: getX(i).toFixed(1), y: getY(v, maxVal).toFixed(1) });
    });
    flush();
  };

  // Observed means unobserved buckets are holes: no samples at all, or a null rate for
  // a bucket that was sampled (a quiet day rolls up null since M81-T3).
  const observed = (b) => Boolean(b.samples);

  if (metric === "all" || metric === "tokens") {
    drawSeries(buckets.map((b) => (observed(b) ? b.total_tokens || 0 : null)), primaryMax,
               { stroke: "#bc8cff", width: "2", areaFill: "url(#chart-grad-tokens)" });
  }

  if (metric === "all" || metric === "requests") {
    const rMax = metric === "requests" ? primaryMax : Math.max(maxReqs, 1);
    drawSeries(buckets.map((b) => (observed(b) ? b.requests || 0 : null)), rMax,
               { stroke: "#d29922", width: metric === "requests" ? "2.2" : "1.8",
                 dash: metric === "all" ? "4,3" : null,
                 areaFill: metric === "requests" ? "url(#chart-grad-reqs)" : null });
  }

  if (metric === "all" || metric === "throughput") {
    const tMax = metric === "throughput" ? primaryMax : Math.max(maxTok, 1);
    drawSeries(buckets.map((b) => (observed(b) ? b.tok_s_mean : null)), tMax,
               { stroke: "#58a6ff", width: "2.2",
                 areaFill: metric === "throughput" ? "url(#chart-grad-tok)" : null });

    const pMax = metric === "throughput" ? Math.max(maxPrefill * 1.15, 100) : Math.max(maxPrefill, 1);
    drawSeries(buckets.map((b) => (observed(b) ? b.prefill_mean : null)), pMax,
               { stroke: "#3fb950", width: "1.8" });
  }

  // M81-T4 (a33-18/a33-22): the legend is the disclosure for every series that does NOT
  // own the left axis, so each drawn series states its own peak; items for series that
  // are not in this metric mode are hidden instead of implying an absent line.
  const legend = [
    { sel: ".legend-tok", on: metric === "all" || metric === "throughput", peak: seriesPeak.tok, unit: "tok/s" },
    { sel: ".legend-prefill", on: metric === "all" || metric === "throughput", peak: seriesPeak.prefill, unit: "tok/s" },
    { sel: ".legend-tokens", on: metric === "all" || metric === "tokens", peak: seriesPeak.tokens, unit: "" },
    { sel: ".legend-reqs", on: metric === "all" || metric === "requests", peak: seriesPeak.reqs, unit: "" },
  ];
  legend.forEach((item) => {
    const el = document.querySelector(`#chart-legend ${item.sel}`);
    if (!el) return;
    el.hidden = !item.on;
    const peakEl = el.querySelector(".legend-peak");
    if (!peakEl) return;
    if (!item.on) { peakEl.textContent = ""; return; }
    // A series scaled by the left axis needs no extra disclosure; the others do.
    const ownsAxis = (metric === "throughput" && item.sel === ".legend-tok")
      || (metric === "tokens" && item.sel === ".legend-tokens")
      || (metric === "requests" && item.sel === ".legend-reqs")
      || (metric === "all" && item.sel === ".legend-tokens");
    if (ownsAxis) { peakEl.textContent = "· left axis"; return; }
    const p = item.peak > 0 ? (item.unit === "tok/s" ? item.peak.toFixed(1) : fmtInt(item.peak)) : null;
    peakEl.textContent = p != null ? `· scaled to peak ${p}${item.unit ? " " + item.unit : ""}` : "· no data";
  });
  // M81-T8 (a32-02): stamped at the very end of the pass, so the UI suite can wait for a chart
  // render newer than its own click instead of sleeping a guessed interval.
  window.__lastChartRender = Date.now();
}

function wireCharts() {
  const rangeBtns = document.querySelectorAll("#chart-range-btns .chart-range-btn");
  rangeBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      rangeBtns.forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      const r = btn.dataset.range;
      currentChartRange = r;
      fetchTimeseries(r, true);
    });
  });

  const metricTabs = document.querySelectorAll("#chart-metric-tabs .chart-tab");
  metricTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      metricTabs.forEach((t) => {
        t.classList.remove("is-active");
        t.setAttribute("aria-selected", "false");
      });
      tab.classList.add("is-active");
      tab.setAttribute("aria-selected", "true");
      currentChartMetric = tab.dataset.metric;
      renderTimeseriesChart(currentTimeseriesData, currentChartMetric, currentChartRange);
    });
  });

  const wrap = $("chart-canvas-wrap");
  const svg = $("chart-svg");
  const crosshair = $("chart-crosshair");
  const tooltip = $("chart-tooltip");

  if (!wrap || !svg || !crosshair || !tooltip) return;

  const onPointerMove = (e) => {
    if (!currentTimeseriesData || !currentTimeseriesData.buckets || !currentTimeseriesData.buckets.length) return;
    const rect = svg.getBoundingClientRect();
    if (!rect.width) return;
    const clientX = e.clientX || (e.touches && e.touches[0] && e.touches[0].clientX);
    if (clientX == null) return;

    const padLeft = 55;
    const padRight = 25;
    const W = 900;
    const chartW = W - padLeft - padRight;
    const relX = (clientX - rect.left) / rect.width;
    const svgX = relX * W;

    const clampedSvgX = Math.max(padLeft, Math.min(W - padRight, svgX));
    const frac = (clampedSvgX - padLeft) / chartW;
    const N = currentTimeseriesData.buckets.length;
    const idx = Math.max(0, Math.min(N - 1, Math.round(frac * (N - 1))));
    const b = currentTimeseriesData.buckets[idx];
    if (!b) return;

    const bucketX = padLeft + (N > 1 ? (idx / (N - 1)) * chartW : chartW / 2);
    crosshair.setAttribute("x1", bucketX.toFixed(1));
    crosshair.setAttribute("x2", bucketX.toFixed(1));
    crosshair.style.display = "";

    const tokStr = b.tok_s_mean != null ? `${b.tok_s_mean.toFixed(1)} tok/s` : "--";
    const prefStr = b.prefill_mean != null ? `${b.prefill_mean.toFixed(0)} tok/s` : "--";
    // a33-21: hovering an unobserved bucket must not present zeros as measurements.
    if (!b.samples) {
      tooltip.innerHTML = `
        <div class="chart-tip__head">${b.time ? b.time.replace("T", " ").replace("Z", "") : b.label} (${b.label})</div>
        <div class="chart-tip__row">No samples in this bucket — nothing was recorded, which is not the same as idle.</div>
      `;
    } else {
      tooltip.innerHTML = `
      <div class="chart-tip__head">${b.time ? b.time.replace("T", " ").replace("Z", "") : b.label} (${b.label})</div>
      <div class="chart-tip__row"><span class="chart-tip__dot" style="background:#58a6ff;"></span>Decode: <b>${tokStr}</b></div>
      <div class="chart-tip__row"><span class="chart-tip__dot" style="background:#3fb950;"></span>Prefill: <b>${prefStr}</b></div>
      <div class="chart-tip__row"><span class="chart-tip__dot" style="background:#bc8cff;"></span>Tokens: <b>${fmtInt(b.total_tokens)}</b> (${fmtInt(b.prompt_tokens)} in / ${fmtInt(b.output_tokens)} out)</div>
      <div class="chart-tip__row"><span class="chart-tip__dot" style="background:#d29922;"></span>Requests: <b>${fmtInt(b.requests)}</b></div>
      ${b.prefill_note ? `<div class="chart-tip__row chart-tip__sub">Prefill not shown: this day was recorded before readings were bounded, and its samples are no longer kept, so its figure cannot be recomputed.</div>` : ""}
      <div class="chart-tip__row chart-tip__sub">${b.samples} sample${b.samples === 1 ? "" : "s"}</div>
    `;
    }

    const wrapRect = wrap.getBoundingClientRect();
    const px = (bucketX / W) * wrapRect.width;
    const isRightHalf = px > wrapRect.width * 0.55;

    tooltip.style.left = `${px}px`;
    tooltip.style.top = "30%";
    tooltip.style.transform = isRightHalf ? "translate(-105%, -30%)" : "translate(15px, -30%)";
    tooltip.style.display = "block";
  };

  wrap.addEventListener("mousemove", onPointerMove);
  wrap.addEventListener("touchmove", onPointerMove, { passive: true });

  const onPointerLeave = () => {
    crosshair.style.display = "none";
    tooltip.style.display = "none";
  };
  wrap.addEventListener("mouseleave", onPointerLeave);
  wrap.addEventListener("touchend", onPointerLeave);
}

// ---------- Layout save/reset buttons ----------
function wireLayoutButtons() {
  const save = $("layout-save");
  if (save) save.addEventListener("click", () => persistOrder());
  const reset = $("layout-reset");
  if (reset) {
    reset.addEventListener("click", () => {
      localStorage.removeItem(ORDER_KEY);
      applyOrder(DEFAULT_ORDER);
      const note = $("layout-note");
      if (note) note.hidden = true; // Reset is the fix the note points at; stop repeating it.
    });
  }
  const close = $("layout-note-close");
  if (close) close.addEventListener("click", () => ($("layout-note").hidden = true));
}

async function refresh() {
  let data;
  try {
    data = await fetchStats();
    // M81-T7: the age of the numbers on screen is measured from when a poll last
    // succeeded, not from when the page loaded.
    lastPollOkAtMs = Date.now();
    setBadge(false);
  } catch (err) {
    // No backend reachable — keep the last rendered state and flag the badge so
    // the user knows the numbers are not live.
    console.warn("stats endpoint unavailable", err);
    setBadge(true);
    layoutAll(); // audit-31 P-05: spans must stay correct even on the failure path
    return;
  }

  // Stash the bucketed-series window before rendering so drawSpark labels the requests
  // x-axis with the real interval rather than the per-poll default (r3-01).
  if (data.history_bucket_s) historyBucketMs = data.history_bucket_s * 1000;

  renderEngine(data.engine, data.config);
  renderLive(data.live, data.status);
  renderContext(data.context);
  renderThroughput(data.throughput, data.history, data.analysis, data.totals);
  renderPower(data.power, data.history);
  renderGpu(data.gpu, data.history, data.power);
  renderHardware(data.hardware);
  renderCache(data.cache);
  renderSpec(data.spec);
  renderRequests(data.requests, data.requests_kept);
  renderAnalysis(data.analysis, data.telemetry, data.totals);
  renderSwitch(data.switch);
  renderLog(data.log);
  renderEndpoints(data.endpoints);
  renderHero(data.throughput, data.power, data.context, data.cache, data.status);
  renderTopbar(data.engine, data.throughput, data.history);
  renderLiveness(data.totals);
  renderHistory(data.periods, data.daily, data.requests);
  renderHud(data);

  lastStatsData = data;
  // M81-T8 (a32-02): marks the poll whose values are now on screen. The suite waits for this
  // instead of sleeping, which is also what lets a check prove a seeded DB row or a pinned
  // fixture actually reached the DOM. Stamped before layoutAll so a masonry pass always
  // post-dates the content it is spanning.
  window.__lastRender = Date.now();
  layoutAll(); // M80-T1: re-span after every render pass
  if (Date.now() - lastTimeseriesFetch > 15000 && (currentChartRange === "15m" || currentChartRange === "1h")) {
    fetchTimeseries(currentChartRange);
  }
}

// ---------- Tab & View switching ----------
let currentView = "full";

function switchView(viewName) {
  const isCompact = viewName === "compact";
  currentView = isCompact ? "compact" : "full";

  const tabFull = $("tab-full");
  const tabCompact = $("tab-compact");
  const viewFull = $("view-full");
  const viewCompact = $("view-compact");

  if (tabFull) {
    tabFull.classList.toggle("is-active", !isCompact);
    tabFull.setAttribute("aria-selected", !isCompact ? "true" : "false");
  }
  if (tabCompact) {
    tabCompact.classList.toggle("is-active", isCompact);
    tabCompact.setAttribute("aria-selected", isCompact ? "true" : "false");
  }
  if (viewFull) {
    viewFull.classList.toggle("is-active", !isCompact);
    viewFull.hidden = isCompact;
  }
  if (viewCompact) {
    viewCompact.classList.toggle("is-active", isCompact);
    viewCompact.hidden = !isCompact;
  }

  document.body.setAttribute("data-view", currentView);
  try {
    localStorage.setItem("llm-monitor-view", currentView);
  } catch (_) {}
  // audit-32 F-32-05: hiding #view-full zeroes every tile's height. The ResizeObserver does
  // heal this, but the spans should not depend on observer timing, so re-run the pass here.
  queueLayout();
}

function wireTabs() {
  const tabFull = $("tab-full");
  const tabCompact = $("tab-compact");
  const btnPopout = $("btn-popout");

  if (tabFull) tabFull.addEventListener("click", () => switchView("full"));
  if (tabCompact) tabCompact.addEventListener("click", () => switchView("compact"));
  if (btnPopout) {
    btnPopout.addEventListener("click", () => {
      window.open(location.pathname + "?view=compact", "LLMMonitorHUD", "width=480,height=820,resizable=yes,scrollbars=yes");
    });
  }

  document.querySelectorAll(".view-tab").forEach((tab) => {
    tab.addEventListener("keydown", (e) => {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        const next = tab.id === "tab-full" ? "compact" : "full";
        switchView(next);
        $(next === "compact" ? "tab-compact" : "tab-full")?.focus();
      }
    });
  });

  const params = new URLSearchParams(location.search);
  const initialView = params.get("view") || (function() {
    try { return localStorage.getItem("llm-monitor-view"); } catch (_) { return null; }
  })() || "full";
  switchView(initialView);
}

// ---------- Compact HUD View ----------
function renderHud(data) {
  if (!data) return;

  // Identity & state
  const engine = data.engine || {};
  setText("hud-engine", engine.service || engine.active ? (engine.service === "strata" ? "Strata Coder" : engine.service === "vulkan" ? "Vulkan llama.cpp" : engine.service) : "--");
  setText("hud-model", engine.model || "--");

  const orb = $("hud-status-orb");
  const mark = $("hud-mark");
  const stateVal = (data.status && data.status.state) || "idle";
  const stateLabel = stateName(stateVal);
  setText("hud-state", stateLabel);
  setText("hud-sub-state", stateLabel);

  if (orb) {
    orb.className = "hud-status-orb";
    if (stateVal === "generating" || stateVal === "processing") orb.classList.add("is-generating");
    else if (stateVal === "reading") orb.classList.add("is-reading");
    else if (data.status && data.status.ok === false) orb.classList.add("is-down");
    else orb.classList.add("is-idle");
  }

  if (mark) {
    const svc = engine.service || engine.active || "";
    mark.innerHTML = brandMark(svc, engine.port_open);
    mark.className = "brand__mark";
    if (!engine.port_open) mark.classList.add("down");
    else if (svc === "strata") mark.classList.add("strata");
    else if (svc === "vulkan") mark.classList.add("vulkan");
  }

  // Hero Speed
  const thr = data.throughput;
  setText("hud-tok", thr && thr.now != null ? thr.now.toFixed(1) : "0.0");
  const meanSpeed = thr && thr.mean != null ? `${thr.mean.toFixed(1)} tok/s` : "--";
  const an = data.analysis && data.analysis.recent;
  const peakSpeed = an && an.tok_s_max != null ? `${an.tok_s_max.toFixed(1)} tok/s` : (thr && thr.now != null ? `${thr.now.toFixed(1)} tok/s` : "--");
  setText("hud-tok-sub", `peak ${peakSpeed} · mean ${meanSpeed}`);
  setText("hud-prefill", thr && thr.prefill != null ? thr.prefill.toFixed(0) : "--");
  let hudPreMean = thr && (thr.prefill_mean ?? thr.recent_prefill_mean);
  if (hudPreMean == null && an && an.prefill_mean != null) hudPreMean = an.prefill_mean;
  if (hudPreMean == null && data.totals && data.totals.prompt_tokens && data.totals.prompt_ms && data.totals.prompt_ms > 0) {
    hudPreMean = Math.max(0, data.totals.prompt_tokens - (data.totals.reused || 0)) / (data.totals.prompt_ms / 1000);
  }
  setText("hud-prefill-sub", hudPreMean != null ? `avg ${hudPreMean.toFixed(0)}` : "avg --");

  // VRAM Card
  const gpu = data.gpu || {};
  // M81-T2 (a33-04): report the source the server sent; inventing one hides the difference
  // between "derived from vram_free_mib" and "we have no idea".
  setText("hud-vram-source", gpu.mem_source || "none");
  setText("hud-vram-val", gpu.mem_pct != null ? `${gpu.mem_pct.toFixed(0)}%` : "--");
  setMeter("hud-vram-gauge", gpu.mem_pct);
  const vramVal = $("hud-vram-val");
  if (vramVal && gpu.mem_pct != null) {
    vramVal.classList.remove("is-ok", "is-warn", "is-bad");
    vramVal.classList.add(`is-${severity(gpu.mem_pct, false)}`);
  }
  // A derived figure is in MiB (the engine reports vram_free_mib); a driver counter would be
  // bytes. Shares the GPU panel's rule so the two views can never disagree (audit-33 a33-05).
  const vramScaleFactor = vramScale(gpu);
  setText("hud-vram-hint", gpu.mem_used != null && gpu.mem_total != null
    ? `${fmtBytes(gpu.mem_used * vramScaleFactor)} / ${fmtBytes(gpu.mem_total * vramScaleFactor)}`
    : (data.hardware && data.hardware.vram_free_mib != null ? `${data.hardware.vram_free_mib} MiB free` : "used / total"));

  // Power Card
  const pw = data.power || {};
  setText("hud-power-source", pw.source || "none");
  setText("hud-power-val", pw.total_w != null ? `${pw.total_w} W` : "--");
  // rated_w is the server's alias of peak_w; before M81-T2 it did not exist, so this gauge was
  // permanently zero. Guard with != null: a genuine 0 W reading must still size the gauge.
  const pwPct = pw.total_w != null && pw.rated_w ? (pw.total_w / pw.rated_w) * 100 : null;
  setMeter("hud-power-gauge", pwPct);
  const pwVal = $("hud-power-val");
  if (pwVal && pwPct != null) {
    pwVal.classList.remove("is-ok", "is-warn", "is-bad");
    pwVal.classList.add(`is-${severity(pwPct, false)}`);
  }
  setText("hud-power-hint", pwPct != null ? `${pwPct.toFixed(0)}% of ${pw.rated_w}W peak` : "of rated peak");

  // Context Card
  const ctx = data.context || {};
  // M81-T2 (audit-33 a33-36): context.pct is already a percentage (server.py multiplies by 100),
  // so multiplying again rendered 7417.0% where the real figure was 74.2%. The full dashboard
  // passes ctx.pct straight to setGauge; the HUD now matches it.
  setText("hud-ctx-pct", ctx.pct != null ? `${ctx.pct.toFixed(1)}%` : "--");
  // used/max are the payload's keys; used_tokens/max_tokens never existed, so this row was always "--".
  setText("hud-ctx-val", ctx.used != null ? fmtInt(ctx.used) : "--");
  setMeter("hud-ctx-gauge", ctx.pct);
  const ctxVal = $("hud-ctx-val");
  if (ctxVal && ctx.pct != null) {
    ctxVal.classList.remove("is-ok", "is-warn", "is-bad");
    ctxVal.classList.add(`is-${severity(ctx.pct, false)}`);
  }
  setText("hud-ctx-hint", ctx.used != null && ctx.max != null ? `${fmtInt(ctx.used)} / ${fmtInt(ctx.max)} max` : "used / max tokens");

  // Cache & Spec Card
  const cache = data.cache || {};
  setText("hud-cache-hit", cache.hit_rate != null ? `${(cache.hit_rate * 100).toFixed(0)}% hit` : "--");
  const firstReq = (data.requests || [])[0];
  setText("hud-reuse-val", cache.reused_tokens != null ? fmtInt(cache.reused_tokens) : (firstReq?.reused != null ? fmtInt(firstReq.reused) : "--"));
  const spec = data.spec || {};
  const draftPct = spec.accept_rate != null
    ? (spec.accept_rate * 100).toFixed(0)
    : (firstReq?.drafts_offered ? ((firstReq.drafts_accepted ?? 0) / firstReq.drafts_offered * 100).toFixed(0) : null);
  setText("hud-draft-val", draftPct != null ? `${draftPct}%` : "--");
  setText("hud-cache-hint", cache.kv_type ? `KV: ${cache.kv_type}` : "prompt-token reuse");

  // Last Request Spotlight
  const reqs = data.requests || [];
  const r0 = reqs[0];
  const r1 = reqs.length >= 2 ? reqs[1] : null;
  if (r0) {
    const t0 = r0.total_tokens ?? ((r0.prompt_tokens ?? 0) + (r0.output_tokens ?? 0));
    setText("hud-req-total", t0 != null ? fmtInt(t0) : "--");
    setText("hud-req-prompt", r0.prompt_tokens != null ? fmtInt(r0.prompt_tokens) : "--");
    setText("hud-req-out", r0.output_tokens != null ? fmtInt(r0.output_tokens) : "--");
    setText("hud-req-dur", r0.duration_s != null ? `${r0.duration_s.toFixed(1)}s` : "--");
    setText("hud-req-speed", r0.decode_tok_s != null ? `${r0.decode_tok_s.toFixed(1)} tok/s` : "--");

    if (r1) {
      const t1 = r1.total_tokens ?? ((r1.prompt_tokens ?? 0) + (r1.output_tokens ?? 0));
      if (t0 != null && t1 != null && t1 > 0) {
        const diff = t0 - t1;
        const pct = (diff / t1) * 100;
        const sign = diff >= 0 ? "+" : "";
        setText("hud-req-delta", `${sign}${fmtDelta(pct)} vs prev`);
        const deltaEl = $("hud-req-delta");
        if (deltaEl) {
          deltaEl.className = "hud-spotlight__delta " + (pct > 0 ? "is-warn" : pct < 0 ? "is-ok" : "");
        }
      } else {
        setText("hud-req-delta", "--");
      }
    } else {
      setText("hud-req-delta", "first req");
    }
  } else {
    ["hud-req-total", "hud-req-prompt", "hud-req-out", "hud-req-dur", "hud-req-speed", "hud-req-delta"].forEach((id) => setText(id, "--"));
  }

  // Micro Performance Trends
  const periods = data.periods;
  const curH = periods?.hour?.current;
  const prevH = periods?.hour?.previous;
  setText("hud-trend-hour", curH ? `${fmtInt(curH.total_tokens)} tok · ${curH.requests ?? 0} req` : "--");
  if (curH && prevH && curH.total_tokens != null && prevH.total_tokens != null) {
    if (prevH.total_tokens === 0) {
      // M81-T3 (a33-16): same rule as the History table — a percentage out of an
      // empty prior period is not a number. State the absolute movement instead.
      const txt = curH.total_tokens > 0 ? `new (+${fmtInt(curH.total_tokens)})` : "±0%";
      setText("hud-delta-hour", txt);
      const elH = $("hud-delta-hour");
      if (elH) elH.className = "hud-trend-delta " + (curH.total_tokens > 0 ? "is-warn" : "");
    } else {
      const dH = ((curH.total_tokens - prevH.total_tokens) / prevH.total_tokens) * 100;
      setText("hud-delta-hour", fmtDelta(dH));
      const elH = $("hud-delta-hour");
      if (elH) elH.className = "hud-trend-delta " + (dH > 0 ? "is-warn" : dH < 0 ? "is-ok" : "");
    }
  } else {
    setText("hud-delta-hour", "--");
  }

  const curD = periods?.day?.current;
  const prevD = periods?.day?.previous;
  setText("hud-trend-today", curD ? `${fmtInt(curD.total_tokens)} tok · ${curD.requests ?? 0} req` : "--");
  if (curD && prevD && curD.total_tokens != null && prevD.total_tokens != null) {
    if (prevD.total_tokens === 0) {
      // M81-T3 (a33-16): see the hour row above.
      const txt = curD.total_tokens > 0 ? `new (+${fmtInt(curD.total_tokens)})` : "±0%";
      setText("hud-delta-today", txt);
      const elD = $("hud-delta-today");
      if (elD) elD.className = "hud-trend-delta " + (curD.total_tokens > 0 ? "is-warn" : "");
    } else {
      const dD = ((curD.total_tokens - prevD.total_tokens) / prevD.total_tokens) * 100;
      setText("hud-delta-today", fmtDelta(dD));
      const elD = $("hud-delta-today");
      if (elD) elD.className = "hud-trend-delta " + (dD > 0 ? "is-warn" : dD < 0 ? "is-ok" : "");
    }
  } else {
    setText("hud-delta-today", "--");
  }

  // Micro Sparkline
  drawSpark("hud", data.history && data.history.tok_s, "decode tok/s", REFRESH_MS);

  // Endpoints dots
  const ep = data.endpoints || {};
  ["health", "metrics", "slots", "models", "status"].forEach((k) => {
    const el = $(`hud-dot-${k}`);
    if (el) {
      el.classList.toggle("is-up", Boolean(ep[k]));
      el.classList.toggle("is-down", !ep[k]);
    }
  });
}

async function wireDragDrop() {
  container = document.querySelector(".tiles");
  if (!container) return;
  slotEl = document.createElement("div");
  slotEl.className = "drop-slot";
  slotEl.id = "drop-slot";
  // Detached until a drag places it, so it never renders or takes a11y order.
  wireContainer(container);
  // M79-T4: the Detail region is a second tiles container; panels may move between
  // them, so both are wired and persistOrder records both lists under one key.
  detailContainer = document.querySelector(".tiles--detail");
  if (detailContainer) wireContainer(detailContainer);
  // M80-T1: any child that changes size (poll updates, log lines, details open,
  // until-found reveal — audit-31 P-03) re-runs the masonry pass. Observing the
  // children, not the containers, is what catches a <details> growing inside.
  if (typeof ResizeObserver === "function") {
    const ro = new ResizeObserver(queueLayout);
    for (const c of containersList()) {
      for (const el of c.children) ro.observe(el);
    }
  }
  window.addEventListener("resize", queueLayout);
}

// M78 usage ledger: today and the last 7 days, every 60 s. A missing source says "unavailable", never 0 (honest labels).
const fmtTok = (n) => (n == null ? "unavailable" : n >= 1e6 ? `${(n / 1e6).toFixed(2)} M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)} k` : String(Math.round(n)));
async function fetchUsage() {
  const now = new Date();
  const iso = (d) => d.toISOString().replace(/\.\d{3}Z$/, "Z");
  const day = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const week = new Date(now.getTime() - 7 * 86400000);
  try {
    for (const [key, from] of [["day", day], ["week", week]]) {
      const r = await fetch(`/api/usage?from=${iso(from)}&to=${iso(now)}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const u = await r.json();
      $(`usage-${key}-orch`).textContent = u.weighted.orchestrator == null ? "unavailable" : `${fmtTok(u.weighted.orchestrator)} weighted`;
      $(`usage-${key}-exec`).textContent = u.executor ? `${fmtTok(u.executor.input + u.executor.output)} tokens` : "unavailable";
      $("usage-sources").textContent = `Claude Code ${u.sources.claude_code}, Hermes ${u.sources.hermes}${u.partial ? " (catching up)" : ""}`;
    }
  } catch (err) {
    console.error(err);
    $("usage-sources").textContent = `unavailable (${err.message})`;
  }
  // M81-T8 (a32-02): the ledger text is longer than the "--" it replaces, so the panel grows.
  // switchView re-spans for the same reason — a tile's span must not depend on when the
  // ResizeObserver happens to fire, or the row underneath it is measured against a stale span.
  // The stamp lets the UI suite require that a layout pass happened AFTER the ledger landed.
  window.__lastUsage = Date.now();
  queueLayout();
}

async function init() {
  // The countdown ring on the badge sweeps once per poll, so it has to know the
  // interval that JS actually uses.
  document.documentElement.style.setProperty("--poll-ms", `${REFRESH_MS}ms`);
  wireTabs();
  wireDragDrop(); // collects the containers before any order is applied
  restoreOrder();
  wireScrub();
  wireHistMetricTabs();
  wireHistBars();
  wireLayoutButtons();
  wireCharts();
  tickClock();
  wireLogReveal();
  wireDetail();
  await refresh();
  fetchTimeseries("1h");
  fetchUsage();
  setInterval(tickClock, 1000);
  setInterval(refresh, REFRESH_MS);
  setInterval(fetchUsage, 60000);
}

init().catch(console.error);
