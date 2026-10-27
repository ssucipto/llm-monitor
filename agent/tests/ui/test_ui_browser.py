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
        # Let the first poll + render land, and collect any thrown errors while it does.
        time.sleep(3.0)

        # 1. page-clean — no uncaught exceptions during load and first renders.
        errs = [e["params"].get("exceptionDetails", {}) for e in ws.events if e.get("method") == "Runtime.exceptionThrown"]
        assert not errs, "page threw: " + json.dumps(errs[0])[:400]
        print("PASS page-clean")

        # Pin a known viewport so geometry assertions are deterministic.
        ws.call("Emulation.setDeviceMetricsOverride", {"width": 1240, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        time.sleep(0.5)
        js(ws, "window.dispatchEvent(new Event('resize'))")
        time.sleep(0.8)

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
            ws.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False})
            time.sleep(0.6)
            js(ws, "window.dispatchEvent(new Event('resize'))")
            time.sleep(0.6)

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
        ws.call("Emulation.clearDeviceMetricsOverride")
        time.sleep(0.6)
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
            time.sleep(0.4)

        click_id("layout-save")
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
        ws.call("Emulation.setDeviceMetricsOverride", {"width": 1240, "height": 1400, "deviceScaleFactor": 1, "mobile": False})
        time.sleep(0.6)
        js(ws, "window.dispatchEvent(new Event('resize'))")
        time.sleep(0.8)
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
        ws.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": pts["x0"], "y": pts["y0"], "button": "left", "clickCount": 1})
        for i in (1, 2, 3):
            mx = pts["x0"] + (pts["x1"] - pts["x0"]) * i / 3
            my = pts["y0"] + (pts["y1"] - pts["y0"]) * i / 3
            ws.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": mx, "y": my, "button": "left"})
            time.sleep(0.12)
        ws.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": pts["x1"], "y": pts["y1"], "button": "left", "clickCount": 1})
        time.sleep(0.6)
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
        assert dgeo["tiles"] >= 4, f"expected the Detail region to show several panels, got {dgeo['tiles']}"
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
        click_id("tab-compact")
        time.sleep(0.6)
        assert js(ws, "document.body.getAttribute('data-view')") == "compact", "Compact tab did not switch the view"
        click_id("tab-full")
        time.sleep(0.6)
        assert js(ws, "document.body.getAttribute('data-view')") == "full", "Full tab did not switch the view"
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
        time.sleep(3.0)   # first poll + render + layout pass
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
        ws.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
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
                      hudCtx: hc ? hc.textContent : null, hudCtxVal: hv ? hv.textContent : null};
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
        # Switch the metric tab; the unit must change with it.
        js(ws, """(() => {
          const t = document.querySelector('#chart-metric-tabs .chart-tab[data-metric=throughput]');
          if (t) t.click();
        })()""")
        time.sleep(0.5)
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

        js(ws, """(() => {
          document.querySelector('#chart-metric-tabs .chart-tab[data-metric=throughput]').click();
          const b = document.querySelector("#chart-range-btns .chart-range-btn[data-range='1h']");
          if (b) b.click();
        })()""")
        time.sleep(1.5)
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

        js(ws, """(() => {
          const b = document.querySelector("#chart-range-btns .chart-range-btn[data-range='7d']");
          if (b) b.click();
        })()""")
        time.sleep(2.0)
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


if __name__ == "__main__":
    sys.exit(main())
