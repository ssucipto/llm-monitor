# ARCHIVE — homelab dashboard

Preserved deliverable. This directory (`ZedTest/homelab-dashboard/`) holds a complete,
working homelab status dashboard that was built as a **template**, not as a wired-up
monitor for any real hardware. It is archived so it can be adapted to a real homelab
later. Nothing here needs a build step, a package manager, or a browser extension:
five plain files, Python standard library only.

Status at archive time: **DONE and validated** (see the validation record in
`HANDOVER.md`). No outstanding work.

---

## 1. What it is

A **self-contained homelab status dashboard**: a static front end (`index.html` +
`style.css` + `app.js`) plus a small Python backend (`server.py`) that serves those
files *and* a live `/api/stats` JSON endpoint.

```
browser ──GET /api/stats──▶ server.py build_stats()   (real data where portable,
   ▲                          simulated where not)
   │
   └── app.js render*() updates the DOM by element ID, every REFRESH_MS (5 s)
```

Two independent halves joined by one contract:

| Half | What it does |
|---|---|
| Front end | Semantic, accessible markup; a dark theme that flips to light automatically; a JS layer that polls, renders, and animates. |
| Backend | `http.server` subclass that answers `/api/stats` with 12 keys of metrics, gathered fresh on every request. |

**The contract is the JSON shape, not the code.** Any backend that returns the shape
in §3 drives this page unchanged; any front end that updates the IDs in §4 is driven
by this backend unchanged. That is the whole point of the design, and it is what makes
the archive reusable.

There is no third-party dependency anywhere. `server.py` imports only stdlib modules
(`json os random shutil socket subprocess sys time datetime pathlib http.server
functools`); `app.js` uses only browser APIs.

---

## 2. File-by-file reference

| File | Role |
|---|---|
| `index.html` | The page: semantic shell, and the **element IDs that are the API contract**. |
| `style.css` | Appearance + the entire animation layer. Dark theme with automatic light mode. |
| `app.js` | Polls `/api/stats`, renders it into the IDs, schedules the next poll. |
| `server.py` | Static file server + `/api/stats` JSON endpoint (Python stdlib). |
| `README.md` | Run + wiring instructions (user-facing). |
| `HANDOVER.md` | Build-session record: decisions, validation, pitfalls. Historical. |
| `ARCHIVE.md` | This document: the implementation reference for future reuse. |

### `index.html` — semantic HTML as the contract

The markup is deliberately semantic rather than a wall of `<div>`s, so the page is
readable, keyboard-navigable, and screen-reader usable without any styling:

- **Head**: `lang="en"`, viewport meta, `<meta name="color-scheme" content="dark light">`,
  two `<meta name="theme-color">` values (one per `prefers-color-scheme`), a
  `data:image/svg+xml` favicon (no asset file needed), `<link rel="stylesheet">`,
  and `<script type="module" src="app.js">` — **`type="module"` makes it deferred**,
  so the DOM is fully parsed before `app.js` runs and no `DOMContentLoaded` guard is
  needed.
- **Accessibility furniture**: a `.skip` "Skip to the dashboard" link (visually hidden
  until focused, per `style.css`), and a `<noscript>` block explaining that the
  sections stay in their last rendered state.
- **`<header class="topbar">`** — sticky, with `<hgroup>` (title + tagline) and
  `<p class="topbar__meta">` holding `<time class="clock" id="clock">` and
  `<span class="refresh-badge" id="refresh-badge" role="status">`. The badge is
  `role="status"` so its **Live / Stale** text is announced to assistive tech.
- **`<nav class="toc">`** — an `<ol>` of fragment links to each panel, mirrored by the
  grid areas in `style.css`.
- **`<main id="main" class="layout">`** — a CSS grid of `<section class="panel …">`
  blocks, each `aria-labelledby` its own `<h2>`.

Key design decisions in the markup:

- **`<dl class="metrics">` of `<div class="metric" data-metric="…">`** — each metric is
  a `<dt>` label (wrapped in `<abbr title="…">` for an expandable acronym) and a `<dd>`
  value group. `data-metric` is a hook, not a style driver.
- **`<data class="metric__value" id="cpu-value" value="0">`** — the HTML
  `<data>` element carries the reading both as text and as its `value` attribute;
  `app.js` keeps both in sync.
- **`<meter class="metric__gauge" min="0" max="100" low="60" high="85" optimum="20" value="0">`**
  — a *native* gauge. The browser draws the bar from these attributes; `app.js` only
  writes `value`. The `low`/`high`/`optimum` triple is what makes the native bar
  colour itself, and it is the same 60/85 split the CSS severity classes use.
- **`<time id="uptime-value">`** (and `<time class="clock" id="clock">`) — machine-readable
  time via a `datetime` attribute that `app.js` sets on each update. Note: **no empty
  `datetime=""` appears in the markup** — an empty value is invalid HTML, so the
  attribute is simply omitted and JS supplies it.
- **Inline SVG sparkline** in a `<figure>`: a `<linearGradient id="spark-fill">`, a
  `<polygon id="cpu-area">`, a `<polyline id="cpu-spark" pathLength="1">`, and two
  `<circle>` markers (`cpu-halo`, `cpu-head`). `viewBox="0 0 100 30"` is the coordinate
  space `renderSpark()` computes into. `role="img"` + `aria-label` describe it.
- **`<table class="host-table">`** with a `<caption id="host-caption">`, `<thead>`
  `scope="col"` headers, and an **empty `<tbody id="host-tbody">`** — rows are built by
  `app.js`, and each row's first cell is a `<th scope="row">` so the table stays
  navigable for screen readers.
- **`<dialog class="confirm-dialog" id="confirm-dialog" closedby="any">`** containing
  `<form method="dialog">` and two `<button type="submit" value="cancel|reboot">`.
  This is a **native confirmation flow**: `app.js` calls `dialog.showModal()`, and the
  submit buttons produce `event.returnValue` on the dialog's `close` event — no custom
  modal, no keyboard-trap reimplementation. `closedby="any"` is what lets a click
  outside the dialog close it.
- **`<section class="panel log" id="log" hidden="until-found">`** — the system log ships
  **collapsed** and is revealed by find-in-page (`Ctrl+F`) or by the `#log` fragment
  link. `app.js` listens for `beforematch` to mark the reveal.
- **`<footer>`** states the contract in the page itself: the `id` attributes are the
  integration points.

### `style.css` — theme and the animation layer

- **Palette tokens in `:root`** (`--bg`, `--bg-elev`, `--bg-elev-2`, `--border`,
  `--text`, `--text-dim`, `--accent`, `--ok`, `--warn`, `--down`, plus `--radius`,
  `--shadow`, `--font`, `--mono`) with `color-scheme: dark light`.
- **`light-dark()` palette**: a `@supports (color: light-dark(red, red))` block
  redefines the tokens as `light-dark(dark-value, light-value)`, so the OS picks the
  scheme where the function is supported and the dark values remain the fallback where
  it is not. Progressive enhancement, not a second stylesheet.
- **Native gauge styling** via `::-webkit-meter-bar` /
  `::-webkit-meter-optimum-value` / `::-webkit-meter-suboptimum-value` /
  `::-webkit-meter-even-less-good-value`. Firefox renders its own native bar, which is
  accepted — hence the compensating rule that **numeric severity also drives the value
  text** (`.metric__value.is-ok / .is-warn / .is-bad`), so the reading is legible even
  where the bar cannot be restyled.
- **Layout** is a named-area grid (`cards / hosts / services / containers / controls / log`)
  with breakpoints at 860px (single column) and 480px (stacked topbar, single-column
  metrics).
- **The animation layer** (motion system) — every animation encodes data:
  - `@property --sweep { initial-value: 0deg; inherits: false }` — a **registered**
    custom property, required so `--sweep` can be animated at all.
  - `body::before` ambient backdrop: `position: fixed`, `z-index: -1`,
    **`pointer-events: none`** so it can never sit over the controls and swallow a click.
  - `.panel` entrance `panel-in`, delayed `calc(var(--i, 0) * 90ms)`; the `--i` index is
    assigned in CSS for the panels and **written by `app.js`** for rows, dots, badges and
    log entries. Choreography lives in CSS, data in JS.
  - Sparkline: `.spark__line { stroke-dasharray: 1 }` + `@keyframes spark-draw`
    (`stroke-dashoffset: 1 → 0`). Because the polyline carries `pathLength="1"`, the
    dash maths is **unit-free** — one dash spans the whole line regardless of point
    count, so the line redraws itself on every poll.
  - `@keyframes spark-fade` for the area, `ping` for the halo behind the head marker.
  - Countdown ring: `.refresh-badge::after` paints a `conic-gradient(from -90deg,
    var(--accent) var(--sweep), transparent 0)` masked to a ring, animated
    `sweep var(--poll-ms, 5s) linear infinite` — **`app.js` sets `--poll-ms` from
    `REFRESH_MS`**, so changing the refresh interval keeps the ring in sync.
  - `.container__fill` per-container CPU bar: `app.js` writes `width`, CSS
    `transition: width 650ms …` eases it.
  - Idle/urgency: `breathe` on running container badges, `dot-glow` on healthy dots
    (both staggered by `--i`), `urgent` on down dots, `alert` on `.metric__value.is-bad`.
  - Cascades: `row-in` for table rows, `log-in` for revealed log entries,
    `dialog-in` / `backdrop-in` for the confirmation dialog.
- **Reduced-motion guard is the LAST block in the sheet** (line 911 of 928). It sets
  `animation: none !important` and `transition-duration: 0.01ms !important` on
  `*`, `*::before`, `*::after`, then restores the *informational* fallbacks: the
  countdown ring renders as a full ring, and `.spark__line` keeps
  `stroke-dashoffset: 0` (drawn, not hidden). `app.js`'s `reducedMotion()` does the
  JS-side half — tweens commit their final value in one step.
- Totals for orientation: **15 `@keyframes`**, **1 `@property`**, balanced braces.

### `app.js` — poll, render, animate

- **Configuration**: `REFRESH_MS = 5000`, `SPARK_SAMPLES = 12`,
  `STATS_ENDPOINT = "api/stats"` — **relative**, so `fetch()` resolves it against the
  same origin as the page. Change the interval in one place; `init()` propagates it to
  CSS as `--poll-ms`.
- **Fallback inventory** (`HOSTS`, `CONTAINER_NAMES`, `SERVICES`) duplicated from
  `server.py`, used *only* when the endpoint is unreachable.
- **Helpers**: `$ = (id) => document.getElementById(id)`; `el(tag, cls, text)` node
  factory; `severity(pct)` (`>=85` bad, `>=60` warn, else ok — the same thresholds the
  `<meter>` attributes encode); `reducedMotion()`; `restart(node, name, ms)` which
  **re-assigns `node.style.animation`** to start a fresh animation each poll;
  `stagger(node, i)` writing `--i`.
- **`tweenNumber(node, to, suffix)`** — a `requestAnimationFrame` loop, cubic ease-out,
  600ms, reading its start value from a `displayed` map **keyed on `node.id`** so the
  previous reading survives across polls. Under `reducedMotion()` it commits the final
  value immediately, so a reading is never lost.
- **Data source**: `fetchStats()` (`fetch(..., { cache: "no-store" })`, throws on
  `!res.ok`) and `simulateStats()`, which **mirrors `build_stats()`'s shape exactly**.
  `refresh()` tries the endpoint, and on failure logs a warning, uses the simulation,
  and flips the badge to **Stale** via `setBadge(true)`. The page therefore always
  renders, and the user always knows whether the numbers are live.
- **Render functions are pure DOM updates keyed on IDs**: `renderStats`, `setMetric`,
  `renderSpark`, `renderHosts`, `renderContainers`, `renderServices`, `renderLog`,
  plus `wireLogReveal`, `wireControls`, `tickClock`, `setBadge`, `refresh`, `init`.
  Notable derivations: hosts count `online` as `cpu < 90`; containers count `running`;
  services count `up`; the per-container bar width is
  `Math.min(100, c.running ? c.cpu : 0)%`; a down service renders `unreachable`.
- **`init()`** sets `--poll-ms`, ticks the clock, wires the reveal + controls, runs the
  first `refresh()`, then schedules `setInterval(tickClock, 1000)` and
  `setInterval(refresh, REFRESH_MS)`.

### `server.py` — stdlib server + gatherers

- **`build_stats()`** calls the `gather_*()` functions and returns the 12-key dict
  (verbatim in §3).
- **Static inventory** at module level: `HOSTS` (4), `CONTAINER_NAMES` (6),
  `SERVICES` (5), `LOG_POOL` (info/warn/bad message pools). Names and addresses are
  template data; **live metrics are gathered per request**.
- **Gatherers, and what is real vs. simulated** — this is the crux of §5:

  | Function | Real source | Fallback |
  |---|---|---|
  | `gather_disk()` | `shutil.disk_usage("/")` (home dir if `/` absent) — **works on Windows and Unix** | `62 ± 4`% |
  | `gather_cpu()` | `os.getloadavg()[0] / cpu_count * 100` — **Unix only** (`OSError`/`AttributeError` elsewhere) | `rand(3, 78)` |
  | `gather_mem()` | `psutil.virtual_memory()` **if psutil is installed** (optional import, not stdlib) | `rand(35, 88)` |
  | `gather_uptime()` | `/proc/uptime` — **Linux only** | random days/hours |
  | `gather_hosts()` | none — per-host load is not portable across a network | fully simulated |
  | `gather_containers()` | `docker ps -a --format "{{json .}}"` (3s timeout, `check=True`); `running` = `Status` starts with `Up` | simulated over `CONTAINER_NAMES` |
  | `gather_services()` | TCP `socket.connect(("127.0.0.1", port))`, 0.2s timeout, `ms` measured with `perf_counter` | random up/down |
  | `gather_log()` | timestamps are real (`datetime.now(timezone.utc)`); messages drawn from `LOG_POOL` | — |

  Note `gather_containers()` gets **real names and real running state** from `docker ps`
  but still simulates per-container `cpu`/`mem` — that is the obvious upgrade path
  (`docker stats --no-stream`).
- **`serve(port)`**: a `_Handler` subclass of `SimpleHTTPRequestHandler` whose `do_GET`
  intercepts `self.path.rstrip("/") == "/api/stats"` (so `/api/stats` and `/api/stats/`
  both work), replying 200 with `Content-Type: application/json` and an explicit
  `Content-Length`; everything else falls through to `super().do_GET()`. The served
  root is **pinned to the script's own directory** via
  `functools.partial(_Handler, directory=root)` + `ThreadingHTTPServer(("127.0.0.1", port))`
  + `serve_forever()`, so it works regardless of the caller's CWD.
- **`__main__`**: `port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT_DEFAULT`
  (`PORT_DEFAULT = 8000`), prints the URL, then `serve(port)`.

---

## 3. The `/api/stats` JSON contract

Verbatim from `server.py`'s module docstring (and reproduced in `README.md` and
`HANDOVER.md`):

```json
{
  "cpu": 42.0, "cpu_hint": "load 1.20 · 8 cores",
  "mem": 61.0, "mem_hint": "9.8 / 16 GB",
  "disk": 62.0, "disk_hint": "285 / 460 GB",
  "uptime": "12d 4h", "uptime_iso": "P12DT4H",
  "hosts":      [{"name","ip","os","cpu","mem"}],
  "containers": [{"name","running","cpu","mem"}],
  "services":   [{"name","port","ok","ms"}],
  "log":        [{"level","iso","msg"}]
}
```

Exactly **12 top-level keys**. Field-level detail, as actually produced by the code:

| Key | Type | Produced by | Notes |
|---|---|---|---|
| `cpu` | float, 1 dp, clamped 0–100 | `gather_cpu()` | percent of total core capacity |
| `cpu_hint` | string | `gather_cpu()` | `"load {1.2f} · {cores} cores"` |
| `mem` | float, 1 dp | `gather_mem()` | percent used |
| `mem_hint` | string | `gather_mem()` | `"used / total GB"` |
| `disk` | float, 1 dp, clamped 0–100 | `gather_disk()` | `used / total * 100` |
| `disk_hint` | string | `gather_disk()` | `"used / total GB"` |
| `uptime` | string | `gather_uptime()` | `"{d}d {h}h"` |
| `uptime_iso` | string | `gather_uptime()` | ISO-8601 duration `P{d}DT{h}H` → `<time datetime>` |
| `hosts[]` | `{name: str, ip: str, os: str, cpu: float, mem: float}` | `gather_hosts()` | `mem` is derived as `cpu * 0.8` in the template |
| `containers[]` | `{name: str, running: bool, cpu: float, mem: int}` | `gather_containers()` | `running` from `Status` prefix `Up`; `mem` in **MB** |
| `services[]` | `{name: str, port: int, ok: bool, ms: int \| null}` | `gather_services()` | `ms` is `null` when unreachable |
| `log[]` | `{level: "info"\|"warn"\|"bad", iso: str, msg: str}` | `gather_log()` | 6 entries, newest first, `iso` is UTC |

Consumer side (`app.js`): `renderStats()` reads `cpu/cpu_hint/mem/mem_hint/disk/disk_hint/
uptime/uptime_iso`; `refresh()` passes `data.hosts`, `data.containers`, `data.services`,
`data.log` to their renderers. `simulateStats()` returns the same 12 keys, which is why
the `file://` fallback needs no special-casing downstream.

---

## 4. The element-ID contract

`app.js` looks up these IDs with `$("id")`. **These are the integration points**: if you
swap the data source, these are the only hooks the front end has.

Looked up by literal ID (18):

| ID | Element | Written by |
|---|---|---|
| `clock` | `<time>` in the topbar | `tickClock()` — text + `datetime` |
| `refresh-badge` | `<span role="status">` | `setBadge()` — `Live`/`Stale` + `is-error` |
| `uptime-value` | `<time>` metric | `renderStats()` — text + `datetime` |
| `cpu-spark` | `<polyline pathLength="1">` | `renderSpark()` — `points`, restart animation |
| `cpu-area` | `<polygon>` | `renderSpark()` — `points`, `spark-fade` |
| `cpu-head` | `<circle>` | `renderSpark()` — `cx`/`cy` |
| `cpu-halo` | `<circle>` | `renderSpark()` — `cx`/`cy` |
| `spark-caption` | `<figcaption>` | `renderSpark()` — sample count |
| `host-tbody` | `<tbody>` | `renderHosts()` — rebuilt rows |
| `hosts-count` | `<p class="panel__count">` | `renderHosts()` — `n/m online` |
| `container-list` | `<ul>` | `renderContainers()` — rebuilt items |
| `containers-count` | `<p>` | `renderContainers()` — `n/m running` |
| `service-list` | `<ul>` | `renderServices()` — rebuilt items |
| `services-count` | `<p>` | `renderServices()` — `n/m up` |
| `log-list` | `<ol>` | `renderLog()` — rebuilt entries |
| `log` | `<section hidden="until-found">` | `wireLogReveal()` — `beforematch` → `revealed` |
| `confirm-dialog` | `<dialog closedby="any">` | `wireControls()` — `showModal()`, `close` |
| `reboot-btn` | `<button>` | `wireControls()` — label + `btn--used` |

Looked up by **templated** ID — `setMetric(key, …)` builds `` `${key}-value` ``,
`` `${key}-gauge` ``, `` `${key}-hint` `` for `key ∈ {cpu, mem, disk}` (9 more):
`cpu-value`, `cpu-gauge`, `cpu-hint`, `mem-value`, `mem-gauge`, `mem-hint`,
`disk-value`, `disk-gauge`, `disk-hint`.

**27 IDs touched by `app.js`** out of **41 unique `id=` attributes in `index.html`** —
the remainder are anchors and headings used by the TOC/`aria-labelledby`
(`main`, `overview`, `overview-h`, `hosts`, `hosts-h`, `containers`, `containers-h`,
`services`, `services-h`, `controls`, `controls-h`, `log-h`, `host-caption`,
`spark-fill`), which are structural rather than data hooks.

---

## 5. How to adapt it to a real homelab

**The front end does not need to change.** `app.js`'s `render*()` functions are pure
DOM updates keyed on IDs; the JSON shape is the only thing they care about. So the
upgrade path is almost entirely inside `server.py`.

1. **Replace the `gather_*()` bodies** with real sources, keeping the return shapes:
   - **Per-host CPU/mem** (`gather_hosts()`): SSH to each host and parse a one-liner,
     e.g. `ssh root@10.0.0.10 "printf '%s %s' \"$(top -bn1 | ...)\" …"`, or read
     `/proc/stat` + `/proc/meminfo`. Cache per host with a TTL — a 5s poll across four
     SSH round-trips will be slower than the poll interval.
   - **Real container stats**: `docker ps -a --format "{{json .}}"` already gives real
     names and running state; add `docker stats --no-stream --format "{{json .}}"`
     and parse `Cpu%` / `Mem` into `cpu: float`, `mem: int` (MB). Or read the cgroup
     files directly if you want to avoid the docker CLI cost.
   - **Service probes**: replace the TCP-connect probe with a real HTTP check against
     each service's base URL (`urllib.request.urlopen`, `timeout=…`, record the
     elapsed ms and the status code). Keep `ms: None` for unreachable so the front end
     still renders `unreachable`.
   - **Memory**: install `psutil` (the code already tries it and falls back), or read
     `/sys/devices/.../meminfo` / `wmic` / `GetSystemInfo` per platform.
   - **Log**: replace `gather_log()` with a real journal — `journalctl -o json -n 6`,
     `systemctl` state, or your monitoring tool's feed. Keep `level` in
     `info|warn|bad`; the CSS classes `lvl--info/warn/bad` are generated from it.
2. **Keep the key names and types identical.** If a field is missing or renamed, the
   corresponding renderer throws or renders `undefined`. If you *add* fields, nothing
   breaks — they are simply ignored.
3. **If you want a different endpoint**, change `STATS_ENDPOINT` in `app.js` (it is
   relative, so it resolves against the page's origin — an absolute path like
   `/api/stats` or a full URL both work). Or change the body of `fetchStats()` to call
   a shell/CGI layer, a WebSocket, or a static JSON file written by a cron job.
   Nothing else in the page needs to change.
4. **To add a section**: copy a `<section class="panel">` block in `index.html`
   (give it a unique `id`, an `aria-labelledby` heading, and a `<p class="panel__count">`
   if it counts things), add a `grid-area` in `.layout`'s `grid-template-areas`, add a
   TOC `<li>`, and add a matching `render*()` in `app.js` that writes into the new IDs.
5. **Tuning knobs**: severity thresholds live in two places that must agree —
   `severity()` in `app.js` (`>=85` bad, `>=60` warn) and the `<meter>` attributes
   `low="60" high="85"` in `index.html`. Colours and spacing are `:root` tokens in
   `style.css`. Refresh interval is `REFRESH_MS` in `app.js` (propagated to CSS as
   `--poll-ms`).
6. **The `reboot-btn` / `confirm-dialog` pair is a stub** — the dialog's body says so.
   Wire the submit handler to a real endpoint: on `close`, if
   `event.returnValue === "reboot"`, `fetch()` your real action. Keep the native
   `<dialog>`; it already handles focus, Escape, and the backdrop.

---

## 6. Run instructions

```bash
cd ZedTest/homelab-dashboard
python server.py            # default port 8000
python server.py 8080       # pass a port to change it
```

Then open **http://localhost:8000**. The header badge reads **Live**, the clock ticks
every second, and the metrics refresh every 5 seconds. Ctrl+C stops the server.

Notes:

- The server binds to `127.0.0.1` only, and pins its served root to the directory
  containing `server.py` — so it can be launched from any CWD.
- `gather_containers()` shells out to `docker` with a 3s timeout, and
  `gather_services()` opens a TCP socket per service with a 0.2s timeout. On a machine
  with no docker and nothing listening, that costs roughly a second per poll; it is
  still well inside the 5s interval.
- **`file://` fallback**: opening `index.html` directly also works. `fetch("api/stats")`
  fails, `refresh()` catches it, `simulateStats()` fills the same shape, and the badge
  flips to **Stale** (with the countdown ring hidden). Useful for eyeballing layout and
  styling without the backend — but the numbers are then not real.
- Validation history (from `HANDOVER.md`): `server.py` on port 8797 returned **200** for
  `/`, `/style.css`, `/app.js` and `/api/stats` with 12 keys; `node --check app.js`
  passed; diagnostics were clean on all three front-end files.

---

## 7. Known pitfalls

These are real traps hit while building this, not hypotheticals. They are carried over
from `HANDOVER.md` and still apply if you edit the files.

- **`shutil.disk_usage` returns `(total, used, free)`** — unpacking it as
  `(used, _free, total)` produced **237%** on Windows. The code now reads
  `total, used, _free = shutil.disk_usage(path)`.
- **Detached processes get killed** by the sandbox at command end. A server must be
  backgrounded **within the same command** as its checks:
  `python server.py 8765 & sleep 2; curl -s localhost:8765/api/stats`.
- **Class tokens with dots don't match compound CSS selectors** — a single token like
  `metric__value.is-ok` is not the same as two tokens. `app.js` emits
  `metric__value` **plus** `is-ok` as separate classes.
- **`dialog::before` with `position: fixed` blocked interaction** with the dialog's
  buttons. The sheet uses `::open`, `::close` and `::backdrop` instead, so the backdrop
  only paints when the dialog is open.
- **`hidden="until-found"`** needs `contain-intrinsic-size: auto 220px` on `.panel.log`
  to avoid a layout jump when it reveals, and must **not** get an entrance animation
  (it would fight the reveal) — `.panel.log { animation: none }`.
- **The reduced-motion guard must be the LAST block in the stylesheet.** Inserting the
  motion system *after* it silently overrode the guard's non-important fallbacks
  (static ring, drawn sparkline) — `animation: none !important` still won, but the
  fallbacks lost. Source order, not `!important`, is what protects them.
- **A CSS transition cannot be re-triggered from JS** the way an animation can. The
  sparkline redraw is an animation that `restart()` re-assigns each poll.
- **`@property --sweep` is required** for the countdown ring: an unregistered custom
  property cannot be animated — it flips at the boundary instead of sweeping.
- **Empty `datetime=""` attributes are invalid HTML** — omitted from the markup; JS sets
  them on update.
- **`http.server.test(HandlerClass=…, port=…, directory=root)` raises
  `TypeError` on Python 3.12** — `directory` was never a parameter (the signature is
  `(HandlerClass, ServerClass, protocol, port, bind)` and it reads `os.getcwd()`
  internally). The working form is `functools.partial(_Handler, directory=root)` +
  `ThreadingHTTPServer` + `serve_forever()`, which also pins the root to the script's
  directory.
- **Severity thresholds**: metrics `>=85` bad, `>=60` warn, else ok. Service status in
  the front end is binary (`ok` → `dot--up`, else `dot--down`); the `dot--degraded`
  class and a `>=90` down / `>=60` degraded split exist in CSS but are not currently
  emitted by `renderServices()`.

### Environment notes at archive time

- Windows; project root `C:\Project\ZedTest`, tool paths in `ZedTest/...` form.
- **Not a git repository** — the ACP `git_workflow` branch check does not apply to this
  standalone deliverable.
- Natural follow-ups that were **not** started: per-host SSH gatherers, real `docker ps`
  stat parsing, HTTPS service probes, a `favicon`/PWA manifest.
