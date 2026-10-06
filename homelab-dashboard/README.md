# Homelab Dashboard

> **Archive status** — this project is preserved as a working template, not wired to
> any real hardware. See **`ARCHIVE.md`** for the full implementation reference: the
> file-by-file design record, the exact `/api/stats` contract, the element-ID hooks,
> adaptation guidance, and the pitfalls hit while building it.

A self-contained homelab dashboard: static front end plus a small Python backend
that serves it and a live `/api/stats` endpoint. No build step, no third-party
dependencies (stdlib only).

## Files

| File         | Purpose                                                            |
|--------------|--------------------------------------------------------------------|
| `index.html` | Page structure — semantic shell, element IDs are the API contract  |
| `style.css`  | Dark theme with automatic light mode (`light-dark()` palette)      |
| `app.js`     | Fetches `/api/stats`, renders, auto-refreshes every 5 s            |
| `server.py`  | Static server + `/api/stats` JSON endpoint (Python stdlib)         |

## Run it

```bash
cd homelab-dashboard
python server.py          # default port 8000; pass one to change: python server.py 8080
```

Then open **http://localhost:8000**. The badge in the header reads **Live** and
the numbers refresh every 5 seconds.

Opening `index.html` directly as a `file://` also works: `app.js` falls back to
a client-side simulation and flips the badge to **Stale**, so you can eyeball
the layout without the backend.

## `/api/stats` shape

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

The element IDs in `index.html` (`cpu-value`, `mem-gauge`, `host-tbody`,
`container-list`, `service-list`, `log-list`, …) are the contract: `app.js`
updates them by ID, so any backend returning the shape above drives the page.

## Going fully live

`server.py` already uses real data where the platform can measure it —
`shutil.disk_usage` for disk, `os.getloadavg()` for CPU (Unix), `/proc/uptime`
for uptime, `docker ps -a` for containers, and TCP probes for service ports.
Where a value can't be measured portably it falls back to a simulation.

To make it fully live on your own homelab, replace the `gather_*()` bodies in
`server.py` with your sources — e.g. SSH to each host for per-host CPU/mem,
`docker ps` output parsing for real container stats, and actual HTTP checks
against each service's base URL instead of TCP-connect probes. The response
shape is the only thing `app.js` cares about.

## Animation

Motion encodes data rather than decorating the page, so it stays useful on a
live dashboard:

- **Tweened readings** — CPU/mem/disk numbers ease from their previous value to
  the new one, so a jump is visible rather than a snap.
- **Self-redrawing sparkline** — `pathLength="1"` makes the dash maths unit-free,
  so the line redraws itself on every poll; the head marker rides the newest
  sample and a halo pings behind it.
- **Countdown ring** — the header badge sweeps a conic ring once per poll, so it
  reads as a timer. Its duration comes from `--poll-ms`, which `app.js` sets from
  `REFRESH_MS`, so changing the interval keeps the ring in sync.
- **Per-container CPU bar** — `app.js` writes the width, CSS eases it.
- **Breathing / urgency** — running containers and healthy dots idle on staggered
  delays; failures pulse.
- **Entrance choreography** — panels, table rows and log entries cascade in via
  a `--i` stagger index assigned by `app.js`.

All of it is informational, so the `prefers-reduced-motion: reduce` block at the
**bottom** of `style.css` switches the whole layer off without losing any reading
— gauges, dots, badges and bars still carry state in colour and text. If you add
animations, keep that block last: source order, not just `!important`, is what
protects the fallbacks inside it.

## Customizing

- Colors, spacing, severity thresholds (`--ok` / `--warn` / `--bad`) live in
  `:root` in `style.css`.
- Refresh interval: `REFRESH_MS` in `app.js`.
- Add a section by copying a `<section class="panel">` block in `index.html`
  and adding a matching `render*()` function in `app.js`.
