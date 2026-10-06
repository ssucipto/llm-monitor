/* Homelab Dashboard
 *
 * Loaded as type="module", so it is deferred: the DOM is parsed before this runs.
 * Data comes from the backend's /api/stats endpoint (see server.py). If that
 * endpoint is unreachable — e.g. the page was opened directly as a file:// —
 * a client-side simulation fills the same shape, so the page always renders.
 * The element IDs in index.html are the contract between backend and front end.
 */

// ---------- Configuration ----------
const REFRESH_MS = 5000;
const SPARK_SAMPLES = 12;
const STATS_ENDPOINT = "api/stats";

// Fallback inventory, used only when /api/stats is unavailable.
const HOSTS = [
  { name: "rack-01", ip: "10.0.0.10", os: "Proxmox" },
  { name: "rack-02", ip: "10.0.0.11", os: "Debian 12" },
  { name: "nas", ip: "10.0.0.20", os: "TrueNAS" },
  { name: "wifi-ap", ip: "10.0.0.2", os: "OpenWrt" },
];
const CONTAINER_NAMES = ["nginx", "postgres", "vaultwarden", "plex", "pihole", "portainer"];
const SERVICES = [
  { name: "Web", port: 80 },
  { name: "SSH", port: 22 },
  { name: "Plex", port: 32400 },
  { name: "Vaultwarden", port: 8200 },
  { name: "Portainer", port: 9443 },
];

// ---------- Helpers ----------
const $ = (id) => document.getElementById(id);

function rand(min, max) {
  return Math.random() * (max - min) + min;
}

function randInt(min, max) {
  return Math.floor(rand(min, max + 1));
}

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

// Severity thresholds shared by the <meter> gauges and the value text, so the
// reading is consistent even where the native bar cannot be restyled (Firefox).
function severity(pct) {
  if (pct >= 85) return "bad";
  if (pct >= 60) return "warn";
  return "ok";
}

// Every animation in this layer is informational: when the OS asks for reduced
// motion, the tweens below resolve to their final value in a single step.
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

// The big readings ease from their previous value to the new one, so the number
// carries the delta between polls instead of snapping.
const displayed = {};

function tweenNumber(node, to, suffix) {
  const from = displayed[node.id] ?? 0;
  displayed[node.id] = to;

  const commit = (v) => {
    node.textContent = `${v.toFixed(0)}${suffix}`;
    node.setAttribute("value", v.toFixed(0));
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

// ---------- Data source ----------
async function fetchStats() {
  const res = await fetch(STATS_ENDPOINT, { cache: "no-store" });
  if (!res.ok) throw new Error(`stats ${res.status}`);
  return res.json();
}

// Mirrors server.py's build_stats() shape, for the file:// fallback.
function simulateStats() {
  const cpu = rand(3, 78);
  const mem = rand(35, 88);
  const disk = 62 + rand(-4, 4);
  const days = randInt(2, 45);
  const hours = randInt(0, 23);
  return {
    cpu,
    cpu_hint: `load ${rand(0.1, 2.4).toFixed(2)} · ${randInt(4, 16)} cores`,
    mem,
    mem_hint: `${(mem * 0.16).toFixed(1)} / 16 GB`,
    disk,
    disk_hint: `${(disk * 4.6).toFixed(0)} / 460 GB`,
    uptime: `${days}d ${hours}h`,
    uptime_iso: `P${days}DT${hours}H`,
    hosts: HOSTS.map((h) => {
      const c = rand(2, 95);
      return { ...h, cpu: c, mem: c * 0.8 };
    }),
    containers: CONTAINER_NAMES.map((name) => ({
      name,
      running: Math.random() > 0.12,
      cpu: rand(0.5, 45),
      mem: randInt(50, 900),
    })),
    services: SERVICES.map((s) => {
      const ok = Math.random() > 0.1;
      return { ...s, ok, ms: ok ? randInt(4, 180) : null };
    }),
    log: Array.from({ length: 6 }, (undefined, i) => {
      const level = LOG_LEVELS[randInt(0, LOG_LEVELS.length - 1)];
      const when = new Date(Date.now() - i * randInt(60, 3600) * 1000);
      return { level, iso: when.toISOString(), msg: logMessage(level) };
    }),
  };
}

// ---------- Overview ----------
const cpuHistory = [];

function renderStats(data) {
  setMetric("cpu", data.cpu, data.cpu_hint);
  setMetric("mem", data.mem, data.mem_hint);
  setMetric("disk", data.disk, data.disk_hint);

  const uptime = $("uptime-value");
  uptime.textContent = data.uptime;
  uptime.setAttribute("datetime", data.uptime_iso);

  cpuHistory.push(data.cpu);
  while (cpuHistory.length > SPARK_SAMPLES) cpuHistory.shift();
  renderSpark();
}

function setMetric(key, pct, hint) {
  const value = $(`${key}-value`);
  const gauge = $(`${key}-gauge`);
  const hintEl = $(`${key}-hint`);

  tweenNumber(value, pct, "%");
  value.classList.remove("is-ok", "is-warn", "is-bad");
  value.classList.add(`is-${severity(pct)}`);

  // <meter> drives its own bar from these attributes.
  gauge.setAttribute("value", pct.toFixed(0));
  hintEl.textContent = hint;
}

function renderSpark() {
  const line = $("cpu-spark");
  const area = $("cpu-area");
  const head = $("cpu-head");
  const halo = $("cpu-halo");
  if (!line || cpuHistory.length < 2) return;

  const step = 100 / (SPARK_SAMPLES - 1);
  const pts = cpuHistory.map((v, i) => [i * step, 30 - (v / 100) * 30]);
  const text = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`);
  line.setAttribute("points", text.join(" "));

  // The area polygon is the same outline closed down to the baseline.
  if (area) {
    const [xLast, yLast] = pts.at(-1);
    area.setAttribute("points", `${pts[0][0].toFixed(1)},30 ${text.join(" ")} ${xLast.toFixed(1)},30`);
    // The head marker rides the newest sample; the halo pings behind it.
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
  $("spark-caption").textContent = `CPU, last ${cpuHistory.length} samples`;
}

// ---------- Hosts ----------
function renderHosts(hosts) {
  const tbody = $("host-tbody");
  tbody.innerHTML = "";
  let online = 0;

  hosts.forEach((h, i) => {
    if (h.cpu < 90) online++;

    const tr = el("tr");
    stagger(tr, i);
    const name = el("th", "num", h.name);
    name.setAttribute("scope", "row");
    tr.appendChild(name);
    tr.appendChild(el("td", "num", h.ip));
    tr.appendChild(el("td", null, h.os));
    tr.appendChild(el("td", "num", `${h.cpu.toFixed(0)}%`));
    tr.appendChild(el("td", "num", `${h.mem.toFixed(0)}%`));
    tbody.appendChild(tr);
  });

  $("hosts-count").textContent = `${online}/${hosts.length} online`;
}

// ---------- Containers ----------
function renderContainers(containers) {
  const list = $("container-list");
  list.innerHTML = "";
  let running = 0;

  containers.forEach((c, i) => {
    if (c.running) running++;
    const cpu = c.running ? c.cpu.toFixed(1) : "0.0";
    const mem = c.running ? c.mem : 0;

    const li = el("li", "container");
    const top = el("div", "container__top");
    top.appendChild(el("span", "container__name", c.name));
    const status = el("span", c.running ? "container__status--running" : "container__status--exited", c.running ? "running" : "exited");
    stagger(status, i);
    top.appendChild(status);
    li.appendChild(top);

    const stats = el("div", "container__stats");
    stats.appendChild(el("span", null, "CPU ")).appendChild(el("strong", null, `${cpu}%`));
    stats.appendChild(el("span", null, "MEM ")).appendChild(el("strong", null, `${mem} MB`));
    li.appendChild(stats);

    // Per-container CPU bar: app.js writes the width, style.css eases it, so the
    // bar carries the reading between polls.
    const track = el("div", "container__track");
    const fill = el("span", "container__fill");
    fill.style.width = `${Math.min(100, c.running ? c.cpu : 0)}%`;
    track.appendChild(fill);
    li.appendChild(track);

    list.appendChild(li);
  });

  $("containers-count").textContent = `${running}/${containers.length} running`;
}

// ---------- Services ----------
function renderServices(services) {
  const list = $("service-list");
  list.innerHTML = "";
  let up = 0;

  services.forEach((s, i) => {
    if (s.ok) up++;

    const li = el("li", "service");
    const main = el("div", "service__main");
    const dot = el("span", `dot--${s.ok ? "up" : "down"}`, "");
    stagger(dot, i);
    main.appendChild(dot);
    main.appendChild(el("span", "service__name", s.name));
    main.appendChild(el("span", "service__port", `:${s.port}`));
    li.appendChild(main);

    const resp = el("span", `service__resp is-${s.ok ? "ok" : "bad"}`, s.ok ? `${s.ms} ms` : "unreachable");
    li.appendChild(resp);

    list.appendChild(li);
  });

  $("services-count").textContent = `${up}/${services.length} up`;
}

// ---------- System log ----------
const LOG_LEVELS = ["info", "info", "info", "warn", "bad"];

function renderLog(entries) {
  const list = $("log-list");
  list.innerHTML = "";

  entries.forEach((e, i) => {
    const li = el("li", `lvl--${e.level}`);
    stagger(li, i);
    const when = new Date(e.iso);
    const time = el("time", null, when.toLocaleTimeString());
    time.setAttribute("datetime", e.iso);
    li.appendChild(time);
    li.appendChild(document.createTextNode(" " + e.msg));
    list.appendChild(li);
  });
}

function logMessage(level) {
  const pool = {
    info: ["nginx reaped 1 worker", "postgres fsck clean", "vaultwarden rekeyed", "portainer synced 6 units"],
    warn: ["disk on /srv above 60%", "wifi-ap dns timeout 4s", "plex transcode queue backed up"],
    bad: ["rack-02 sshd refused connection", "nas SMART pool degraded"],
  };
  return pool[level][randInt(0, pool[level].length - 1)];
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

// ---------- Controls ----------
function wireControls() {
  const dialog = $("confirm-dialog");
  const btn = $("reboot-btn");
  if (!dialog || !btn) return;

  btn.addEventListener("click", () => {
    dialog.showModal();
    dialog.addEventListener("close", (event) => {
      btn.textContent = event.returnValue === "reboot" ? "Reboot queued" : "Dismissed";
      btn.classList.add("btn--used");
    });
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

async function refresh() {
  let data;
  try {
    data = await fetchStats();
    setBadge(false);
  } catch (err) {
    // No backend reachable (file:// or server down) — render a simulation and
    // flag the badge so the user knows the numbers are not live.
    console.warn("stats endpoint unavailable, using simulation", err);
    data = simulateStats();
    setBadge(true);
  }

  renderStats(data);
  renderHosts(data.hosts);
  renderContainers(data.containers);
  renderServices(data.services);
  renderLog(data.log);
}

// ---------- Wiring for real data ----------
//
// The backend (server.py) already returns the shape consumed here. To point at a
// different source, change STATS_ENDPOINT or the body of fetchStats(); the render*()
// functions are pure DOM updates, so nothing else in the page needs to change.

async function init() {
  // The countdown ring on the badge sweeps once per poll, so it has to know the
  // interval that JS actually uses.
  document.documentElement.style.setProperty("--poll-ms", `${REFRESH_MS}ms`);
  tickClock();
  wireLogReveal();
  wireControls();
  await refresh();
  setInterval(tickClock, 1000);
  setInterval(refresh, REFRESH_MS);
}

await init();
