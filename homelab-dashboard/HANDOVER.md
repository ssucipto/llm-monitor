# HANDOVER — homelab dashboard + live backend

Status: **DONE**. Front end, backend, and a full animation layer all shipped and
validated. This note records what shipped, the contract, and the validation
actually run — kept for reference.

## Task (verbatim, in order)

1. "create simple website for homelab dashboard template"
2. "can you run it in a browser"
3. "research and deep dive, and then modernize the index.html to the best of your creativity"
4. "add a small /api/stats backend (Node or Python) to make it fully live, or open it in the browser to eyeball the new layout"
5. "improvise the latest home-lab site with full animation"

Deliverable: `ZedTest\website\`.

## Files

| Path | Role |
|---|---|
| `ZedTest\website\index.html` | semantic markup — element IDs are the API contract |
| `ZedTest\website\style.css`  | dark theme + auto light mode |
| `ZedTest\website\app.js`     | fetches `/api/stats`, renders, 5 s refresh, `file://` fallback |
| `ZedTest\website\server.py`  | Python stdlib static server + `/api/stats` |
| `ZedTest\website\README.md`  | run + wiring instructions (updated for the backend) |

## Decisions

- **Python backend** (user offered Node or Python) — stdlib-only `http.server`, no deps.
- `STATS_ENDPOINT = "api/stats"` is **relative**, so it resolves against the same origin.
- `simulateStats()` in `app.js` mirrors `server.py`'s shape; the header badge flips to
  **Stale** when the endpoint is unreachable (e.g. opened as `file://`), so the page
  always renders and the user always knows whether numbers are live.
- Real data where portable: `shutil.disk_usage`, `os.getloadavg()`, `/proc/uptime`,
  `docker ps -a`, TCP probes on `127.0.0.1`. Simulated elsewhere.

## Contract

`server.py → build_stats()` returns:

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

`app.js` render functions are pure DOM updates keyed on IDs in `index.html`:
`clock`, `refresh-badge`, `uptime-value`, `cpu-spark`, `spark-caption`,
`host-tbody`, `hosts-count`, `container-list`, `containers-count`,
`service-list`, `services-count`, `log-list`, `confirm-dialog`, `reboot-btn`,
plus the templated `{cpu,mem,disk}-{value,gauge,hint}` (9 IDs).

## Animation layer (pass 5)

Motion encodes data, not decoration. Design decisions:

- **Tweened numbers** (`tweenNumber()` in `app.js`) — rAF loop, cubic ease-out,
  600 ms. Reads from a `displayed` map keyed on `node.id` so the previous value
  survives across polls. Under `reducedMotion()` it commits the final value in one
  step, so the reading is never lost.
- **Sparkline redraw** — `pathLength="1"` on the polyline makes `stroke-dasharray:
  1` unit-free, so one dash covers the whole line regardless of point count. `app.js`
  **re-assigns** `animation` via `restart()` to start a fresh animation each poll;
  a CSS transition cannot be re-triggered this way, which is why it is an animation.
- **Countdown ring** — `conic-gradient` + `@property --sweep` (registered so it can
  animate) sweeps once per `--poll-ms`, which `init()` sets from `REFRESH_MS`.
- **Stagger** — `app.js` writes a `--i` index; `style.css` multiplies it by a
  per-element delay. Keeps the choreography in CSS, the data in JS.
- **`body::before` backdrop** — `pointer-events: none` and `z-index: -1` so it can
  never sit over the controls and swallow a click (this bit us with the dialog).

## Validation (all pass)

- `node --check app.js` → syntax OK.
- `diagnostics` on `app.js` / `index.html` / `style.css` → no errors or warnings.
- ID/class contract re-checked against the **rewritten** files: every `$("id")`
  resolves; 0 missing, 0 duplicate IDs, 41 IDs total; HTML tag balance 0 errors.
- Keyframe contract: both JS-driven names (`spark-draw`, `spark-fade`) defined in
  CSS; 15 keyframes total.
- CSS braces balanced (185 open / 185 close); 1 `@property` block.
- **Reduced-motion guard is genuinely last** in `style.css` (line 905 of 926);
  the only animation declaration after it is its own `animation: none !important`.
- **End-to-end**: `server.py` on 8797 → `GET /` **200**, `/style.css` **200**,
  `/app.js` **200**, `/api/stats` **200** with 12 keys.

## Bug found and fixed during this pass

`http.server.test(HandlerClass=..., port=..., directory=root)` raised
`TypeError: test() got an unexpected keyword argument 'directory'` on **Python 3.12**
(the signature is `(HandlerClass, ServerClass, protocol, port, bind)`; `directory`
was never a parameter — it reads `os.getcwd()` internally). Replaced with an
explicit `functools.partial(_Handler, directory=root)` + `ThreadingHTTPServer`
+ `serve_forever()`, which works on 3.8+ and pins the served root to the script's
directory regardless of the caller's CWD.

## Pitfalls (tried, didn't work)

- **The reduced-motion guard must be the LAST block in the stylesheet.** I first
  inserted the motion system *after* the guard, so the guard's non-important
  fallbacks (static countdown ring, drawn sparkline) were overridden by the later
  rules. `animation: none !important` still wins on specificity, but the fallbacks
  inside the guard silently lost. Fixed by moving the guard to the true end of the
  sheet and asserting it with `grep -n` + an `awk` scan for declarations after it.
- **A CSS transition cannot be re-triggered from JS** the way an animation can, so
  the sparkline redraw is an animation that `restart()` re-assigns, not a transition.
- **`@property --sweep` is required** for the countdown ring: an unregistered custom
  property cannot be animated (it flips at the boundary instead of sweeping).
- **`shutil.disk_usage` returns `(total, used, free)`** — unpacking `(used, _free, total)`
  gave 237% on Windows. Fixed to `(total, used, _free)`.
- **Detached processes get killed** by the sandbox at command end. A server must be
  backgrounded *within the same command* as its `curl` checks:
  `python server.py 8765 & sleep 2; curl ...`.
- **Class tokens with dots** (`metric__value.is-ok`) don't match compound CSS selectors —
  split into two tokens (`metric__value` + `is-ok`).
- **`dialog::before` with `position: fixed`** blocked interaction — used
  `::open` / `::close` / `::backdrop` instead.
- **`hidden="until-found"`** needs `contain-intrinsic-size: auto 220px` to avoid a layout
  jump, and must not get an entrance animation (it would fight the reveal) — `.panel.log`
  sets `animation: none`.
- **Empty `datetime=""` attributes** are invalid HTML — omitted; JS sets them on update.
- **Severity thresholds**: `>=85` bad, `>=60` warn, else ok. Service status: `>=90` down,
  `>=60` degraded, else up.

## Environment

- Windows. Project root `C:\Project\ZedTest`; tool paths use the `ZedTest/...` form.
- **Not a git repository** (`git branch` fails, exit 128) — the ACP `git_workflow`
  branch check in `.github/copilot-instructions.md` is skipped. Those project rules
  describe an unrelated ACP-protocol codebase; the dashboard is a standalone deliverable.
- Each terminal call is a fresh shell; use `timeout_ms` for long-running commands.

## If continuing

Nothing outstanding. Natural follow-ups (not started, not requested):
per-host SSH gatherers, real `docker ps` stat parsing, HTTPS service probes,
or a `favicon`/PWA manifest.
