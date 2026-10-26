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
import socket
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
          for (const id of ['requests','charts','history','detail']) {
            const el = document.getElementById(id);
            if (!el) { out[id] = 'missing'; continue; }
            el.open = true;
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
        ids = set(order.get("tiles", [])) | set(order.get("detail", []))
        panels = js(ws, "[...document.querySelectorAll('.tiles > .panel')].map(e => e.id)")
        missing = sorted(set(panels) - ids)
        assert not missing, f"saved order dropped panels: {missing}"
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
        pos = "[...document.querySelectorAll('.tiles > .panel')].map(e => e.id).indexOf(" + json.dumps(src) + ")"
        before = js(ws, pos)
        ws.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": pts["x0"], "y": pts["y0"], "button": "left", "clickCount": 1})
        for i in (1, 2, 3):
            mx = pts["x0"] + (pts["x1"] - pts["x0"]) * i / 3
            my = pts["y0"] + (pts["y1"] - pts["y0"]) * i / 3
            ws.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": mx, "y": my, "button": "left"})
            time.sleep(0.12)
        ws.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": pts["x1"], "y": pts["y1"], "button": "left", "clickCount": 1})
        time.sleep(0.6)
        after = js(ws, pos)
        assert after != before and after >= 0, f"drag did not move #{src} (before={before}, after={after})"
        persisted = js(ws, "localStorage.getItem('llm-monitor-order')")
        assert persisted, "drag committed but nothing was persisted"
        got = json.loads(persisted).get("tiles", [])
        assert got.index(src) == after, f"persisted position {got.index(src)} != DOM position {after}"
        print("PASS drag-persists")
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
