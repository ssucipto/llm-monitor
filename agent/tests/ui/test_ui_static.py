"""Static UI suite (llm-monitor M79-T8 / M80) — SIMULATED: reads the shipped files and
starts the real server.py on a free port the OS assigns; never the live :8090 dashboard,
never a real engine. One PASS line per check.

Why this exists: index.html's id attributes are the contract — app.js writes into them
from /api/stats. A renamed or deleted id is a silent runtime hole (setText/setGauge just
miss). These checks make that mechanical instead of eyeballed.

Checks
  1 no-stale-classes   index.html no longer references the pre-M79 .masonry/.band/hero__
  2 literal-ids        every $()/setText()/setGauge() id literal in app.js exists in HTML
  3 template-ids       the built ids (spark groups, hud dots, usage rows) exist
  4 default-order      DEFAULT_ORDER tiles+detail == the 16 panels, no extras
  5 hud-ids            every hud-* id used by app.js exists; HUD subtree stays dense
  6 unique-ids         no duplicate id in index.html
  7 server-smoke       server.py serves index.html, app.js and style.css on a free port
"""
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))  # agent/tests/ui -> repo root
UI = os.path.join(ROOT, "llm-monitor")

fails = []


def expect(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -- {str(detail)[:300]}"))
    if not ok:
        fails.append(name)


def read(rel):
    with open(os.path.join(UI, rel), encoding="utf8") as fh:
        return fh.read()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    html = read("index.html")
    js = read("app.js")

    # 1 — no stale pre-M79 layout classes outside the HUD subtree (a half-migrated file).
    hud = re.search(r'<div class="hud"[^>]*id="view-compact".*?</main>', html, re.S)
    outside_hud = html.replace(hud.group(0), "") if hud else html
    leftovers = re.findall(r'class="[^"]*\b(?<!hud-)hero(?:__|[-"])|(?:^|[\s"])(masonry|band)(?:[\s"])', outside_hud)
    expect("no-stale-classes", not leftovers, f"stale M79 class references: {sorted(set(leftovers))}")

    # 2 — literal ids app.js reaches for must exist in the markup.
    html_ids = set(re.findall(r'\bid="([^"]+)"', html))
    used = set()
    used.update(re.findall(r'\$\("([^"]+)"\)', js))
    used.update(re.findall(r'setText\("([^"]+)"', js))
    for m in re.findall(r'setGauge\("([^"]+)",\s*"([^"]+)"', js):
        used.update(m)
    dynamic = {"drop-slot"}  # created by app.js during a drag
    missing = sorted(used - html_ids - dynamic)
    expect("literal-ids", not missing, f"app.js ids absent from index.html: {missing[:12]}")

    # 3 — template-built ids. drawSpark(prefix) writes <prefix>-{spark,area,head,halo,caption};
    # usage rows and endpoint dots are built the same way. Each must exist in the markup.
    # -halo is optional in code (drawSpark guards it with `if (halo)`), so only the other
    # four suffixes are contractual; a series may ship without a halo.
    prefixes = set(re.findall(r'drawSpark\("([^"]+)"', js))
    built = set()
    for p in prefixes:
        for suffix in ("spark", "area", "head", "caption"):
            built.add(f"{p}-{suffix}")
    for key in ("day", "week"):
        built.add(f"usage-{key}-orch")
        built.add(f"usage-{key}-exec")
    built.add("usage-sources")
    for k in ("health", "metrics", "slots", "models", "status"):
        built.add(f"hud-dot-{k}")
    missing_built = sorted(b for b in built if b not in html_ids)
    expect("template-ids", not missing_built, f"built ids absent from index.html: {missing_built[:12]}")

    # 4 — DEFAULT_ORDER must cover exactly the panels that ship, split across the two grids.
    m = re.search(r'const DEFAULT_ORDER = \{(.*?)\n\};', js, re.S)
    assert m, "DEFAULT_ORDER block not found in app.js"
    lists = {}
    for name in ("tiles", "detail"):
        lm = re.search(rf'{name}: \[(.*?)\]', m.group(1), re.S)
        assert lm, f"DEFAULT_ORDER.{name} missing"
        lists[name] = re.findall(r'"([^"]+)"', lm.group(1))
    panels = re.findall(r'<section class="panel[^"]*" id="([^"]+)"', html)
    ordered = lists["tiles"] + lists["detail"]
    problems = []
    if len(set(ordered)) != len(ordered):
        problems.append("duplicate ids in DEFAULT_ORDER")
    if set(ordered) != set(panels):
        problems.append(f"order vs panels mismatch: only-in-order={sorted(set(ordered)-set(panels))} "
                        f"only-panels={sorted(set(panels)-set(ordered))}")
    if not lists["tiles"] or not lists["detail"]:
        problems.append("DEFAULT_ORDER has an empty list")
    expect("default-order", not problems, problems)

    # 5 — HUD (compact view) ids: every hud-* app.js touches exists, and the subtree stays dense.
    js_hud = {i for i in used | built if i.startswith("hud-") and not i.endswith("-halo")}
    missing_hud = sorted(i for i in js_hud if i not in html_ids)
    hud_ids = re.findall(r'\bid="(hud-[^"]+)"', hud.group(0) if hud else html)
    expect("hud-ids", not missing_hud and len(set(hud_ids)) >= 40,
           f"missing={missing_hud[:8]} hud_id_count={len(set(hud_ids))}")

    # 6 — no duplicate ids anywhere in the page.
    all_ids = re.findall(r'\bid="([^"]+)"', html)
    dupes = sorted({i for i in all_ids if all_ids.count(i) > 1})
    expect("unique-ids", not dupes, f"duplicate ids: {dupes[:12]}")

    # 7 — the real server serves the three files that make the contract (free port, own PID).
    # LLM_MONITOR_DB keeps this run out of the production history: every /api/stats appends a
    # poll row, and audit-33 a33-34 measured that as real pollution of telemetry.sqlite3.
    port = free_port()
    test_db = os.path.join(tempfile.mkdtemp(prefix="m81-static-"), "telemetry-test.sqlite3")
    proc = subprocess.Popen([sys.executable, os.path.join(UI, "server.py"), str(port)],
                            cwd=UI, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            env=dict(os.environ, LLM_MONITOR_DB=test_db))
    try:
        base = f"http://127.0.0.1:{port}"
        up = False
        for _ in range(40):
            try:
                urllib.request.urlopen(base + "/", timeout=2)
                up = True
                break
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.25)
        if not up:
            expect("server-smoke", False, "server.py did not come up on a free port")
        else:
            bad = []
            for path, needle in (("/", "<section class=\"panel"), ("/app.js", "DEFAULT_ORDER"),
                                 ("/style.css", ".tiles")):
                try:
                    body = urllib.request.urlopen(base + path, timeout=10).read().decode("utf8", "replace")
                    if needle not in body:
                        bad.append(f"{path} lacks {needle!r}")
                except Exception as exc:
                    bad.append(f"{path}: {exc}")
            # One stats call so the isolation check below has something to look for.
            try:
                urllib.request.urlopen(base + "/api/stats", timeout=10).read()
            except Exception as exc:
                bad.append(f"/api/stats: {exc}")
            expect("server-smoke", not bad, bad)

            # 8 — the poll row landed in the test DB, not beside server.py (a33-34). If the env
            # override is removed this file is never created, so the check can fail.
            rows = -1
            if os.path.exists(test_db):
                con = sqlite3.connect(test_db)
                try:
                    rows = con.execute("SELECT count(*) FROM poll").fetchone()[0]
                finally:
                    con.close()
            expect("telemetry-db-isolated", rows > 0,
                   f"expected poll rows in the LLM_MONITOR_DB file, got {rows}")

            # 9 — GPU name provenance (audit-33 a33-01). The engine's hardware_static.gpu_name is
            # not a measurement: on this PC it names a card that was removed. The server must
            # resolve the name through its own OS detection and never label the engine's value
            # "measured".
            srv_src = open(os.path.join(UI, "server.py"), encoding="utf8").read()
            problems = []
            if '"name_source": "measured"' in srv_src:
                problems.append("gpu.name_source can still be 'measured'")
            if 'HOST_GPU["name"]' not in srv_src:
                problems.append("the gpu name is not resolved through the OS detection")
            if '"name_conflict"' not in srv_src:
                problems.append("no name_conflict key — an OS/engine disagreement would be hidden")
            expect("gpu-name-provenance", not problems, problems)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    if fails:
        print(f"[tests/ui static] FAIL {len(fails)}: {fails}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
