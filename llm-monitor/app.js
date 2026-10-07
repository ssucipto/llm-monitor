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
function setGauge(valueId, gaugeId, pct, higherBetter) {
  const value = $(valueId);
  const gauge = $(gaugeId);
  if (!value) return;

  const shown = pct === null || pct === undefined ? 0 : pct;
  tweenNumber(value, shown, "%", 0);
  if (gauge) gauge.setAttribute("value", shown.toFixed(0));

  if (pct !== null && pct !== undefined) {
    value.classList.remove("is-ok", "is-warn", "is-bad");
    value.classList.add(`is-${severity(pct, higherBetter)}`);
  }
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
function renderThroughput(throughput, history) {
  const now = $("thr-now");
  if (now) {
    const t = throughput && throughput.now;
    now.textContent = t != null ? `${t.toFixed(1)} tok/s` : "idle";
    now.classList.remove("is-ok", "is-warn", "is-bad");
  }
  const mean = throughput && throughput.mean;
  setText("thr-mean", mean != null ? `${mean.toFixed(1)} tok/s` : "--");
  const pre = throughput && throughput.prefill;
  setText("thr-prefill", pre != null ? `${pre.toFixed(0)} tok/s` : "--");
  // The prefill reading is derived (the engine's own field is broken), so say where it
  // came from rather than implying it is the engine's measurement.
  const psrc = throughput && throughput.prefill_source === "last" ? "last request"
    : throughput && throughput.prefill_source === "live" ? "live"
    : throughput && throughput.prefill_source === "engine" ? "engine" : "";
  const src = throughput && throughput.source === "last" ? "last request" : throughput && throughput.source === "live" ? "live" : "";
  setText("thr-source", src || "--");
  setText("thr-prefill-source", psrc || "--");
  drawSpark("thr", history && history.tok_s, "tokens/s", "tokens/s, recent history");
  drawSpark("req", history && history.requests, "requests", "requests per interval — a flat stretch is an idle engine");
}

// A sparkline drawn into any <prefix>-* group. The engine keeps no request-count or
// prefill history, so those series are derived server-side; a flat stretch is the
// whole point of the request chart — it means the engine sat idle.
function drawSpark(prefix, samples, unit, fallbackCaption) {
  const line = $(`${prefix}-spark`);
  const area = $(`${prefix}-area`);
  const head = $(`${prefix}-head`);
  const halo = $(`${prefix}-halo`);
  const caption = $(`${prefix}-caption`);
  if (!line) return;

  const vals = (samples || []).filter((v) => v !== null && v !== undefined).slice(-SPARK_SAMPLES);
  if (vals.length < 2) {
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
    caption.textContent = `${unit}, last ${vals.length} samples (peak ${max.toFixed(0)} · min ${min.toFixed(0)})`;
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
  drawSpark("pw", history && history.power_w, "watts", "watts, recent history");
}

// ---------- GPU ----------
// Parity with the engine's own monitor, which draws gpu/gpu_mem/temp/power/pcie
// cards. On builds whose driver exposes no userspace counter (AMD HIP) every
// reading is null, so the panel states that in words instead of gauges at zero.
function renderGpu(gpu, history) {
  if (!gpu) return;
  const gpuCaption = $("gpu-caption");
  const state = $("gpu-state");
  if (state) {
    const has = gpu.util_pct != null || gpu.temp_c != null || gpu.mem_used != null || gpu.power_w != null;
    state.textContent = has ? "counters live" : gpu.name ? "no counters on this driver" : "no gpu readings";
    state.classList.remove("measured");
    if (has) state.classList.add("measured");
  }
  setGauge("gpu-util", "gpu-util-gauge", gpu.util_pct, false);
  setGauge("gpu-mem", "gpu-mem-gauge", gpu.mem_pct, false);
  setText("gpu-mem-hint", gpu.mem_used && gpu.mem_total ? `${fmtBytes(gpu.mem_used)} / ${fmtBytes(gpu.mem_total)}` : "used / total");
  // Temperature is a fraction of a 100 °C ceiling, so the gauge reads severity.
  setGauge("gpu-temp", "gpu-temp-gauge", gpu.temp_c != null ? Math.min(100, gpu.temp_c) : null, false);
  setText("gpu-power", gpu.power_w != null ? `${gpu.power_w} W${gpu.power_limit_w ? ` / ${gpu.power_limit_w} limit` : ""}` : "--");
  setText("gpu-pcie", gpu.pcie_rx_mb != null ? `${gpu.pcie_rx_mb.toFixed(1)} MB${gpu.pcie_gen ? ` · gen ${gpu.pcie_gen}/${gpu.pcie_gen_max ?? gpu.pcie_gen} · ${gpu.pcie_width ?? "--"}G` : ""}` : "--");
  setText("gpu-name", gpu.name ? `${gpu.name} ×${gpu.count ?? 1}` : (gpu.count ? `${gpu.count} GPU(s)` : "--"));
  if (history && gpu.history_available) {
    drawSpark("gpu", history.gpu_util, "% gpu util", "gpu utilisation, recent history");
  } else if (gpuCaption) {
    // No gpu_* series exists on this driver, so the figure would stay an empty box.
    // Say why in the caption instead of leaving a blank chart to be read as "zero".
    gpuCaption.textContent = gpu.history_available
      ? "gpu utilisation, awaiting samples"
      : gpu.name
        ? `gpu utilisation — no counters on ${gpu.name}`
        : "gpu utilisation — no counters on this driver";
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
  setText("an-prefill", recent.prefill_mean != null ? `${recent.prefill_mean.toFixed(0)} tok/s` : "--");
  setText("an-hit", recent.hit_pct_mean != null ? `${recent.hit_pct_mean.toFixed(0)}%` : "--");
  setText("an-accept", recent.accept_pct_mean != null ? `${recent.accept_pct_mean.toFixed(0)}%` : "--");
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
  setText("hw-ram-hint", hw.ram_used && hw.ram_total ? `${fmtBytes(hw.ram_used)} / ${fmtBytes(hw.ram_total)}` : "used / total");
  setText("hw-vram", hw.vram_free_mib != null ? `${hw.vram_free_mib} MiB free` : "--");
  setText("hw-disk", hw.disk_read_mb != null ? `${hw.disk_read_mb.toFixed(1)} / ${fmtNum(hw.disk_write_mb, "", 1)} MB` : "--");
  setText("hw-gpu", hw.gpu_name ? `${hw.gpu_name} ×${hw.gpu_count ?? 1}` : (hw.gpu_count ? `${hw.gpu_count} GPU(s)` : "--"));
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
      r.duration_s != null ? `${r.duration_s.toFixed(1)}s` : "--",
      r.finish || "--",
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
      if (c >= 2) td.className = "num";
      td.textContent = val;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });

  setText("requests-count", kept ? `${requests.length} recent · ${fmtInt(kept)} kept` : `${requests.length} recent`);
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

// ---------- Clock ----------
function tickClock() {
  const clock = $("clock");
  const now = new Date();
  clock.textContent = now.toLocaleTimeString();
  clock.setAttribute("datetime", now.toISOString());
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

function renderHero(throughput, power, context, cache) {
  const tok = throughput && throughput.now;
  setText("hero-tok", tok != null ? `${tok.toFixed(1)}` : "--");
  setText("hero-power", power && power.total_w != null ? `${power.total_w}` : "--");
  setText("hero-ctx", context && context.pct != null ? `${context.pct}` : "--");
  setText("hero-hit", cache && cache.hit_rate != null ? `${(cache.hit_rate * 100).toFixed(0)}` : "--");
}

async function refresh() {
  let data;
  try {
    data = await fetchStats();
    setBadge(false);
  } catch (err) {
    // No backend reachable — keep the last rendered state and flag the badge so
    // the user knows the numbers are not live.
    console.warn("stats endpoint unavailable", err);
    setBadge(true);
    return;
  }

  renderEngine(data.engine, data.config);
  renderLive(data.live, data.status);
  renderContext(data.context);
  renderThroughput(data.throughput, data.history);
  renderPower(data.power, data.history);
  renderGpu(data.gpu, data.history);
  renderHardware(data.hardware);
  renderCache(data.cache);
  renderSpec(data.spec);
  renderRequests(data.requests, data.requests_kept);
  renderAnalysis(data.analysis, data.telemetry, data.totals);
  renderSwitch(data.switch);
  renderLog(data.log);
  renderEndpoints(data.endpoints);
  renderHero(data.throughput, data.power, data.context, data.cache);
}

async function init() {
  // The countdown ring on the badge sweeps once per poll, so it has to know the
  // interval that JS actually uses.
  document.documentElement.style.setProperty("--poll-ms", `${REFRESH_MS}ms`);
  tickClock();
  wireLogReveal();
  await refresh();
  setInterval(tickClock, 1000);
  setInterval(refresh, REFRESH_MS);
}

await init();
