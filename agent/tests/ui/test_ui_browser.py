#!/usr/bin/env python3
"""Browser functional suite (llm-monitor M80-T4) — SIMULATED: a headless browser drives the
dashboard on a free port this process starts and stops. Synthetic data only, nothing real read,
nothing leaves the machine.

Why this exists: test_ui_static.py can prove ids and markup, but it cannot press a button. The
user asked to "verify functionalities, and ensure the save button works" — that needs a real page
with real input events (audit-30 F-30-04).

No third-party packages: the CDP websocket client is hand-rolled from stdlib (socket/base64/struct).
Browser discovery: Edge on this PC, Chrome/Chromium on CI runners. If none is found the suite prints
NOTRUN browser-unavailable and exits 0; run-tests.py reports that as a visible skip.

Geometry checks pin the viewport with Emulation.setDeviceMetricsOverride — the headless default is
only ~800px, which legitimately gives one column. Measured on this build: 1240->3, 980->2, 860->1,
640->1 columns. The 860px case is what pins the max-width:900px rule (auto-fill alone would still
fit two 300px columns there).
"""
import base64
import json
import os
import re
import shutil
import socket
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))  # agent/tests/ui -> repo root
UI = os.path.join(ROOT, "llm-monitor")

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def find_browser():
    for b in BROWSERS:
        if os.path.exists(b):
            return b
    return None


class WS:
    """Minimal CDP websocket client: masked client frames, unmasked server frames."""

    def __init__(self, ws_url):
        # ws://127.0.0.1:PORT/devtools/page/ID
        rest = ws_url.split("://", 1)[1]
        hostport, _, path = rest.partition("/")
        host, _, port = hostport.partition(":")
        self.sock = socket.create_connection((host, int(port)), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET /{path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("websocket handshake closed")
            buf += chunk
        if b"101" not in buf.split(b"\r\n", 1)[0]:
            raise RuntimeError("websocket handshake rejected: " + buf.split(b"\r\n", 1)[0].decode(errors="replace"))
        self.leftover = buf.split(b"\r\n\r\n", 1)[1]
        self.next_id = 0
        self.events = []

    def _send(self, payload):
        data = payload.encode()
        mask = os.urandom(4)
        head = b"\x81"  # FIN + text
        n = len(data)
        if n < 126:
            head += bytes([0x80 | n])
        elif n < (1 << 16):
            head += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", n)
        head += mask
        self.sock.sendall(head + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _recv_frame(self):
        buf = self.leftover
        self.leftover = b""

        def need(k):
            nonlocal buf
            while len(buf) < k:
                chunk = self.sock.recv(65536)
                if not chunk:
                    raise RuntimeError("websocket closed")
                buf += chunk

        need(2)
        b1, b2 = buf[0], buf[1]
        ln = b2 & 0x7F
        off = 2
        if ln == 126:
            need(4)
            ln = struct.unpack(">H", buf[2:4])[0]
            off = 4
        elif ln == 127:
            need(10)
            ln = struct.unpack(">Q", buf[2:10])[0]
            off = 10
        need(off + ln)
        payload = buf[off:off + ln]
        self.leftover = buf[off + ln:]
        # Low nibble is the opcode; the high nibble of b1 holds FIN/RSV bits (0x81 = text).
        return b1 & 0x0F, payload

    def call(self, method, params=None):
        self.next_id += 1
        mid = self.next_id
        self._send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            opcode, payload = self._recv_frame()
            if opcode == 0x8:  # close
                raise RuntimeError("websocket closed by browser")
            if opcode == 0x9:  # ping -> pong
                continue
            msg = json.loads(payload.decode())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            self.events.append(msg)


def js(ws, expression):
    r = ws.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
    if r.get("exceptionDetails"):
        raise RuntimeError("page threw: " + json.dumps(r["exceptionDetails"])[:300])
    return r.get("result", {}).get("value")


# Each grid's own children, in DOM order. Note that '.tiles > .panel' matches BOTH grids
# (.tiles--detail carries .tiles as well) and persistOrder() also records #detail inside the
# tiles list, so any order comparison must read the containers directly (audit-32).
ORDER_SIG = """(() => {
  const t = document.querySelector('.tiles');
  const d = document.querySelector('.tiles--detail');
  if (!t || !d) return null;
  return { tiles: [...t.children].map(e => e.id), detail: [...d.children].map(e => e.id) };
})()"""

# ---------- Settle helpers (M81-T8 / audit-32 a32-02) ----------
# The suite used to read geometry after a fixed time.sleep(), so a slow runner could read the
# page mid-pass and produce a false failure. Every wait below is now an observable:
#   __lastLayout  - stamped by layoutAll() on every masonry pass (app.js)
#   __lastRender  - stamped at the end of refresh(), i.e. "these values are on screen"
# Both are on window (not module scope), so unlike app.js's consts they ARE reachable from
# Runtime.evaluate.

def settle(ws, predicate_expr, what, timeout=10.0):
    """Poll an in-page predicate until it is truthy. Returns the value; raises on timeout."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = js(ws, predicate_expr)
        if last:
            return last
        time.sleep(0.15)
    raise AssertionError(f"settle timed out after {timeout}s: {what} (last value {last!r})")


def mark_layout(ws):
    """Stamp of the most recent masonry pass, for settle_spans(since=...)."""
    return js(ws, "window.__lastLayout || 0")


def settle_render(ws, since, what="after the change", timeout=20.0):
    """Wait for a poll to finish rendering (values on screen) later than `since`.
    REFRESH_MS is 5 s, so the default timeout covers at least one full poll interval."""
    return settle(ws, "(window.__lastRender || 0) > %d" % int(since),
                  f"no render after {what}", timeout)


def settle_usage(ws, timeout=45.0):
    """Wait for the usage ledger fetch to land. It runs at init and every 60 s, and its text is
    longer than the '--' it replaces, so the Usage tile grows when it arrives. The server may
    take several seconds to answer while it catches the ledger up, hence the generous timeout.
    """
    return settle(ws, "(window.__lastUsage || 0) > 0", "the usage ledger fetch", timeout)


def settle_chart(ws, since, what="after the chart control", timeout=20.0):
    """Wait for a /api/timeseries fetch AND its render later than `since`.

    The timeseries fetch is throttled to one request per 15 s while the 15m/1h tabs are
    active, so waiting only for __lastChartRender could be satisfied by the next /api/stats
    re-render of the OLD data. This waits for the fetch itself and then for a render that
    follows it, which is what makes a seeded DB row provably reach the chart.
    """
    settle(ws, "(window.__lastChartFetch || 0) > %d" % int(since),
           f"no timeseries fetch after {what}", timeout)
    return settle(ws, "(window.__lastChartRender || 0) > %d" % int(since),
                  f"no chart render after {what}", timeout)


SPANS_SIG = """(() => {
  const out = [];
  for (const sel of ['.tiles', '.tiles--detail']) {
    const t = document.querySelector(sel);
    if (!t) continue;
    const cs = getComputedStyle(t);
    const unit = parseFloat(cs.gridAutoRows) || 4;
    const gap = parseFloat(cs.columnGap) || 0;
    for (const el of t.children) {
      // Height is part of the signature: a span can stay the same while the tile grows past it.
      const h = Math.round(el.getBoundingClientRect().height);
      out.push(el.id + ':' + getComputedStyle(el).gridRowEnd + ':' + h);
      // And whether that span still brackets that height. Two identical reads of the raw values
      // only prove the page stopped working; a STALE span (written for a height the tile no longer
      // has) is perfectly stable, so without this flag a settle can confirm a broken layout.
      // The drag preview slot is spanned to the dragged panel's height by placeSlot, not to its
      // own box, so it would read stale by construction. It only exists during a drag, and no
      // settle runs then — skipping it keeps that from becoming a hang if one ever does.
      if (el.classList.contains('drop-slot')) continue;
      const cs2 = getComputedStyle(el);
      const m = /span (\\d+)/.exec(cs2.gridRowEnd);
      // A tile with height left at gridRowEnd:auto is just as broken as a span that is too big:
      // it overlaps its neighbours instead of leaving a gap. Both must keep the settle waiting.
      const stale = !!h && (!m || parseInt(m[1], 10) * unit > h + gap + unit * 2);
      out.push(el.id + (stale ? ':STALE' : ''));
    }
  }
  return out.join('|');
})()"""


def settle_spans(ws, since=None, what="after the change", timeout=10.0):
    """Wait for two consecutive identical reads of every tile's span+height.

    When `since` is given, also require a masonry pass newer than it AND newer than every
    content stamp (__lastUsage / __lastRender). The content-stamp condition is what caught a
    real flake on 2026-10-27: the usage ledger fetch rewrites the Usage panel's text after
    load, growing it, so a pass that merely post-dates a viewport change can still be stale
    relative to content that lands later. Requiring __lastLayout >= max(__lastUsage,
    __lastRender) means the spans cover every known mutation; the double read catches
    anything that moves afterwards.

    A stable read is NOT the same as a correct one. M81-review-015 round 3 (A9) saw
    requests-collapsible fail with span=123 on an 83px panel: 123 is ceil((480 + 12) / 4), the
    span for the panel while the fold was still OPEN, and both settle reads landed inside the
    window before the ResizeObserver pass that re-spans (measured at ~100 ms after the click,
    agent/scratch-m81-rv3/flake.py). So a signature containing a STALE marker keeps settling
    instead of returning, and a genuinely stuck layout times out with a message that names it.
    """
    if since is not None:
        cond = ("(window.__lastLayout || 0) > %d"
                " && window.__lastLayout >= Math.max(window.__lastUsage || 0, window.__lastRender || 0)"
                % int(since))
        settle(ws, cond, f"no masonry pass covering all content changes {what}", timeout)
    else:
        settle(ws, "window.__lastLayout >= Math.max(window.__lastUsage || 0, window.__lastRender || 0)",
               f"no masonry pass covering all content changes {what}", timeout)
    deadline = time.time() + timeout
    prev = js(ws, SPANS_SIG)
    while time.time() < deadline:
        cur = js(ws, SPANS_SIG)
        if cur == prev and ":STALE" not in cur:
            return cur
        prev = cur
        time.sleep(0.15)
    last = js(ws, SPANS_SIG)
    stale = [p for p in last.split("|") if p.endswith(":STALE")]
    raise AssertionError(
        f"row spans never agreed within {timeout}s {what}"
        + (f"; span no longer brackets the tile height: {stale}" if stale else "")
    )


def main():
    browser = find_browser()
    if not browser:
        print("NOTRUN browser-unavailable")
        return 0

    profile = tempfile.mkdtemp(prefix="m80-browser-")
    dbg = free_port()
    srv = free_port()
    proc = None
    server = None
    ws = None
    try:
        server = subprocess.Popen(
            [sys.executable, os.path.join(UI, "server.py"), str(srv)],
            cwd=UI, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            # audit-33 a33-34: this is the production server, and without an override every
            # /api/stats the page requests appends a poll row to the real telemetry.sqlite3.
            env=dict(os.environ, LLM_MONITOR_DB=os.path.join(profile, "telemetry-test.sqlite3")),
        )
        base = f"http://127.0.0.1:{srv}"
        up = False
        for _ in range(40):
            try:
                urllib.request.urlopen(base + "/", timeout=1)
                up = True
                break
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.25)
        assert up, "server did not come up"

        for flag in ("--headless=new", "--headless"):
            proc = subprocess.Popen(
                [browser, flag, f"--remote-debugging-port={dbg}", f"--user-data-dir={profile}",
                 "--no-first-run", "--disable-gpu", "--no-sandbox", "about:blank"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            target = None
            for _ in range(60):
                try:
                    data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{dbg}/json/list", timeout=1).read())
                    page = next((t for t in data if t.get("type") == "page"), None)
                    if page:
                        target = page["webSocketDebuggerUrl"]
                        break
                except (urllib.error.URLError, ConnectionError, StopIteration, OSError):
                    time.sleep(0.25)
            if target:
                ws = WS(target)
                break
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            proc = None
        assert ws, "no CDP page target from either headless flag"

        ws.call("Runtime.enable")
        ws.call("Page.enable")
        ws.call("Page.navigate", {"url": base + "/"})
        ready = ""
        for _ in range(60):
            ready = js(ws, "document.readyState")
            if ready == "complete":
                break
            time.sleep(0.25)
        assert ready == "complete", f"page never reached complete (got {ready!r})"
        # Wait for the first poll to have rendered rather than guessing a wall-clock interval
        # (a32-02), and collect any thrown errors while it does.
        settle_render(ws, 0, "the first poll after load")

        # 1. page-clean — no uncaught exceptions during load and first renders.
        errs = [e["params"].get("exceptionDetails", {}) for e in ws.events if e.get("method") == "Runtime.exceptionThrown"]
        assert not errs, "page threw: " + json.dumps(errs[0])[:400]
        print("PASS page-clean")

        # Pin a known viewport so geometry assertions are deterministic.
        ws.call("Emulation.setDeviceMetricsOverride", {"width": 1240, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        # The ledger fetch rewrites the Usage tile; settle it before any geometry read so no
        # span is measured against a tile that is about to grow (the a32-02 flake class).
        settle_usage(ws)
        stamp = mark_layout(ws)
        js(ws, "window.dispatchEvent(new Event('resize'))")
        settle_spans(ws, stamp, "after pinning the viewport to 1240px")

        # 2. masonry-spans — every tile has a JS-computed span tall enough for it and no
        #    slack in it, and the container is no taller than wide rows + tallest column.
        geo = js(ws, """(() => {
          const t = document.querySelector('.tiles'); if (!t) return null;
          const cs = getComputedStyle(t);
          const unit = parseFloat(cs.gridAutoRows) || 4;
          const gap = parseFloat(cs.columnGap) || 0;
          const cols = (cs.gridTemplateColumns.split(/\\s+/).filter(x => x && x !== 'none')).length || 1;
          let bad = [], loose = [], wideH = 0;
          const colSum = {};
          for (const el of t.children) {
            if (!el.classList.contains('panel')) continue;
            const r = el.getBoundingClientRect();
            const h = r.height;
            if (!h) continue;
            const m = /span\\s+(\\d+)/.exec(getComputedStyle(el).gridRowEnd);
            if (!m || parseInt(m[1], 10) * unit < h - 1) bad.push(el.id + ':' + (m ? m[1] : 'none'));
            else if (parseInt(m[1], 10) * unit > h + gap + unit * 2) loose.push(el.id + ':' + Math.round(parseInt(m[1], 10) * unit - h));
            if (r.width > t.clientWidth - 2) { wideH += h + gap; continue; }
            const k = Math.round(r.left);
            colSum[k] = (colSum[k] || 0) + h + gap;
          }
          const vals = Object.values(colSum).sort((a, b) => a - b);
          return {bad, loose, wideH, cols, colSum: vals, rows: t.getBoundingClientRect().height, unit, gap};
        })()""")
        assert geo, "no .tiles container"
        assert not geo["bad"], f"tiles without a sufficient row span: {geo['bad'][:6]}"
        # A span may not be much taller than the tile itself: extra rows are blank space.
        assert not geo["loose"], f"tiles with slack in their row span: {geo['loose'][:6]}"
        assert geo["cols"] >= 3, f"expected >=3 columns at 1240px, got {geo['cols']}"
        assert len(geo["colSum"]) >= 3, f"expected >=3 populated tile columns, got {geo['colSum']}"
        # Full-width rows split the tiles above/below them into separate column segments, so
        # the container is at best wide rows + (tallest column, plus a little per segment).
        # Anything much beyond that is blank space — exactly the bug masonry is here to remove.
        hi = geo["colSum"][-1]
        expect_h = geo["wideH"] + hi * 1.15 + 24
        assert geo["rows"] <= expect_h, (
            f"blank space in grid: rows={geo['rows']:.0f} "
            f"wide={geo['wideH']:.0f} tallest_col={hi:.0f} cols={[round(v) for v in geo['colSum']]}"
        )
        print("PASS masonry-spans")

        # 3. wide-full-width — requests/charts/history and the Detail region span the grid.
        widths = js(ws, """(() => {
          const t = document.querySelector('.tiles'); const w = t.clientWidth;
          const out = {};
          // Only #detail is a <details>; setting .open on a <section> is a no-op property,
          // so open the real one explicitly (audit-32 F-32-08).
          const d = document.getElementById('detail');
          if (d) d.open = true;
          for (const id of ['requests','charts','history','detail']) {
            const el = document.getElementById(id);
            if (!el) { out[id] = 'missing'; continue; }
            const r = el.getBoundingClientRect();
            out[id] = Math.abs(r.width - w) <= 2 ? 'full' : r.width + '/' + w;
          }
          return out;
        })()""")
        badw = {k: v for k, v in widths.items() if v != "full"}
        assert not badw, f"not full width: {badw}"
        print("PASS wide-full-width")

        # 4. columns-adapt — the number of tile columns follows the viewport width.
        def col_count():
            return js(ws, """(() => {
              const t = document.querySelector('.tiles'); const w = t.clientWidth;
              const cs = getComputedStyle(t);
              const tmpl = (cs.gridTemplateColumns.split(/\\s+/).filter(x => x && x !== 'none')).length || 1;
              const xs = new Set();
              let tiles = 0;
              for (const el of t.children) {
                if (!el.classList.contains('panel')) continue;
                const r = el.getBoundingClientRect();
                if (!r.height) continue;
                tiles++;
                if (r.width > w - 2) continue; // full-width tile
                xs.add(Math.round(r.left));
              }
              // Every tile spans the grid => a single-column layout (the narrow breakpoint).
              return xs.size || (tiles ? Math.min(tmpl, tiles) : 0);
            })()""")

        def set_viewport(w):
            # The resize listener calls queueLayout, so the pass that follows a viewport change
            # is observable: wait for a newer __lastLayout, then for the spans to stop moving.
            stamp = mark_layout(ws)
            ws.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False})
            js(ws, "window.dispatchEvent(new Event('resize'))")
            settle_spans(ws, stamp, f"after setting the viewport to {w}px")

        set_viewport(1240)
        wide_n = col_count()
        set_viewport(980)
        mid_n = col_count()
        # 860 is inside the max-width:900px breakpoint but wide enough that auto-fill alone
        # would still fit two 300px columns — so this is what pins the breakpoint rule.
        set_viewport(860)
        bp_n = col_count()
        set_viewport(640)
        narrow_n = col_count()
        stamp = mark_layout(ws)
        ws.call("Emulation.clearDeviceMetricsOverride")
        settle_spans(ws, stamp, "after clearing the viewport override")
        assert wide_n >= 3, f"expected >=3 columns at 1240px, got {wide_n}"
        assert mid_n == 2, f"expected 2 columns at 980px, got {mid_n}"
        assert bp_n == 1, f"expected the max-width:900px rule to force 1 column at 860px, got {bp_n}"
        assert narrow_n == 1, f"expected 1 column at 640px, got {narrow_n}"
        print("PASS columns-adapt")

        # 5. save-button — the user's explicit ask: pressing Save writes the order.
        # The footer is far below the viewport, so scroll it into view before measuring a
        # click point; Input.dispatchMouseEvent uses viewport coordinates.
        def click_id(eid):
            box = js(ws, """(() => { const b = document.getElementById('%s');
              if (!b) return null;
              b.scrollIntoView({block: 'center'});
              const r = b.getBoundingClientRect();
              return {x: r.left + r.width/2, y: r.top + r.height/2}; })()""" % eid)
            assert box, f"no #{eid} button"
            for et, cc in (("mousePressed", 1), ("mouseReleased", 1)):
                ws.call("Input.dispatchMouseEvent", {"type": et, "x": box["x"], "y": box["y"], "button": "left", "clickCount": cc})
            # No fixed wait here: every caller settles on the observable its click is supposed to
            # produce (localStorage, data-view, a new layout pass), so a sleep in the helper would
            # just hide a missing effect instead of failing on one.

        click_id("layout-save")
        settle(ws, "localStorage.getItem('llm-monitor-order')", "the Save button writing the order")
        saved = js(ws, "localStorage.getItem('llm-monitor-order')")
        assert saved, "Save layout wrote nothing to localStorage"
        order = json.loads(saved)
        dom = js(ws, ORDER_SIG)
        assert dom, "containers unavailable"
        # Note: #detail is itself a child of .tiles (it is a grid item), so the tiles list
        # legitimately contains it; comparing container children keeps that honest.
        for key in ("tiles", "detail"):
            assert sorted(order.get(key, [])) == sorted(dom[key]), (
                f"saved {key} != DOM {key}: saved={order.get(key)} dom={dom[key]}"
            )
        print("PASS save-button")

        # 6. reset-button — Reset clears the save and restores DEFAULT_ORDER (live first).
        click_id("layout-reset")
        assert js(ws, "localStorage.getItem('llm-monitor-order')") is None, "Reset left a saved order"
        first = js(ws, "document.querySelector('.tiles > .panel').id")
        assert first == "live", f"after Reset the first tile is {first!r}, expected 'live'"
        print("PASS reset-button")

        # 7. drag-persists — trusted mouse input drags a panel by its heading and the new DOM
        #    order is remembered (audit-31 P-04: dispatchMouseEvent, not synthetic events).
        # A taller viewport keeps two whole panels on screen for the press/move/release.
        stamp = mark_layout(ws)
        ws.call("Emulation.setDeviceMetricsOverride", {"width": 1240, "height": 1400, "deviceScaleFactor": 1, "mobile": False})
        js(ws, "window.dispatchEvent(new Event('resize'))")
        settle_spans(ws, stamp, "after opening a taller viewport for the drag")
        # Pick two panels that are actually inside the viewport (dispatchMouseEvent uses
        # viewport coords, so an off-screen handle can never receive the press). Drag the
        # later one onto the earlier one's top edge.
        pts = js(ws, """(() => {
          window.scrollTo(0, 0);
          const vh = window.innerHeight;
          const vis = [...document.querySelectorAll('.tiles > .panel')].filter(e => {
            const h = e.querySelector('h2'); if (!h) return false;
            const r = h.getBoundingClientRect();
            return r.top > 0 && r.bottom < vh && r.height > 0;
          });
          if (vis.length < 2) return null;
          const src = vis[1], dst = vis[0];
          const a = src.querySelector('h2').getBoundingClientRect();
          const b = dst.getBoundingClientRect();
          return {src: src.id, x0: a.left + a.width/2, y0: a.top + a.height/2,
                  x1: b.left + b.width/2, y1: b.top + 6};
        })()""")
        assert pts, "no two on-screen panels to drag"
        src = pts["src"]
        before = js(ws, ORDER_SIG)
        # Captured BEFORE the press: the drag persists synchronously on release, so reading the
        # saved order afterwards and comparing it to itself would pass or fail on nothing.
        before_saved = js(ws, "localStorage.getItem('llm-monitor-order')")
        ws.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": pts["x0"], "y": pts["y0"], "button": "left", "clickCount": 1})
        for i in (1, 2, 3):
            mx = pts["x0"] + (pts["x1"] - pts["x0"]) * i / 3
            my = pts["y0"] + (pts["y1"] - pts["y0"]) * i / 3
            ws.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": mx, "y": my, "button": "left"})
            # Input pacing, not a read-after-change wait: the drag handler needs distinct move
            # events, so this interval is part of the input, not part of the observation.
            time.sleep(0.12)
        ws.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": pts["x1"], "y": pts["y1"], "button": "left", "clickCount": 1})
        # The drag handler persists on release, so the observable is a saved order that differs
        # from the pre-drag one — not a delay.
        settle(ws, "(localStorage.getItem('llm-monitor-order') || '') !== %s"
                  % json.dumps(before_saved or ""),
               "the drag committing to localStorage")
        after = js(ws, ORDER_SIG)
        assert before and after, "order signature unavailable"
        assert after["tiles"] != before["tiles"], f"drag did not reorder the tiles: {before['tiles']}"
        assert src in after["tiles"] and src in before["tiles"], f"#{src} vanished from the tile grid"
        assert after["tiles"].index(src) != before["tiles"].index(src), (
            f"drag did not move #{src}: {before['tiles'].index(src)} -> {after['tiles'].index(src)}"
        )
        persisted = js(ws, "localStorage.getItem('llm-monitor-order')")
        assert persisted, "drag committed but nothing was persisted"
        got = json.loads(persisted)
        assert got.get("tiles") == after["tiles"], (
            f"persisted tiles != DOM tiles:\\n  saved={got.get('tiles')}\\n  dom  ={after['tiles']}"
        )
        assert got.get("detail") == after["detail"], (
            f"persisted detail != DOM detail:\\n  saved={got.get('detail')}\\n  dom  ={after['detail']}"
        )
        print("PASS drag-persists")

        # 8. detail-packing — the Detail region packs in its own columns with tight spans.
        #    audit-30 F-30-01 / carryover a30-01: it used to be crammed into one narrow stack,
        #    which wide-full-width (a width check) could not detect.
        # The drag above reordered tiles, so wait for the spans to settle before reading them.
        settle_spans(ws, None, "after the drag re-ordered the tiles")
        dgeo = js(ws, """(() => {
          const t = document.querySelector('.tiles--detail'); if (!t) return null;
          const cs = getComputedStyle(t);
          const unit = parseFloat(cs.gridAutoRows) || 4;
          const gap = parseFloat(cs.columnGap) || 0;
          const tmpl = (cs.gridTemplateColumns.split(/\\s+/).filter(x => x && x !== 'none')).length || 1;
          let bad = [], loose = [], tiles = 0;
          const xs = new Set();
          for (const el of t.children) {
            if (!el.classList.contains('panel')) continue;
            const r = el.getBoundingClientRect();
            const h = r.height;
            if (!h) continue;            // collapsed (log is hidden="until-found")
            tiles++;
            const m = /span\\s+(\\d+)/.exec(getComputedStyle(el).gridRowEnd);
            if (!m || parseInt(m[1], 10) * unit < h - 1) bad.push(el.id + ':' + (m ? m[1] : 'none'));
            else if (parseInt(m[1], 10) * unit > h + gap + unit * 2) loose.push(el.id + ':' + Math.round(parseInt(m[1], 10) * unit - h));
            xs.add(Math.round(r.left));
          }
          return {bad, loose, tiles, cols: xs.size || Math.min(tmpl, tiles)};
        })()""")
        assert dgeo, "no .tiles--detail container"
        # M81-T6 re-categorised the region: cache and speculative decode are engine readings and
        # moved to the main grid, hardware joined them. Only engine/switch/log remain, and #log is
        # hidden="until-found" (zero height, skipped above), so TWO measurable tiles is correct.
        # audit-34 G-34-01: this assertion had to change in the same commit as the DOM move.
        assert dgeo["tiles"] >= 2, f"expected the Detail region to show its panels, got {dgeo['tiles']}"
        assert not dgeo["bad"], f"Detail tiles without a sufficient row span: {dgeo['bad'][:6]}"
        assert not dgeo["loose"], f"Detail tiles with slack in their row span: {dgeo['loose'][:6]}"
        assert dgeo["cols"] >= 2, (
            f"Detail region packed into {dgeo['cols']} column(s) at 1240px "
            f"(audit-30 F-30-01 / a30-01 regression)"
        )
        print("PASS detail-packing")

        # 9. view-toggle-spans — Full -> Compact -> Full leaves every span correct.
        #    Hiding #view-full zeroes tile heights (audit-32 F-32-05); the spans must be
        #    recomputed when the view is shown again. Tabs are trusted clicks in the sticky header.
        stamp = mark_layout(ws)
        click_id("tab-compact")
        settle(ws, "document.body.getAttribute('data-view') === 'compact'", "the Compact view becoming active")
        assert js(ws, "document.body.getAttribute('data-view')") == "compact", "Compact tab did not switch the view"
        click_id("tab-full")
        settle(ws, "document.body.getAttribute('data-view') === 'full'", "the Full view becoming active")
        assert js(ws, "document.body.getAttribute('data-view')") == "full", "Full tab did not switch the view"
        # switchView() calls queueLayout(), so the re-span after unhiding is observable.
        settle_spans(ws, stamp, "after returning to the Full view")
        vgeo = js(ws, """(() => {
          const t = document.querySelector('.tiles');
          const unit = parseFloat(getComputedStyle(t).gridAutoRows) || 4;
          let bad = [], n = 0;
          for (const el of t.children) {
            if (!el.classList.contains('panel')) continue;
            const h = el.getBoundingClientRect().height;
            if (!h) continue;
            n++;
            const m = /span\\s+(\\d+)/.exec(getComputedStyle(el).gridRowEnd);
            if (!m || parseInt(m[1], 10) * unit < h - 1) bad.push(el.id + ':' + (m ? m[1] : 'auto'));
          }
          return {bad, n};
        })()""")
        assert vgeo["n"] >= 8, f"expected tiles to be laid out after the view toggle, got {vgeo['n']}"
        assert not vgeo["bad"], f"tiles without a sufficient row span after Full->Compact->Full: {vgeo['bad'][:6]}"
        print("PASS view-toggle-spans")

        # 10. reload-restores-order — the README promise ("remembered between reloads") proven:
        #     the drag from check 7 is still saved, so a fresh load must reproduce that order
        #     in both grids (audit-32 F-32-03).
        saved_before = js(ws, "localStorage.getItem('llm-monitor-order')")
        assert saved_before, "no saved order to reload against"
        expected = json.loads(saved_before)
        # A sentinel on the old window proves we are reading the NEW document: right after
        # Page.navigate the previous document can still report readyState == "complete",
        # which would otherwise let this check compare the pre-reload DOM and pass vacuously.
        js(ws, "window.__m80_pre_reload = 1")
        ws.call("Page.navigate", {"url": base + "/"})
        fresh = False
        for _ in range(60):
            state = js(ws, "({sentinel: window.__m80_pre_reload, ready: document.readyState})")
            if state and state.get("sentinel") is None and state.get("ready") == "complete":
                fresh = True
                break
            time.sleep(0.25)
        assert fresh, "never observed a fresh document after Page.navigate"
        # Wait for this document's first poll to render; the sentinel above already proves the
        # document is new, so __lastRender cannot belong to the pre-reload page.
        settle_render(ws, 0, "the first poll after the reload")
        got = js(ws, ORDER_SIG)
        assert got, "containers missing after reload"
        assert got["tiles"] == expected.get("tiles"), (
            f"reload did not apply the saved tiles order:\\n  saved={expected.get('tiles')}\\n  dom  ={got['tiles']}"
        )
        assert got["detail"] == expected.get("detail"), (
            f"reload did not apply the saved detail order:\\n  saved={expected.get('detail')}\\n  dom  ={got['detail']}"
        )
        print("PASS reload-restores-order")

        # 11. null-gauge-not-zero — audit-33 a33-02: setGauge used to coerce a missing reading
        #     to 0, so the GPU Temp row showed a definite "0%" on a driver that exposes no
        #     temperature counter at all. A null must render as "--" with an empty (indeterminate)
        #     meter, never as a number.
        #     The fixture is injected in the page (addScriptToEvaluateOnNewDocument runs before
        #     app.js), so the check does not depend on what the live engine happens to report.
        #     The identifier is kept so check 25 can remove this script before navigating to the
        #     fixture-backed server: an injected fetch wrapper survives navigation and would
        #     otherwise rewrite the fixture's answers.
        null_script = ws.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
          (() => {
            // The flag is runtime-flippable so one document can show both states: a null poll
            // followed by a measured one. That is what makes gauge-clears-on-real-reading failable.
            window.__m81_null = true;
            const real = window.fetch;
            window.fetch = (u, o) => real(u, o).then((res) => {
              // Decide BEFORE consuming the body: returning a plain object here would break the
              // app's res.json() and no poll would render at all.
              if (!String(u).includes('api/stats') || !window.__m81_null) return res;
              return res.json().then((j) => {
                if (j.gpu) j.gpu.temp_c = null;
                if (j.hardware) j.hardware.cpu_pct = null;
                // M81-review-015 round 3 (A7): req_per_min is None whenever the window's span is
                // under one sampling period, which the live DB does produce. Force that state so
                // the "rate n/a" branch is driven by data rather than only grepped in the source.
                if (j.analysis && j.analysis.recent) {
                  j.analysis.recent.req_per_min = null;
                  j.analysis.recent.requests = 12;
                }
                // audit-33 a33-36: the HUD multiplied an already-percentage value by 100.
                // Pin it so the check catches a re-scaling in either place.
                if (j.context) { j.context.pct = 74.16954; j.context.used = 194431; j.context.max = 262144; }
                return new Response(JSON.stringify(j), {headers: {'content-type': 'application/json'}});
              });
            });
          })();"""})
        js(ws, "window.__m81_pre_reload = 1")
        ws.call("Page.navigate", {"url": base + "/"})
        fresh2 = False
        for _ in range(60):
            state = js(ws, "({sentinel: window.__m81_pre_reload, ready: document.readyState})")
            if state and state.get("sentinel") is None and state.get("ready") == "complete":
                fresh2 = True
                break
            time.sleep(0.25)
        assert fresh2, "never observed a fresh document after installing the null fixture"
        # Wait for an actual render rather than a wall-clock guess: the app marks each poll.
        rendered = False
        gauges = None
        for _ in range(40):
            gauges = js(ws, """(() => {
              const t = document.getElementById('gpu-temp');
              const m = document.getElementById('gpu-temp-gauge');
              const c = document.getElementById('hw-cpu');
              const cm = document.getElementById('hw-cpu-gauge');
              const hc = document.getElementById('hud-ctx-pct');
              const hv = document.getElementById('hud-ctx-val');
              if (!t || !m) return null;
              // Proves the striped "no data" track is applied, not just the class name.
              // Asserted on the ELEMENT because Chrome's getComputedStyle reports 'none' for a
              // meter pseudo-element's own background, so the ::-webkit-meter-bar rule (the one
              // Chrome paints) is not observable this way. That makes this assertion a guard for
              // the bar rule and a proof for the element rule — recorded as such in task-81-t8.
              let stripe = '';
              try { stripe = getComputedStyle(m).backgroundImage || ''; } catch (e) {}
              return {temp: t.textContent, tempVal: m.getAttribute('value'),
                      cls: m.getAttribute('class') || '', stripe,
                      cpu: c ? c.textContent : null, cpuVal: cm ? cm.getAttribute('value') : null,
                      hudCtx: hc ? hc.textContent : null, hudCtxVal: hv ? hv.textContent : null,
                      reqs: (() => { const e = document.getElementById('an-requests'); return e ? e.textContent : null; })()};
            })()""")
            # The element ships as "--", so a single match is not proof the fixture landed:
            # require the meter to be indeterminate, which only the null path can produce.
            if gauges and gauges["temp"] == "--" and gauges["tempVal"] in ("", None):
                rendered = True
                break
            time.sleep(0.25)
        assert gauges, "#gpu-temp / #gpu-temp-gauge missing"
        assert rendered, f"the null fixture never reached the Temp row, it reads {gauges['temp']!r}"
        assert gauges["tempVal"] in ("", None), (
            f"a null reading sized the meter to {gauges['tempVal']!r}; an empty value is the "
            f"indeterminate state (audit-33 a33-02)"
        )
        assert "is-none" in gauges["cls"], (
            f"the null meter lacks the is-none class (class={gauges['cls']!r})"
        )
        # An empty <meter> value falls back to the minimum per HTML, so without the striped track
        # a null reading still paints as an empty bar — visually identical to a real 0.
        assert "linear-gradient" in gauges["stripe"], (
            f"the striped no-data track is not applied to the meter (backgroundImage="
            f"{gauges['stripe'][:60]!r})"
        )
        if gauges["cpu"] is not None:
            assert gauges["cpu"] == "--" and gauges["cpuVal"] in ("", None), (
                f"null cpu_pct rendered as {gauges['cpu']!r}/{gauges['cpuVal']!r}"
            )
        print("PASS null-gauge-not-zero")

        # 11b. rate-na-on-short-span (M81-review-015 round 3, A7) — the static check only grepped
        #      for the string "rate n/a", which a comment would satisfy. This drives the actual
        #      state (a real request count with an uncomputable rate) through the same fixture and
        #      requires the row to state both: the count stays, the rate is marked absent.
        assert gauges["reqs"] == "12 \u00b7 rate n/a", (
            f"#an-requests reads {gauges['reqs']!r} for requests=12 with req_per_min null; it must "
            f"keep the count and mark the rate n/a (never '12 \u00b7 null/min' or a bare '12')"
        )
        print("PASS rate-na-on-short-span")

        # 12. hud-context-scale — audit-33 a33-36: context.pct is already a percentage, so the
        #     HUD's extra *100 rendered 7417.0% for a real 74.2%, and the token rows read keys
        #     the payload never sends so they were always "--".
        assert gauges["hudCtx"] == "74.2%", (
            f"HUD context reads {gauges['hudCtx']!r}, expected '74.2%' for a pinned pct of "
            f"74.16954 (audit-33 a33-36 double scaling)"
        )
        assert gauges["hudCtxVal"] == "194,431" or gauges["hudCtxVal"] == "194431", (
            f"HUD context tokens reads {gauges['hudCtxVal']!r}; the payload sends used/max, "
            f"not used_tokens/max_tokens"
        )
        print("PASS hud-context-scale")

        # 13. gauge-clears-on-real-reading — the is-none track must toggle back off in the SAME
        #     document. A gauge that stayed striped after one null poll would hide every later
        #     measurement, and a check that reloaded instead would pass vacuously (a fresh
        #     document never had the class added).
        striped = js(ws, """(() => {
          const cm = document.getElementById('hw-cpu-gauge');
          return cm ? (cm.getAttribute('class') || '') : null;
        })()""")
        assert striped is not None and "is-none" in striped, (
            f"precondition: the CPU gauge should still be striped from the null poll (class={striped!r})"
        )
        js(ws, "window.__m81_null = false")   # next poll carries the engine's real cpu_pct
        live = None
        for _ in range(40):
            live = js(ws, """(() => {
              const cm = document.getElementById('hw-cpu-gauge');
              const c = document.getElementById('hw-cpu');
              if (!cm || !c) return null;
              return {val: cm.getAttribute('value'), cls: cm.getAttribute('class') || '', text: c.textContent};
            })()""")
            if live and live["val"] not in ("", None) and live["text"] != "--":
                break
            time.sleep(0.25)
        assert live and live["val"] not in ("", None), (
            f"no live CPU reading reached the gauge after un-pinning the fixture ({live!r})"
        )
        assert "is-none" not in live["cls"], (
            f"the no-data track stayed on a measured value (class={live['cls']!r}, value={live['val']!r})"
        )
        print("PASS gauge-clears-on-real-reading")

        # 14. chart-axis-labelled (a33-18) — the y-axis must state its unit, and the unit must
        #     follow the metric tab. With a fresh temp DB every bucket has samples == 0, so the
        #     axis is still drawn while every series is a hole: that makes the label the thing
        #     under test rather than whatever the engine happened to report.
        axis = js(ws, """(() => {
          const g = document.getElementById('chart-grid');
          if (!g) return null;
          const texts = [...g.querySelectorAll('text')].map(t => t.textContent.trim());
          return {texts, title: (document.querySelector('.chart-axis-title') || {}).textContent};
        })()""")
        assert axis and axis["title"], f"no chart axis title was rendered ({axis!r})"
        assert "tokens" in axis["title"], (
            f"the default (all) axis must name its unit, got {axis['title']!r}"
        )
        # Switch the metric tab; the unit must change with it. A metric tab re-renders from the
        # data already in hand (no fetch), so the observable is a newer chart render.
        chart_stamp = js(ws, "window.__lastChartRender || 0")
        js(ws, """(() => {
          const t = document.querySelector('#chart-metric-tabs .chart-tab[data-metric=throughput]');
          if (t) t.click();
        })()""")
        settle(ws, "(window.__lastChartRender || 0) > %d" % int(chart_stamp),
               "the throughput metric tab re-rendering the chart")
        axis2 = js(ws, """(() => {
          const g = document.getElementById('chart-grid');
          if (!g) return null;
          const texts = [...g.querySelectorAll('text')].map(t => t.textContent.trim());
          return {texts, title: (document.querySelector('.chart-axis-title') || {}).textContent};
        })()""")
        assert axis2 and "tok/s" in axis2["title"], (
            f"the throughput axis must read tok/s, got {axis2!r}"
        )
        assert any("tok/s" in t for t in axis2["texts"]), (
            f"no gridline label carries the unit ({axis2['texts'][:8]!r})"
        )
        print("PASS chart-axis-labelled")

        # 15. chart-gap-marked (a33-21) — an unobserved bucket must be marked as a gap, not
        #     drawn as a flat zero. The empty temp DB makes every bucket unobserved, so the
        #     note is deterministic here.
        gaps = js(ws, """(() => {
          const g = document.getElementById('chart-grid');
          if (!g) return null;
          const note = (document.querySelector('.chart-gap-note') || {}).textContent || '';
          return {note, lines: g.querySelectorAll('.chart-gap-line').length,
                  window: (document.getElementById('chart-sum-window') || {}).textContent || ''};
        })()""")
        assert gaps and "no samples" in gaps["note"], (
            f"an all-gap window printed no gap note ({gaps!r})"
        )
        assert gaps["lines"] > 0, f"no gap markers were drawn ({gaps!r})"
        # a33-21: the count must agree between the in-chart note and the summary strip.
        # Both are read from the DOM, so this is not a literal the check can satisfy alone.
        m = re.search(r"(\d+) bucket", gaps["note"])
        assert m and f"{m.group(1)} with no samples" in gaps["window"], (
            f"the gap count differs between the chart note ({gaps['note']!r}) "
            f"and the summary strip ({gaps['window']!r})"
        )
        # a33-20: the summary strip must state the window every number covers.
        assert "buckets of" in gaps["window"], (
            f"the summary strip does not state its window ({gaps['window']!r})"
        )
        print("PASS chart-gap-marked")

        # 16. chart-series-breaks-at-gap (a33-21) — a series must not fall to zero across an
        #     unobserved stretch. Seeding the test DB directly (not the live engine) makes the
        #     pattern deterministic: samples, a ten-minute hole, samples again.
        test_db = os.path.join(profile, "telemetry-test.sqlite3")
        seed = sqlite3.connect(test_db)
        now_ts = time.time()
        cols = ("t", "cpu", "ram", "tok_s", "prefill", "ctx_used", "ctx_pct", "hit_pct",
                "accept_pct", "reqs", "prompt_tokens", "reused", "output_tokens", "power_w",
                "power_src", "gpu_util", "gpu_power", "busy", "vram_used", "vram_total",
                "drafts_offered", "drafts_accepted", "pcie_share", "prompt_ms")
        ph = ",".join("?" * len(cols))

        def seed_row(t, tok):
            return (t, 10.0, 1000.0, tok, 400.0, 1000.0, 10.0, 90.0, 70.0, 10, 20000, 15000,
                    500, 100.0, "modelled", None, None, 1, 8000.0, 24576.0, 50, 35, None, 900.0)

        seeded = []
        for t in range(int(now_ts) - 3300, int(now_ts) - 3000, 20):
            seeded.append(seed_row(t, 40.0))
        # deliberate hole: nothing between -3000 and -1800
        for t in range(int(now_ts) - 1800, int(now_ts) - 1500, 20):
            seeded.append(seed_row(t, 42.0))
        seed.executemany(f"INSERT INTO poll ({', '.join(cols)}) VALUES ({ph})", seeded)
        seed.commit()
        seed.close()

        # The seeded rows must reach the chart through a NEW /api/timeseries fetch, so wait for
        # the fetch and the render that follows it rather than guessing an interval (a32-02).
        fetch_stamp = js(ws, "window.__lastChartFetch || 0")
        js(ws, """(() => {
          document.querySelector('#chart-metric-tabs .chart-tab[data-metric=throughput]').click();
          const b = document.querySelector("#chart-range-btns .chart-range-btn[data-range='1h']");
          if (b) b.click();
        })()""")
        settle_chart(ws, fetch_stamp, "the 1h range button after seeding poll rows")
        lines = js(ws, """(() => {
          const g = document.getElementById('chart-series-lines');
          if (!g) return null;
          return [...g.querySelectorAll('polyline')].map(p => (p.getAttribute('points') || '').trim());
        })()""")
        assert lines, "no chart series lines were rendered after seeding"
        decode = [ln for ln in lines if ln]
        assert len(decode) >= 2, (
            f"the seeded hole did not break the decode series into separate runs ({decode!r})"
        )
        # A dip to zero would put a point on the plot floor (y = pad.top + chartH = 25 + 240).
        bottoms = [ln for ln in decode for pt in ln.split()
                   if abs(float(pt.split(",")[1]) - 265.0) < 0.6]
        assert not bottoms, (
            f"a series point sits on the plot floor, i.e. an unobserved bucket drew zero ({bottoms[:4]!r})"
        )
        print("PASS chart-series-breaks-at-gap")

        # 17. chart-legend-matches-series (a33-22) — the legend must show only series that are
        #     actually drawn, and each non-axis series must state the scale it is drawn to.
        legend = js(ws, """(() => {
          const out = {};
          for (const sel of ['.legend-tok', '.legend-prefill', '.legend-tokens', '.legend-reqs']) {
            const el = document.querySelector('#chart-legend ' + sel);
            if (!el) return null;
            out[sel] = {hidden: el.hidden,
                        peak: ((el.querySelector('.legend-peak') || {}).textContent || '').trim()};
          }
          return out;
        })()""")
        assert legend, "a legend item is missing from index.html"
        # The page is in throughput mode after the previous check.
        assert legend[".legend-tokens"]["hidden"] and legend[".legend-reqs"]["hidden"], (
            f"tokens/requests are not drawn in throughput mode but stay in the legend ({legend!r})"
        )
        assert not legend[".legend-tok"]["hidden"] and not legend[".legend-prefill"]["hidden"], (
            f"a drawn series is hidden from the legend ({legend!r})"
        )
        # The decode line owns the left axis; prefill does not, so it must disclose its own.
        assert "left axis" in legend[".legend-tok"]["peak"], (
            f"the axis-owning series is not labelled as such ({legend['.legend-tok']!r})"
        )
        assert "scaled to peak" in legend[".legend-prefill"]["peak"], (
            f"the privately scaled prefill line states no scale ({legend['.legend-prefill']!r})"
        )
        print("PASS chart-legend-matches-series")

        # 18. chart-no-impossible-prefill (a33-10/a33-19) — a day frozen before the bound holds
        #     an impossible prefill mean that cannot be recomputed (its poll rows are pruned), so
        #     no figure derived from it may reach the panel. Seeded directly into the test DB, so
        #     the value is known exactly and the assertion is one robust text scan rather than
        #     hover geometry. The server-side rule has its own unit tests in tests/telemetry.
        old_day = int(time.time() // 86400) - 5
        seed2 = sqlite3.connect(test_db)
        cols2 = ("t", "cpu", "ram", "tok_s", "prefill", "ctx_used", "ctx_pct", "hit_pct",
                 "accept_pct", "reqs", "prompt_tokens", "reused", "output_tokens", "power_w",
                 "power_src", "gpu_util", "gpu_power", "busy", "vram_used", "vram_total",
                 "drafts_offered", "drafts_accepted", "pcie_share", "prompt_ms")
        ph2 = ",".join("?" * len(cols2))
        seed2.executemany(
            f"INSERT INTO poll ({', '.join(cols2)}) VALUES ({ph2})",
            [(old_day * 86400 + h * 3600, 10.0, 1000.0, 40.0, 400.0, 1000.0, 10.0, 90.0, 70.0,
              10 + h, 20000, 15000, 500, 100.0, "modelled", None, None, 1, 8000.0, 24576.0,
              50, 35, None, 900.0) for h in range(24)])
        # The shape an older build wrote: an unbounded mean, no prefill_max, no bound flag.
        seed2.execute(
            "INSERT OR REPLACE INTO day (d, polls, span_s, reqs, prompt, reused, output,"
            " tok_mean, tok_max, prefill_mean, hit_mean, accept_mean, power_mean, energy_wh,"
            " idle_pct, hours, prefill_max, prefill_bounded)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (old_day, 24, 86400.0, 24, 480000, 360000, 12000, 40.0, 55.0, 9833.65,
             90.0, 70.0, 120.0, 2880.0, 10.0, "[]", None, None))
        seed2.commit()
        seed2.close()

        fetch_stamp2 = js(ws, "window.__lastChartFetch || 0")
        js(ws, """(() => {
          const b = document.querySelector("#chart-range-btns .chart-range-btn[data-range='7d']");
          if (b) b.click();
        })()""")
        settle_chart(ws, fetch_stamp2, "the 7d range button after seeding the old day")
        panel = js(ws, r"""(() => {
          const p = document.getElementById('charts');
          return p ? p.textContent.replace(/\s+/g, ' ') : null;
        })()""")
        assert panel, "the charts panel is missing"
        # 9833.65 rounds to 9834 (0 dp) or 9,834 with separators; catch either form.
        bad = [t for t in ("9833", "9834", "9,833", "9,834") if t in panel]
        assert not bad, (
            f"a pre-bound day's impossible prefill mean reached the panel ({bad!r})"
        )
        print("PASS chart-no-impossible-prefill")

        # 19. history-bars (a33-23) — the History panel used to draw up to 90 daily values into
        #     a 100x30 sparkline with no axis and no ticks. Seeded day rows make the expected
        #     bar count and dates exact, independent of whatever engine is live.
        hist_days = [int(time.time() // 86400) - i for i in range(12, 2, -1)]  # 10 ascending days
        seed3 = sqlite3.connect(test_db)
        seed3.executemany(
            "INSERT OR REPLACE INTO day (d, polls, span_s, reqs, prompt, reused, output,"
            " tok_mean, tok_max, prefill_mean, hit_mean, accept_mean, power_mean, energy_wh,"
            " idle_pct, hours, prefill_max, prefill_bounded)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(d, 100, 86400.0, 10 + i * 5, 100000, 60000, 20000, 30.0 + i, 45.0, 300.0,
              90.0, 70.0, 120.0, 2880.0, 10.0, "[]", 400.0, 0)
             for i, d in enumerate(hist_days)])
        seed3.commit()
        seed3.close()

        # The page polls /api/stats every REFRESH_MS (5 s); wait for the poll whose render is
        # newer than this point rather than reaching for a wall-clock guess (a32-02).
        render_stamp = js(ws, "window.__lastRender || 0")
        settle_render(ws, render_stamp, "the poll that picks up the seeded day rows", timeout=25.0)
        bars = js(ws, """(() => {
          const svg = document.getElementById('hist-bars');
          if (!svg) return null;
          return {
            rects: svg.querySelectorAll('rect.hist-bar').length,
            // M81-review (A6): the bars are cursor:pointer but had no hover affordance, so
            // a value only appeared after a click. Each rect must carry a <title>.
            tips: [...svg.querySelectorAll('rect.hist-bar > title')].map(t => t.textContent.trim()),
            texts: [...svg.querySelectorAll('text')].map(t => t.textContent.trim()),
            caption: (document.getElementById('hist-bars-caption') || {}).textContent || '',
            first: (document.getElementById('hist-scrub-first') || {}).textContent || '',
            last: (document.getElementById('hist-scrub-last') || {}).textContent || '',
            valuetext: (document.getElementById('scrub') || {}).getAttribute('aria-valuetext') || '',
          };
        })()""")
        assert bars, "#hist-bars is missing from the page"
        assert bars["rects"] >= len(hist_days), (
            f"expected >= {len(hist_days)} bars for the seeded days, got {bars['rects']}"
        )
        assert len(bars["tips"]) == bars["rects"], (
            f"{bars['rects']} bars but only {len(bars['tips'])} carry a hover title"
        )
        assert any(re.fullmatch(r"\d{4}-\d\d-\d\d . [\d.]+ req/day", t) for t in bars["tips"]), (
            f"no bar title names its day and value ({bars['tips'][:3]!r})"
        )

        # y-axis unit on BOTH the axis title and the top gridline label, plus >=2 dated x ticks.
        # Selecting by text-anchor keeps the two assertions independent: a check satisfied by
        # either one would pass with the other removed (proven during this task).
        axis = js(ws, """(() => {
          const t = document.querySelector('#hist-bars .chart-axis-title');
          const grid = [...document.querySelectorAll('#hist-bars text')]
            .filter(x => x.getAttribute('text-anchor') === 'end')
            .map(x => x.textContent.trim());
          return {title: t ? t.textContent.trim() : null, grid};
        })()""")
        assert axis["title"] == "req/day", (
            f"the history chart's axis title does not state the unit ({axis!r})"
        )
        assert any(g.endswith("req/day") for g in axis["grid"]), (
            f"no gridline label carries the unit ({axis['grid']!r})"
        )
        dates = [t for t in bars["texts"] if re.fullmatch(r"\d\d-\d\d", t)]
        assert len(dates) >= 2, f"fewer than two dated x ticks ({bars['texts']!r})"
        # a33-23 caption: count, range and peak.
        assert "recorded days" in bars["caption"] and "peak" in bars["caption"], (
            f"the caption states no range/peak ({bars['caption']!r})"
        )
        # a33-24: the track names the day under the marker and the range it spans.
        assert re.fullmatch(r"\d{4}-\d\d-\d\d", bars["first"]), f"no first-day label ({bars!r})"
        assert re.fullmatch(r"\d{4}-\d\d-\d\d", bars["last"]), f"no last-day label ({bars!r})"
        assert re.match(r"^\d{4}-\d\d-\d\d, day \d+ of \d+$", bars["valuetext"]), (
            f"aria-valuetext does not name the selected day ({bars['valuetext']!r})"
        )
        # a33-25: the day/week/month buckets are UTC epoch days while other timestamps on the
        # page render local, so the table must say which alignment its rows use.
        utc = js(ws, """(() => {
          const rows = [...document.querySelectorAll('#history-comparison-tbody tr')]
            .map(tr => (tr.cells[0] ? tr.cells[0].textContent.trim() : ''));
          const note = (document.getElementById('hist-table-note') || {}).textContent || '';
          return {rows, note};
        })()""")
        day_rows = [r for r in utc["rows"] if r.startswith(("Today", "This week", "This month"))]
        assert len(day_rows) == 3, f"expected 3 calendar-period rows, got {utc['rows']!r}"
        assert all("UTC" in r for r in day_rows), (
            f"a calendar-period row does not name its alignment ({day_rows!r})"
        )
        assert "UTC" in utc["note"], f"no note under the table states the alignment ({utc['note']!r})"
        # The per-request row must NOT claim UTC: it compares two individual requests, not
        # calendar periods, so tagging it would be a new kind of wrong label.
        req_rows = [r for r in utc["rows"] if r.startswith("Last request")]
        assert req_rows and not any("UTC" in r for r in req_rows), (
            f"the per-request row is labelled UTC ({req_rows!r})"
        )
        print("PASS history-bars")

        # 20. history-metric-switch (a33-18 applied to the history chart) — switching the metric
        #     must change the axis unit; two units must never share one axis.
        # A history metric tab re-renders from data already in hand, so the observable is the
        # bars group changing, not a fetch.
        js(ws, """(() => {
          const t = document.querySelector('#hist-metric-tabs .chart-tab[data-hmetric=tokens]');
          if (t) t.click();
        })()""")
        settle(ws, "(document.querySelector('#hist-bars .chart-axis-title') || {}).textContent === 'tokens/day'",
               "the tokens/day axis label after the history metric switch")
        bars2 = js(ws, """(() => {
          const svg = document.getElementById('hist-bars');
          if (!svg) return null;
          return {texts: [...svg.querySelectorAll('text')].map(t => t.textContent.trim()),
                  unit: (document.querySelector('#hist-bars .chart-axis-title') || {}).textContent || ''};
        })()""")
        assert bars2 and "tokens/day" in bars2["unit"], (
            f"the tokens axis does not state its own unit ({bars2!r})"
        )
        assert not any("req/day" == t for t in bars2["texts"]), (
            f"the old unit survived the metric switch ({bars2['texts'][:6]!r})"
        )
        print("PASS history-metric-switch")

        # 21. history-scrub-keyboard (a33-24) — the track declares role="slider", which promises
        #     keyboard operation; an unfocusable div with no key handling would be a silent a11y
        #     hole. Arrow keys must move the selection and the aria readout with it.
        kb = js(ws, """(() => {
          const track = document.getElementById('scrub');
          if (!track) return null;
          const before = {now: track.getAttribute('aria-valuenow'),
                          text: track.getAttribute('aria-valuetext'),
                          tabindex: track.getAttribute('tabindex')};
          const key = (k) => track.dispatchEvent(new KeyboardEvent('keydown',
              {key: k, bubbles: true, cancelable: true}));
          key('End');
          const atEnd = track.getAttribute('aria-valuenow');
          key('ArrowLeft');
          const afterLeft = {now: track.getAttribute('aria-valuenow'),
                             text: track.getAttribute('aria-valuetext'),
                             selected: (document.getElementById('hist-selected') || {}).textContent || ''};
          key('Home');
          const atHome = track.getAttribute('aria-valuenow');
          return {before, atEnd, afterLeft, atHome,
                  max: track.getAttribute('aria-valuemax')};
        })()""")
        assert kb and kb["before"]["tabindex"] == "0", (
            f"the slider is not keyboard reachable ({kb!r})"
        )
        assert kb["atEnd"] == kb["max"], f"End did not reach the last day ({kb!r})"
        assert int(kb["afterLeft"]["now"]) == int(kb["max"]) - 1, (
            f"ArrowLeft did not step back one day ({kb!r})"
        )
        assert kb["atHome"] == "0", f"Home did not reach the first day ({kb!r})"
        # The aria readout and the visible readout must both follow the keyboard, and they must
        # agree with each other about which day is selected (both name an ISO date).
        # After End then ArrowLeft the index is max-1, so the readout reads "day max of max+1".
        last = int(kb["max"])
        assert re.match(rf"^\d{{4}}-\d\d-\d\d, day {last} of {last + 1}$",
                        kb["afterLeft"]["text"] or ""), (
            f"aria-valuetext did not follow the keyboard ({kb!r})"
        )
        assert re.match(r"^\d{4}-\d\d-\d\d · ", kb["afterLeft"]["selected"]), (
            f"the visible day readout did not follow the keyboard ({kb['afterLeft']['selected']!r})"
        )
        assert kb["afterLeft"]["text"].split(",")[0] == kb["afterLeft"]["selected"].split(" · ")[0], (
            f"aria and the visible readout name different days ({kb!r})"
        )
        print("PASS history-scrub-keyboard")

        # 22. requests-collapsible (a33-30) — the request table is the tallest block on the page and
        #     is usually read once. It must fold in place, and the masonry pass must re-span after
        #     the fold changes size. Asserted on the panel's own height plus its row span, because a
        #     fold that leaves a full-height hole in the grid is the failure mode this task risks.
        # The before/after snapshots are separate evaluations with a wait between them: the span is
        # written by a ResizeObserver -> requestAnimationFrame pass, so reading it in the same tick
        # as the click would report the stale value (and would pass when the re-span is broken).
        fold0 = js(ws, """(() => {
          const p = document.getElementById('requests');
          if (!p) return null;
          const d = p.querySelector('details.panel__fold');
          const sum = d && d.querySelector('summary');
          const table = p.querySelector('table.request-table');
          return {isSection: p.tagName === 'SECTION' && p.classList.contains('panel'),
                  panelIsDetails: p.tagName === 'DETAILS',
                  hasFold: !!d, open: !!(d && d.open),
                  summary: sum ? sum.textContent.trim() : null,
                  contentShown: !!(d && getComputedStyle(d, '::details-content').contentVisibility === 'visible'),
                  foldH: d.getBoundingClientRect().height,
                  h: p.getBoundingClientRect().height};
        })()""")
        assert fold0, "no #requests panel"
        assert fold0["isSection"], "#requests must stay a <section class=panel> (id + drag contract)"
        assert not fold0["panelIsDetails"], "#requests itself became a <details>, which breaks static check 4"
        assert fold0["hasFold"], "no details.panel__fold inside #requests (a33-30)"
        assert fold0["summary"], f"the fold has no summary text ({fold0['summary']!r})"
        assert fold0["open"] and fold0["contentShown"], (
            f"the Requests fold does not ship open with its contents painted ({fold0!r})"
        )
        fold_stamp = mark_layout(ws)
        js(ws, "(() => { const s = document.querySelector('#requests details.panel__fold summary'); if (s) s.click(); })()")
        # The ResizeObserver re-runs the pass when the fold collapses; waiting for a newer
        # __lastLayout plus stable spans is what makes the height read below deterministic.
        settle_spans(ws, fold_stamp, "after closing the Requests fold")
        fold1 = js(ws, """(() => {
          const p = document.getElementById('requests');
          const d = p && p.querySelector('details.panel__fold');
          const cs = getComputedStyle(document.querySelector('.tiles'));
          const unit = parseFloat(cs.gridAutoRows) || 4;
          const gap = parseFloat(cs.columnGap) || 0;
          const m = /span\\s+(\\d+)/.exec(getComputedStyle(p).gridRowEnd);
          return {open: !!(d && d.open),
                  contentShown: !!(d && getComputedStyle(d, '::details-content').contentVisibility === 'visible'),
                  foldH: d.getBoundingClientRect().height,
                  h: p.getBoundingClientRect().height,
                  span: m ? parseInt(m[1], 10) : null, unit, gap};
        })()""")
        assert not fold1["open"], "clicking the summary did not close the fold"
        # Chrome hides a closed <details> body with content-visibility on the ::details-content
        # pseudo, while the descendants keep their layout boxes — so a table rect is NOT a valid
        # observable here. The fold's own height is: it collapses to just its summary line.
        assert not fold1["contentShown"], (
            f"the fold's contents are still painted while closed ({fold1!r})"
        )
        assert fold0["foldH"] - fold1["foldH"] > 40, (
            f"the fold itself did not collapse: {fold0['foldH']:.0f} -> {fold1['foldH']:.0f}"
        )
        assert fold1["foldH"] < 40, (
            f"the closed fold is {fold1['foldH']:.0f}px tall, more than its summary line"
        )
        shrink = fold0["h"] - fold1["h"]
        assert shrink > 40, (
            f"closing the Requests fold only removed {round(shrink)}px "
            f"({fold0['h']:.0f} -> {fold1['h']:.0f})"
        )
        # The row span must follow the new height: a stale span leaves a full-height blank in the
        # grid, which is exactly the complaint this milestone is about.
        assert fold1["span"] is not None, "#requests lost its row span after the toggle"
        allotted = fold1["span"] * fold1["unit"]
        assert allotted >= fold1["h"] - 1, (
            f"row span too small after the fold closed: {fold1['span']} x {fold1['unit']} < "
            f"{fold1['h']:.0f}"
        )
        # Same tolerance the detail-packing check uses for a stale/oversized span.
        slack = allotted - fold1["h"]
        assert slack <= fold1["gap"] + 2 * fold1["unit"], (
            f"row span left {round(slack)}px of slack below the collapsed Requests panel "
            f"(span={fold1['span']}, height={fold1['h']:.0f})"
        )
        # Re-open so later checks (and the user) see the table as shipped.
        reopen_stamp = mark_layout(ws)
        js(ws, "(() => { const s = document.querySelector('#requests details.panel__fold summary'); if (s) s.click(); })()")
        settle_spans(ws, reopen_stamp, "after re-opening the Requests fold")
        print("PASS requests-collapsible")

        # 23. layout-version-migration (a33-32) — the default arrangement is the point of M81, and a
        #     saved layout from the old arrangement would silently hide it. A save carrying the
        #     current version must be honoured exactly; a stale or version-less save must be replaced
        #     by the new defaults AND announced. Reversed stale order is used deliberately: if the
        #     version gate is removed, the DOM comes out reversed and this fails.
        # app.js is a <script type="module">, so its consts are module-scoped and NOT reachable from
        # Runtime.evaluate. The expected order is therefore read from the shipped source, which is
        # also the stronger assertion: it compares the live DOM against what the file says.
        js_src = open(os.path.join(UI, "app.js"), encoding="utf8").read()
        mm = re.search(r'const ORDER_VERSION = (\d+);', js_src)
        assert mm, "ORDER_VERSION not found in app.js"
        order_version = int(mm.group(1))
        dm = re.search(r'const DEFAULT_ORDER = \{(.*?)\n\};', js_src, re.S)
        assert dm, "DEFAULT_ORDER block not found in app.js"
        want = {}
        for name in ("tiles", "detail"):
            lm = re.search(rf'{name}: \[(.*?)\]', dm.group(1), re.S)
            assert lm, f"DEFAULT_ORDER.{name} missing"
            want[name] = re.findall(r'"([^"]+)"', lm.group(1))
        # #detail is itself a grid item inside .tiles (and persistOrder records it in the tiles
        # list), so the expected tiles order is the 13 panels plus the region at the end.
        expected_tiles = want["tiles"] + ["detail"]
        js(ws, "window.__m81_pre_reset_nav = 1")
        ws.call("Page.navigate", {"url": base + "/?reset=1"})
        fresh3 = False
        for _ in range(60):
            state = js(ws, "({sentinel: window.__m81_pre_reset_nav, ready: document.readyState})")
            if state and state.get("sentinel") is None and state.get("ready") == "complete":
                fresh3 = True
                break
            time.sleep(0.25)
        assert fresh3, "never observed a fresh document after navigating with ?reset=1"
        # Wait for this document's first render; the sentinel proves the document is new, so
        # __lastRender cannot be left over from the previous one.
        settle_render(ws, 0, "the first poll after ?reset=1")
        markup = js(ws, ORDER_SIG)
        # The initial DOM order is the pre-JS fallback; if it drifts from DEFAULT_ORDER, a user with
        # JS disabled or a slow load sees a different dashboard than everyone else.
        assert markup["tiles"] == expected_tiles, (
            f"index.html markup order != DEFAULT_ORDER.tiles:\n  markup={markup['tiles']}\n  js    ={expected_tiles}"
        )
        assert markup["detail"] == want["detail"], (
            f"index.html markup order != DEFAULT_ORDER.detail:\n  markup={markup['detail']}\n  js    ={want['detail']}"
        )
        # Engine performance must lead the first row, not GPU/power (a33-29).
        assert want["tiles"][:5] == ["live", "throughput", "context", "cache", "spec"], (
            f"the default order does not lead with engine performance: {want['tiles'][:6]}"
        )
        stale = {"tiles": list(reversed(want["tiles"])), "detail": list(want["detail"])}
        js(ws, "localStorage.setItem('llm-monitor-order', %s)" % json.dumps(json.dumps(stale)))
        assert json.loads(js(ws, "localStorage.getItem('llm-monitor-order')"))["tiles"][0] == "history", (
            "could not plant a stale (version-less) saved layout"
        )
        js(ws, "window.__m81_pre_migrate = 1")
        ws.call("Page.navigate", {"url": base + "/"})
        fresh4 = False
        for _ in range(60):
            state = js(ws, "({sentinel: window.__m81_pre_migrate, ready: document.readyState})")
            if state and state.get("sentinel") is None and state.get("ready") == "complete":
                fresh4 = True
                break
            time.sleep(0.25)
        assert fresh4, "never observed a fresh document after planting a stale layout"
        settle_render(ws, 0, "the first poll after the migrated load")
        migrated = js(ws, ORDER_SIG)
        assert migrated["tiles"] == expected_tiles, (
            f"a stale saved layout was honoured instead of the new defaults:\n  "
            f"stale={stale['tiles']}\n  dom ={migrated['tiles']}"
        )
        note = js(ws, """(() => { const n = document.getElementById('layout-note');
          return n ? {hidden: n.hidden, text: (document.getElementById('layout-note-text') || {}).textContent || ''} : null; })()""")
        assert note and not note["hidden"], (
            f"the replaced layout was not announced (#layout-note = {note!r}) — a silent change "
            f"to someone's saved arrangement is the failure a33-32 warns about"
        )
        assert re.search(r"layout", note["text"], re.I), f"the note says nothing about layout: {note['text']!r}"
        repersisted = json.loads(js(ws, "localStorage.getItem('llm-monitor-order')"))
        assert repersisted.get("v") == order_version, (
            f"the migrated layout was not re-saved at the current version ({repersisted.get('v')!r})"
        )
        assert repersisted.get("tiles") == expected_tiles, (
            f"re-saved tiles != defaults:\n  saved={repersisted.get('tiles')}\n  want ={expected_tiles}"
        )
        # The note must be dismissible and Reset must clear it (it points the user at that button).
        click_id("layout-note-close")
        assert js(ws, "document.getElementById('layout-note').hidden") is True, (
            "Dismiss did not hide the layout note"
        )
        print("PASS layout-version-migration")

        # 24. header-liveness (a33-27/28) — the header said nothing about how long the engine has
        #     been up, how old the numbers on screen are, or which build is answering, and the gauge
        #     scale was a hardcoded 2000 tok/s this engine never approaches. Everything is pinned by
        #     a fixture so the check tests the render path instead of whatever the live engine
        #     happens to report at the moment the suite runs.
        head_script = ws.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
          (() => {
            window.__m81_bad_since = false;
            const real = window.fetch;
            window.fetch = (u, o) => real(u, o).then((res) => {
              if (!String(u).includes('api/stats')) return res;
              return res.json().then((j) => {
                // 3h 12m of engine uptime, or an unparseable stamp for the second half of the
                // check: an unparseable `since` must print "--", never a bogus duration.
                if (j.totals) j.totals.since = window.__m81_bad_since
                  ? 'not a timestamp' : (Date.now() / 1000 - 11520);
                if (j.engine) j.engine.build_info = 'Strata 9.9.99-test';
                // A prefill series whose interpolated p95 is 1,032.5 tok/s. The gauge scale
                // must follow it (1.25x = 1,291), which the old hardcoded 2000 could never
                // produce and the old off-by-one index (p91 -> 1,250) does not match either.
                if (j.history) j.history.prefill = [120, 300, 450, 640, 800, 900, 1000, 1050];
                if (j.throughput) j.throughput.prefill = 345;
                return new Response(JSON.stringify(j), {headers: {'content-type': 'application/json'}});
              });
            });
          })();"""})
        js(ws, "window.__m81_pre_liveness = 1")
        ws.call("Page.navigate", {"url": base + "/?liveness=1"})
        fresh5 = False
        for _ in range(60):
            state = js(ws, "({sentinel: window.__m81_pre_liveness, ready: document.readyState})")
            if state and state.get("sentinel") is None and state.get("ready") == "complete":
                fresh5 = True
                break
            time.sleep(0.25)
        assert fresh5, "never observed a fresh document after installing the liveness fixture"
        head = None
        for _ in range(40):
            head = js(ws, """(() => {
              const up = document.getElementById('top-uptime');
              const age = document.getElementById('top-age');
              const scale = document.getElementById('top-gauge-ceiling');
              const g = document.getElementById('top-gauge');
              const fill = document.getElementById('top-gauge-fill');
              if (!up || !age || !scale || !g) return null;
              return {up: up.textContent, age: age.textContent, scale: scale.textContent,
                      aria: g.getAttribute('aria-label') || '', now: g.getAttribute('aria-valuenow'),
                      w: fill ? fill.style.width : null,
                      build: (document.getElementById('top-build') || {}).textContent};
            })()""")
            if head and head["up"] != "--":
                break
            time.sleep(0.25)
        assert head, "a header liveness element is missing (#top-uptime/#top-age/#top-gauge-scale)"
        assert re.fullmatch(r"3h 1[12]m", head["up"]), (
            f"engine uptime reads {head['up']!r} for a session that started 3h 12m ago"
        )
        # The age must be seconds-to-minutes old, not the same order as the uptime: an element that
        # was never written stays "--", and one fed the wrong stamp reads like an uptime.
        age = re.fullmatch(r"(\d+)(s|m)", head["age"] or "")
        assert age, f"last-poll age reads {head['age']!r}; expected a few seconds"
        assert (int(age.group(1)) * (60 if age.group(2) == "m" else 1)) < 120, (
            f"the last-poll age is {head['age']!r}, too old to be the current poll"
        )
        assert head["build"] == "Strata 9.9.99-test", (
            f"the header build string reads {head['build']!r}"
        )
        assert re.search(r"gauge to 1,?291", head["scale"] or ""), (
            f"the gauge scale is not derived from the series ({head['scale']!r}); it must follow "
            f"the interpolated p95 of the fixture series (1,032.5 tok/s), not a hardcoded constant"
        )
        assert "2,000" not in (head["scale"] or "") and "2000" not in (head["scale"] or ""), (
            f"the gauge still prints the old hardcoded 2000 tok/s ceiling ({head['scale']!r})"
        )
        assert "1,291" in head["aria"] and "345" in head["aria"], (
            f"the gauge's accessible label does not name the reading and its scale: {head['aria']!r}"
        )
        # 345 of a 1,291 ceiling is ~27% — visible movement, where the old scale pinned it at 17%.
        assert head["w"] and abs(float(head["w"].rstrip("%")) - 26.7) < 1.0, (
            f"the gauge fill is {head['w']!r} for 345 tok/s against a 1,291 ceiling"
        )
        # An unparseable `since` must degrade to "--", never to a NaN duration.
        js(ws, "window.__m81_bad_since = true")
        honest = None
        for _ in range(40):
            honest = js(ws, "(document.getElementById('top-uptime') || {}).textContent")
            if honest == "--":
                break
            time.sleep(0.25)
        assert honest == "--", (
            f"an unparseable totals.since printed {honest!r}; it must print '--'"
        )
        print("PASS header-liveness")

        # Both injected fetch wrappers are removed here: they survive navigation, and check 25
        # needs the server's own answers, not page-level rewrites of them.
        for script in (null_script, head_script):
            ident = (script or {}).get("identifier")
            if ident:
                ws.call("Page.removeScriptToEvaluateOnNewDocument", {"identifier": ident})

        # 25. fixture-engine-values (a33-35) — every check above either asserts structure or pins
        #     values by rewriting the response inside the page. Neither can prove that server.py
        #     turns a KNOWN engine answer into a KNOWN payload field, because both still depend on
        #     whatever engine happens to own :8080 when the suite runs (and on CI, none does).
        #     This starts a second copy of the real server with LLM_MONITOR_FIXTURE pointed at
        #     agent/tests/ui/fixtures/engine.json, whose gpu_* counters carry values the live AMD
        #     HIP driver never supplies — so the GPU panel's measured path becomes testable, and
        #     every number below is one only the fixture can produce.
        fx_port = free_port()
        fx_db = os.path.join(profile, "telemetry-fixture.sqlite3")
        fx_server = subprocess.Popen(
            [sys.executable, os.path.join(UI, "server.py"), str(fx_port)],
            cwd=UI, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=dict(os.environ,
                     LLM_MONITOR_DB=os.path.join(profile, "telemetry-fixture-poll.sqlite3"),
                     LLM_MONITOR_FIXTURE=os.path.join(HERE, "fixtures", "engine.json")),
        )
        try:
            fx_base = f"http://127.0.0.1:{fx_port}"
            fx_up = False
            for _ in range(40):
                try:
                    urllib.request.urlopen(fx_base + "/", timeout=1)
                    fx_up = True
                    break
                except (urllib.error.URLError, ConnectionError, OSError):
                    time.sleep(0.25)
            assert fx_up, "the fixture-backed server did not come up"

            # (a) the payload: exact numbers derived from the fixture document.
            fx = json.loads(urllib.request.urlopen(fx_base + "/api/stats", timeout=15).read())
            gpu = fx.get("gpu") or {}
            problems = []
            if gpu.get("temp_c") != 71.0:
                problems.append(f"gpu.temp_c is {gpu.get('temp_c')!r}, expected 71.0 from the fixture")
            if gpu.get("util_pct") != 62.0 or gpu.get("util_source") != "measured":
                problems.append(f"gpu utilisation is {gpu.get('util_pct')!r}/{gpu.get('util_source')!r}; "
                                f"a counter the fixture supplies must be labelled measured")
            if gpu.get("mem_pct") != 73.2421875:
                problems.append(f"gpu.mem_pct is {gpu.get('mem_pct')!r}, expected 73.2421875")
            if gpu.get("power_w") != 187.0 or gpu.get("power_source") != "measured":
                problems.append(f"gpu power is {gpu.get('power_w')!r}/{gpu.get('power_source')!r}")
            # The OS keeps its precedence over the engine even under a fixture: the fixture names
            # a fake adapter, and the payload must report that disagreement rather than pick one.
            if gpu.get("name_conflict") != "Fixture Virtual Adapter":
                problems.append(f"gpu.name_conflict is {gpu.get('name_conflict')!r}")
            thr = fx.get("throughput") or {}
            # 2,000 tokens actually read / 10,000 ms prompt_ms from the fixture's newest request.
            if thr.get("prefill") != 200.0:
                problems.append(f"throughput.prefill is {thr.get('prefill')!r}, expected 200.0")
            if thr.get("prefill_mean") != 500.0:
                problems.append(f"throughput.prefill_mean is {thr.get('prefill_mean')!r}, "
                                f"expected 500.0 ((400000-320000) read / 160 s)")
            spec = fx.get("spec") or {}
            if spec.get("accept_pct") != 70.0:
                problems.append(f"spec.accept_pct is {spec.get('accept_pct')!r}, expected 70.0")
            cache = fx.get("cache") or {}
            if cache.get("hit_pct") != 80.0:
                problems.append(f"cache.hit_pct is {cache.get('hit_pct')!r}, expected 80.0")
            engine = fx.get("engine") or {}
            if engine.get("build_info") != "Strata 9.9.99-fixture":
                problems.append(f"engine.build_info is {engine.get('build_info')!r}")
            eps = fx.get("endpoints") or {}
            # Every endpoint the payload reports on must be answered by the fixture, with no
            # exception carved out: an unanswered endpoint means the check is partly observing
            # the live engine after all.
            missing_eps = sorted(k for k, v in eps.items() if not v)
            if missing_eps:
                problems.append(f"the fixture does not answer for: {missing_eps}")
            assert not problems, "fixture answers did not reach the payload:\n  " + "\n  ".join(problems)

            # (b) the DOM: the same fixture seen through the page. This is the GPU panel the user
            #     reported as "all 0%" — with counters present it must show them, not zeros.
            js(ws, "window.__m81_pre_fixture_nav = 1")
            ws.call("Page.navigate", {"url": fx_base + "/"})
            fresh6 = False
            for _ in range(60):
                state = js(ws, "({sentinel: window.__m81_pre_fixture_nav, ready: document.readyState})")
                if state and state.get("sentinel") is None and state.get("ready") == "complete":
                    fresh6 = True
                    break
                time.sleep(0.25)
            assert fresh6, "never observed a fresh document on the fixture-backed server"
            settle_render(ws, 0, "the first poll against the fixture-backed server")

            def read_gpu_panel():
                return js(ws, """(() => {
                  const pick = (id) => { const e = document.getElementById(id); return e ? e.textContent : null; };
                  const gm = document.getElementById('gpu-util-gauge');
                  const tm = document.getElementById('gpu-temp-gauge');
                  return {util: pick('gpu-util'), mem: pick('gpu-mem'), temp: pick('gpu-temp'),
                          state: pick('gpu-state'), name: pick('gpu-name'), power: pick('gpu-power'),
                          utilVal: gm ? gm.getAttribute('value') : null,
                          tempVal: tm ? tm.getAttribute('value') : null};
                })()""")

            # setGauge eases each number toward its target over 600 ms, so poll until the readings
            # land rather than reading once and racing the tween.
            gpane = None
            for _ in range(40):
                gpane = read_gpu_panel()
                if gpane and gpane["temp"] == "71%" and gpane["util"] == "62%":
                    break
                time.sleep(0.25)
            assert gpane, "the GPU panel is missing on the fixture-backed server"
            problems = []
            if gpane["temp"] != "71%":
                problems.append(f"#gpu-temp reads {gpane['temp']!r}, expected '71%'")
            if gpane["util"] != "62%":
                problems.append(f"#gpu-util reads {gpane['util']!r}, expected '62%'")
            if gpane["mem"] not in ("73%",):
                problems.append(f"#gpu-mem reads {gpane['mem']!r}, expected '73%'")
            if gpane["tempVal"] != "71":
                problems.append(f"the temp meter is sized to {gpane['tempVal']!r}, expected '71'")
            if not gpane["state"] or "counters live" not in gpane["state"]:
                problems.append(f"#gpu-state reads {gpane['state']!r}; with measured counters it "
                                f"must say the counters are live")
            if "engine says Fixture Virtual Adapter" not in (gpane["state"] or ""):
                problems.append(f"the engine/OS name disagreement is not shown ({gpane['state']!r})")
            if "Fixture Virtual Adapter" in (gpane["name"] or ""):
                problems.append(f"#gpu-name shows the engine's adapter instead of the OS's: {gpane['name']!r}")
            assert not problems, "the fixture's GPU counters did not reach the panel:\n  " + "\n  ".join(problems)
            print("PASS fixture-engine-values")
        finally:
            try:
                fx_server.terminate()
                fx_server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                fx_server.kill()

        # 26. chart-null-value-is-a-hole (M81-review A3/A4) — the renderer's contract, pinned with
        #     a payload no live DB can produce deterministically: a bucket that WAS sampled but
        #     holds null values. The old code drew `b.total_tokens || 0`, i.e. a definite zero on
        #     the plot floor for a reading that simply does not exist, and the legend disclosed
        #     prefill_max while the drawn line uses prefill_mean, overstating the scale.
        #     A page-level fetch rewrite is the right tool here: this tests what drawSeries does
        #     with a value, not what the server chooses to emit.
        ts_script = ws.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
          (() => {
            const real = window.fetch;
            window.fetch = (u, o) => real(u, o).then((res) => {
              if (!String(u).includes('api/timeseries')) return res;
              const b = (i, v) => ({
                t: 1792512000 + i * 60, time: '2026-10-22T00:0' + i + ':00Z',
                label: 'b' + i, samples: 2,
                requests: v ? v * 3 : null, prompt_tokens: v ? v * 10 : null,
                reused: 0, output_tokens: v ? v * 5 : null, total_tokens: v ? v * 15 : null,
                tok_s_mean: v ? v * 20 : null, tok_s_max: v ? v * 22 : null,
                // prefill_max is deliberately 900 while the drawn mean is far lower: the legend
                // must disclose the peak of the line, not of an undrawn series.
                prefill_mean: v ? v * 100 : null, prefill_max: v ? 900 : null,
                prefill_bounded: false, prefill_note: null,
              });
              // 17 buckets: the label stride is round(17/6)=3, so the last index lands at 15 and
              // the right-edge date is exactly the case a ">= half a stride" veto would drop.
              const vals = [];
              for (let i = 0; i < 17; i++) vals.push(i === 8 ? null : (i % 3) + 1);
              const buckets = vals.map((v, i) => b(i, v));
              // Highest drawn prefill_mean is 3 x 100 = 300 while every drawn prefill_max would
              // say 900, so the A3 assertion below cannot be satisfied by the undrawn series.
              return new Response(JSON.stringify({
                range: '1h', span_s: 1020, bucket_s: 60, n_buckets: 17, empty_buckets: 0,
                buckets,
                summary: {total_requests: 54, total_tokens: 270, prompt_tokens: 180,
                          output_tokens: 90, reused_tokens: 0, tok_s_mean: 50, tok_s_max: 60,
                          prefill_mean: 150, prefill_max: 900},
              }), {headers: {'content-type': 'application/json'}});
            });
          })();"""})
        js(ws, "window.__m81_pre_ts_nav = 1")
        ws.call("Page.navigate", {"url": base + "/"})
        fresh7 = False
        for _ in range(60):
            state = js(ws, "({sentinel: window.__m81_pre_ts_nav, ready: document.readyState})")
            if state and state.get("sentinel") is None and state.get("ready") == "complete":
                fresh7 = True
                break
            time.sleep(0.25)
        assert fresh7, "never observed a fresh document on the timeseries-fixture page"
        # A range-button click forces the fetch (the 5 s throttle would otherwise reuse data).
        fetch_stamp = js(ws, "window.__lastChartFetch || 0")
        js(ws, """(() => {
          const b = document.querySelector("#chart-range-btns .chart-range-btn[data-range='1h']");
          if (b) b.click();
        })()""")
        settle_chart(ws, fetch_stamp, "the forced 1h fetch under the timeseries fixture")

        # A4: a sampled bucket whose value is null must be a hole. A point on the plot floor
        # (y = pad.top + chartH = 25 + 240) is what `|| 0` used to draw for it.
        tok_stamp = js(ws, "window.__lastChartRender || 0")
        js(ws, "document.querySelector('#chart-metric-tabs .chart-tab[data-metric=tokens]').click()")
        settle(ws, "(window.__lastChartRender || 0) > %d" % int(tok_stamp),
               "the tokens re-render under the timeseries fixture")
        floor = js(ws, """(() => {
          const pts = [...document.querySelectorAll('#chart-series-lines polyline')]
            .flatMap(p => (p.getAttribute('points') || '').trim().split(/\\s+/));
          return pts.filter(pt => Math.abs(parseFloat(pt.split(',')[1]) - 265.0) < 0.6);
        })()""")
        assert not floor, (
            f"a sampled bucket with a null value drew a point on the plot floor ({floor[:4]!r})"
        )
        # A3: the prefill line is drawn from prefill_mean, so its disclosure must name the peak
        # of THAT line (3 x 100 = 300.0), never the undrawn prefill_max (900).
        thr_stamp = js(ws, "window.__lastChartRender || 0")
        js(ws, "document.querySelector('#chart-metric-tabs .chart-tab[data-metric=throughput]').click()")
        settle(ws, "(window.__lastChartRender || 0) > %d" % int(thr_stamp),
               "the throughput legend under the timeseries fixture")
        peak = js(ws, "(document.querySelector('#chart-legend .legend-prefill .legend-peak') || {}).textContent || ''")
        assert "300.0" in peak and "900" not in peak, (
            f"the prefill legend discloses a peak that is not the drawn line's ({peak!r})"
        )
        # The disclosure must be more than text: the privately scaled line has to actually be
        # drawn to that scale, i.e. its highest point sits on the top of the plot (y = pad.top).
        # Without this, "scaled to peak X" and the divisor used by drawSeries could drift apart
        # again and only the legend would look wrong in hindsight.
        top = js(ws, """(() => {
          const ln = [...document.querySelectorAll('#chart-series-lines polyline')]
            .find(p => (p.getAttribute('stroke') || '') === '#3fb950');
          if (!ln) return null;
          const ys = (ln.getAttribute('points') || '').trim().split(/\\s+/)
            .map(pt => parseFloat(pt.split(',')[1]));
          return ys.length ? Math.min(...ys) : null;
        })()""")
        assert top is not None and abs(top - 25.0) < 0.6, (
            f"the prefill line's peak is at y={top!r}, not at the plot top (25), so its "
            f"disclosed scale ({peak!r}) is not the scale it was drawn to"
        )
        # A8: the comment promises the last bucket is always dated; a second clause used to veto
        # it when the leftover gap was under half a stride (reachable at N=17, stride 3).
        ticks = js(ws, """(() => [...document.querySelectorAll('#chart-grid text')]
            .map(t => (t.textContent || '').trim()).filter(s => /^b\\d+$/.test(s)))()""")
        assert "b16" in ticks, f"the right edge of the plot is undated ({ticks!r})"
        if (ts_script or {}).get("identifier"):
            ws.call("Page.removeScriptToEvaluateOnNewDocument",
                    {"identifier": ts_script["identifier"]})
        print("PASS chart-null-value-is-a-hole")

        # 27. usage-ledger-renders (M81-review-015 D1) — the ledger's content is host-specific
        #     (it reads whatever Claude Code / Hermes state exists), so no check here pinned it,
        #     which is how a refactor could leave every successful fetch throwing and printing
        #     "unavailable (u is not defined)" over numbers that had just loaded. Serving a
        #     pinned /api/usage answer makes the whole path deterministic.
        # Round 3 (A4): the payload used to be a literal inside the injected script, so the
        # fixture and the assertions below were two copies of the same hand-written field names.
        # Renaming a key in usage_ledger.summary() would have left both sides agreeing and the
        # check green while the real panel read undefined. The fixture is now one dict, and its
        # shape is cross-checked against what this suite's own server actually answers below.
        usage_fixture = {
            "window": {"from": "2026-10-28T00:00:00Z", "to": "2026-10-28T12:00:00Z"},
            "orchestrator": {"sessions": 3},
            "executor": {"input": 1200, "output": 300},
            "weighted": {"orchestrator": 4200},
            "sources": {"claude_code": "ok", "hermes": "ok"},
            "partial": False,
            "generated_at": "2026-10-28T12:00:00Z",
            # executor_models is part of the /api/usage contract (M78-H5) even though this panel
            # does not render it; leaving it out would let the fixture drift from the real payload.
            "executor_models": ["strata-iq3_s"],
        }
        usage_script = ws.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
          (() => {
            const real = window.fetch;
            window.fetch = (u, o) => real(u, o).then((res) => {
              if (!String(u).includes('api/usage')) return res;
              return new Response(JSON.stringify(%s),
                                  {headers: {'content-type': 'application/json'}});
            });
          })();""" % json.dumps(usage_fixture)})
        js(ws, "window.__m81_pre_usage_nav = 1")
        ws.call("Page.navigate", {"url": base + "/"})
        fresh8 = False
        for _ in range(60):
            state = js(ws, "({sentinel: window.__m81_pre_usage_nav, ready: document.readyState})")
            if state and state.get("sentinel") is None and state.get("ready") == "complete":
                fresh8 = True
                break
            time.sleep(0.25)
        assert fresh8, "never observed a fresh document on the usage-fixture page"
        settle_usage(ws)
        ledger = js(ws, """(() => {
          const pick = (id) => { const e = document.getElementById(id); return e ? e.textContent : null; };
          return {orch: pick('usage-day-orch'), exec: pick('usage-week-exec'),
                  src: pick('usage-sources')};
        })()""")
        assert ledger["src"] is not None, "#usage-sources is missing from the page"
        assert "unavailable" not in ledger["src"] and "not defined" not in ledger["src"], (
            f"the ledger failed on a payload it was given ({ledger['src']!r})"
        )
        assert "Claude Code ok" in ledger["src"] and "Hermes ok" in ledger["src"], (
            f"the fixture's sources did not reach the row ({ledger['src']!r})"
        )
        assert ledger["orch"] == "4.2 k weighted", (
            f"#usage-day-orch reads {ledger['orch']!r} for a weighted total of 4200"
        )
        assert ledger["exec"] == "1.5 k tokens", (
            f"#usage-week-exec reads {ledger['exec']!r} for 1200 in + 300 out"
        )
        # The fixture must stay the shape the server emits, or this check quietly stops testing
        # the real payload. Ask the suite's own server (its ledger is empty on a fresh test DB,
        # which is fine: only the key set matters here), and require BOTH directions: every
        # fixture key exists in the response, and the response carries no contract key the
        # fixture omits. Proven by agent/scratch-m81-rv3/mutate_a4.py — dropping a contract key
        # from the fixture (or from usage_ledger.summary) fails with the two key sets named.
        live = json.loads(urllib.request.urlopen(
            base + "/api/usage?from=2026-10-28T00:00:00Z&to=2026-10-28T12:00:00Z", timeout=10
        ).read())
        absent = sorted(set(usage_fixture) - set(live))
        assert not absent, (
            f"the usage fixture carries keys the server no longer emits: {absent}; "
            f"the server emits {sorted(live)}"
        )
        untested = sorted(set(live) - set(usage_fixture))
        assert not untested, (
            f"the server's usage contract has keys the fixture never exercises: {untested}; "
            f"the fixture carries {sorted(usage_fixture)}"
        )
        if (usage_script or {}).get("identifier"):
            ws.call("Page.removeScriptToEvaluateOnNewDocument",
                    {"identifier": usage_script["identifier"]})
        print("PASS usage-ledger-renders")

        # 27b. usage-payload-missing-keys (review-015 round 4, R3-1) — the A5 guards exist for a
        #      payload that omits a key the server normally emits (a proxy, a truncated body, a
        #      future shape change). The fixture above supplies every key, so deleting both guards
        #      left the whole suite green: the fix had no coverage. Same payload minus the two
        #      guarded keys must degrade field by field, not throw over numbers that rendered.
        thin_script = ws.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
          (() => {
            const real = window.fetch;
            window.fetch = (u, o) => real(u, o).then((res) => {
              if (!String(u).includes('api/usage')) return res;
              return new Response(JSON.stringify(%s),
                                  {headers: {'content-type': 'application/json'}});
            });
          })();""" % json.dumps({
            "window": {"from": "2026-10-28T00:00:00Z", "to": "2026-10-28T12:00:00Z"},
            "orchestrator": {"sessions": 3},
            "executor": {"input": 1200, "output": 300},
            "partial": False,
            "generated_at": "2026-10-28T12:00:00Z",
        })})
        js(ws, "window.__m81_pre_thin_nav = 1")
        ws.call("Page.navigate", {"url": base + "/"})
        fresh9 = False
        for _ in range(60):
            state = js(ws, "({sentinel: window.__m81_pre_thin_nav, ready: document.readyState})")
            if state and state.get("sentinel") is None and state.get("ready") == "complete":
                fresh9 = True
                break
            time.sleep(0.25)
        assert fresh9, "never observed a fresh document on the thin-payload page"
        settle_usage(ws)
        thin = js(ws, """(() => {
          const pick = (id) => { const e = document.getElementById(id); return e ? e.textContent : null; };
          return {orch: pick('usage-day-orch'), exec: pick('usage-week-exec'),
                  src: pick('usage-sources')};
        })()""")
        assert thin["orch"] == "unavailable", (
            f"a payload with no weighted block must read unavailable, got {thin['orch']!r}"
        )
        assert thin["exec"] == "1.5 k tokens", (
            f"the executor block WAS present and must still render, got {thin['exec']!r}"
        )
        assert "n/a" in (thin["src"] or "") and "unavailable" not in (thin["src"] or ""), (
            f"missing sources must print n/a per source, not the catch branch's "
            f"'unavailable (...)', got {thin['src']!r}"
        )
        if (thin_script or {}).get("identifier"):
            ws.call("Page.removeScriptToEvaluateOnNewDocument",
                    {"identifier": thin_script["identifier"]})
        print("PASS usage-payload-missing-keys")

        # 27c. history-dateless-day (review-015 round 4, R3-2/R3-3) — the A8 fix guarded the x
        #      tick only. The scrubber's aria-valuetext, its selected-day line and the offline
        #      fallback label all read `.date` unguarded, so one date-less day row still printed
        #      "undefined" (or threw) while the bars themselves said "day N". Driven with a real
        #      date-less row: grepping app.js for the fallback would not have caught any of it.
        #      This check FAILED on the code as shipped before dayName() existed —
        #      `aria-valuetext printed an undefined date ('undefined, day 11 of 11')` — so its
        #      failability is established by the defect it found, not by a later mutation.
        dateless_script = ws.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
          (() => {
            const real = window.fetch;
            window.fetch = (u, o) => real(u, o).then((res) => {
              if (!String(u).includes('api/stats')) return res;
              return res.json().then((j) => {
                if (j && Array.isArray(j.daily) && j.daily.length) {
                  // Keep the shape, drop the date on the last (rightmost, ticked) day.
                  delete j.daily[j.daily.length - 1].date;
                }
                return new Response(JSON.stringify(j),
                                    {headers: {'content-type': 'application/json'}});
              });
            });
          })();"""})
        js(ws, "window.__m81_pre_dateless_nav = 1")
        ws.call("Page.navigate", {"url": base + "/"})
        fresh10 = False
        for _ in range(60):
            state = js(ws, "({sentinel: window.__m81_pre_dateless_nav, ready: document.readyState})")
            if state and state.get("sentinel") is None and state.get("ready") == "complete":
                fresh10 = True
                break
            time.sleep(0.25)
        assert fresh10, "never observed a fresh document on the dateless-day page"
        render_stamp = js(ws, "window.__lastRender || 0")
        settle_render(ws, render_stamp, "the poll that renders the seeded days", timeout=25.0)
        # Select the date-less day (the last one) so every readout that names a day is exercised.
        js(ws, """(() => {
          const bars = document.querySelectorAll('#hist-bars .hist-bar');
          if (bars.length) bars[bars.length - 1].dispatchEvent(new MouseEvent('click', {bubbles: true}));
        })()""")
        # selectDay() runs synchronously on click, so no wait is needed before reading.
        named = js(ws, """(() => {
          const track = document.getElementById('scrub');
          const sel = document.getElementById('hist-selected');
          const ticks = [...document.querySelectorAll('#hist-bars .chart-axis-text')]
            .map(t => (t.textContent || '').trim());
          return {valuetext: track && track.getAttribute('aria-valuetext'),
                  selected: sel && (sel.textContent || '').trim(), ticks};
        })()""")
        assert named["valuetext"] and "undefined" not in named["valuetext"], (
            f"aria-valuetext printed an undefined date ({named['valuetext']!r})"
        )
        assert named["selected"] and "undefined" not in named["selected"], (
            f"the selected-day line printed an undefined date ({named['selected']!r})"
        )
        assert not any("undefined" in t for t in named["ticks"]), (
            f"an x tick printed an undefined date ({named['ticks']!r})"
        )
        if (dateless_script or {}).get("identifier"):
            ws.call("Page.removeScriptToEvaluateOnNewDocument",
                    {"identifier": dateless_script["identifier"]})
        print("PASS history-dateless-day")

        # 28. detail-wiring-follows-the-region (M81-review A7, residual gap from review-015) —
        # wiring the region's children at init still missed a panel dragged in later in the
        # same session: nothing re-attaches a listener after a drop. beforematch bubbles (the
        # HTML ancestor-revealing algorithm fires it "with the bubbles attribute initialized to
        # true"), so one delegated listener on the region covers every panel, present or future.
        # The panel is moved with appendChild rather than a trusted drag because the property
        # under test is purely whether the wiring follows the node into the region; the drop
        # handler's effect on the DOM is the same move, and drag-persists already proves the drag.
        # The panel is moved back out of the region without a following settle. That is safe only
        # because this check is the last one in the file (review-015 round 4, R3-6); anything
        # appended after it that reads geometry must settle first, or it inherits the stale span
        # this leaves behind.
        wired = js(ws, """(() => {
          const detail = document.getElementById('detail');
          const region = detail.querySelector('.tiles--detail');
          const panel = [...document.querySelector('.tiles').children]
            .find(el => el.classList.contains('panel') && el.id !== 'detail');
          if (!detail || !region || !panel) return null;
          const moved = panel.id;
          region.appendChild(panel);
          detail.open = false;
          // A bubbling beforematch is exactly what find-in-page / fragment navigation dispatches.
          panel.dispatchEvent(new Event('beforematch', { bubbles: true }));
          const openedByMoved = detail.open;
          // Round 3 (A3): the previous negative here dispatched on a child of the SIBLING grid.
          // A bubbling event can never reach a listener on this subtree, so `openedByStranger
          // is False` was unfailable by construction and tested DOM basics, not coverage.
          // The discriminating version dispatches on document.body: it bubbles through every
          // ancestor, so a listener attached to document/window (the rewrite the static check
          // now also forbids) WOULD open the region, while a region-bound listener does not.
          detail.open = false;
          document.body.dispatchEvent(new Event('beforematch', { bubbles: true }));
          const openedByBodyDispatch = detail.open;
          detail.open = false;
          region.removeChild(panel);
          document.querySelector('.tiles').appendChild(panel);
          return {moved, openedByMoved, openedByBodyDispatch};
        })()""")
        assert wired, "no panel available to move into the Detail region"
        assert wired["openedByMoved"], (
            f"beforematch on {wired['moved']!r}, moved into the region after init, did not open it"
        )
        assert wired["openedByBodyDispatch"] is False, (
            "a beforematch dispatched on document.body opened the region, so the listener is not "
            f"bound to the region ({wired['openedByBodyDispatch']!r})"
        )

        # And the structural half (round 3 A2/A3): ask the browser directly where the listener
        # lives, rather than inferring it from behaviour. The region must have a beforematch
        # listener; document and window must not.
        def listeners_of(expression):
            obj = ws.call("Runtime.evaluate", {"expression": expression, "objectGroup": "m81dw"})
            object_id = (obj.get("result") or {}).get("objectId")
            if not object_id:
                return None
            # depth 0 = the object itself plus its prototype chain. depth -1 would search every
            # DESCENDANT, which made document report the region's and #log's own listeners and
            # this check fail on correct code.
            got = ws.call("DOMDebugger.getEventListeners", {"objectId": object_id, "depth": 0})
            return [l for l in got.get("listeners", []) if l.get("type") == "beforematch"]

        try:
            on_region = listeners_of(
                "document.getElementById('detail').querySelector('.tiles--detail')")
            on_document = listeners_of("document")
            on_window = listeners_of("window")
        finally:
            ws.call("Runtime.releaseObjectGroup", {"objectGroup": "m81dw"})
        assert on_region is not None and len(on_region) >= 1, (
            "the Detail region has no beforematch listener"
        )
        assert not on_document and not on_window, (
            f"beforematch is also listened for outside the region "
            f"(document={len(on_document or [])} window={len(on_window or [])})"
        )
        print("PASS detail-wiring-follows-the-region")
        return 0
    finally:
        for p in (proc, server):
            if not p:
                continue
            try:
                p.terminate()
            except OSError:
                pass
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
        try:
            if ws:
                ws.sock.close()
        except OSError:
            pass
        # The browser profile and the test telemetry DBs all live under this directory, so one
        # recursive removal is the whole cleanup. Best-effort: a locked Chrome profile file must
        # not turn a passing run into a failing one.
        try:
            shutil.rmtree(profile, ignore_errors=True)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
