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
  8 db-isolation       the poll row lands in LLM_MONITOR_DB, not beside server.py
  9 gpu-provenance     gpu.name_source is never "measured"; name_conflict exists
 10 no-empty-prior-pct no hardcoded +100% out of an empty prior period (a33-16)
 11 fallback-shape   the offline fallback builds buckets with the same keys the API emits
 12 toc-covers-panels every panel is reachable from the nav, and no nav link is dead (a33-31)
 13 header-unique-units no two visible header cells print the same unit label (a33-26)
 14 gauge-scale-labelled the prefill gauge's scale is named in markup and driven from data (a33-27)
 15 engine-fixture-honoured LLM_MONITOR_FIXTURE answers _get_json, and a bad fixture aborts startup (a33-35)
 16 geometry-read-settled every viewport change is followed by a settle, not a fixed sleep (a32-02)
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

            # 10 — a33-16: a percentage computed out of an empty prior period is not a number.
            # Every real delta in app.js goes through fmtDelta(); a hardcoded "+100%" literal can
            # only be the old empty-prior shortcut, which claimed a 0 -> N change was 2x.
            bad_pct = [ln.strip() for ln in js.splitlines() if '"+100%"' in ln or "'+100%'" in ln]
            expect("no-empty-prior-percent", not bad_pct,
                   f"hardcoded +100% out of an empty prior: {bad_pct[:4]}")

            # 11 — M81-T4 (a33-21): the renderer decides what is observed from bucket.samples.
            # The offline fallback in app.js builds its own buckets, and if it stops setting the
            # fields the renderer reads, every fallback bucket looks unobserved and the chart
            # silently draws nothing. Assert both bucket builders set the same contract keys.
            server_src = srv_src
            api_bucket = re.search(r'"samples":', server_src) is not None
            fb_blocks = re.findall(r'buckets\.push\(\{(.*?)\n      \}\);', js, re.S)
            problems = []
            if not api_bucket:
                problems.append("server.py db_timeseries no longer emits a per-bucket samples count")
            if len(fb_blocks) != 2:
                problems.append(f"expected 2 fallback bucket builders in app.js, found {len(fb_blocks)}")
            for i, blk in enumerate(fb_blocks):
                for key in ("samples", "tok_s_mean", "prefill_mean", "prefill_max", "total_tokens"):
                    if re.search(rf"\b{key}\b", blk) is None:
                        problems.append(f"fallback bucket builder {i+1} omits {key}")
            expect("fallback-bucket-shape", not problems, problems)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    # 12 — M81-T6 (a33-31): the nav used to omit #usage and point six links into a collapsed
    # region. Every panel must be reachable from it, and no link may be dead. Read straight off
    # the markup, so it does not depend on the server having come up.
    nav = re.search(r'<nav class="toc"[\s\S]*?</nav>', html)
    problems = []
    if not nav:
        problems.append("no .toc nav element")
    else:
        hrefs = re.findall(r'href="#([^"]+)"', nav.group(0))
        panels = re.findall(r'<section class="panel[^"]*" id="([^"]+)"', html)
        dead = sorted({h for h in hrefs if h not in panels})
        unreachable = sorted(set(panels) - set(hrefs))
        if dead:
            problems.append(f"nav links to non-panels: {dead}")
        if unreachable:
            problems.append(f"panels unreachable from the nav: {unreachable}")
    expect("toc-covers-panels", not problems, problems)

    # 13 — M81-T7 (a33-26): the header used to render throughput.now twice, both cells labelled
    # "decode tok/s". Asserting on the unit LABELS rather than on ids is what makes this catch the
    # class of bug: any future pair of header cells that claim the same thing fails, whatever they
    # are called. Hidden cells (#top-tok) are excluded — it stays in the DOM for the id contract.
    header = re.search(r'<header class="topbar">([\s\S]*?)</header>', html)
    problems = []
    if not header:
        problems.append("no <header class=\"topbar\"> block")
    else:
        block = header.group(1)
        # Drop one-line hidden subtrees so a kept-but-hidden cell cannot count as visible.
        visible = re.sub(r'<span[^>]*\bhidden\b[^>]*>[\s\S]*?</span>', "", block)
        units = [u.strip() for u in
                 re.findall(r'class="(?:kpi__unit|topbar__unit)"[^>]*>([^<]*)<', visible)]
        dupes = sorted({u for u in units if units.count(u) > 1})
        if dupes:
            problems.append(f"header cells share a unit label: {dupes}")
        for speed in ("decode tok/s", "prefill tok/s"):
            n = sum(1 for u in units if u.startswith(speed))
            if n != 1:
                problems.append(f"{n} visible header cells label {speed!r}; the header must carry it once")
    expect("header-unique-units", not problems, problems)

    # 14 — M81-T7 (a33-27): the gauge had only an aria-label, so a sighted user could not tell what
    # the bar measured or where its end was, and the end was a hardcoded 2000 tok/s that this
    # engine's ~150-400 tok/s prefill never reached. The scale must be named in markup, written by
    # app.js from data, and never pinned at the old constant. It is a separate cell from the unit
    # label because the Compact HUD hides the gauge bar and must hide the scale with it.
    problems = []
    if not re.search(r'id="top-gauge-ceiling"', html):
        problems.append("index.html has no #top-gauge-ceiling element")
    if re.search(r'setText\("top-gauge-ceiling"', js) is None:
        problems.append("app.js never writes the gauge scale ceiling")
    if re.search(r'aria-label="prefill speed gauge"', html) is None:
        problems.append("#top-gauge lost its aria-label")
    hardcoded = [ln.strip() for ln in js.splitlines() if re.search(r'ceiling\s*=\s*2000\b', ln)]
    if hardcoded:
        problems.append(f"the gauge ceiling is hardcoded again: {hardcoded[:2]}")
    expect("gauge-scale-labelled", not problems, problems)

    # 15 — M81-T8 (audit-33 a33-35): the browser suite drives the real server, so without an
    # engine-independent source of engine answers every value assertion either pins numbers inside
    # the page or depends on whatever owns :8080 at run time. server.py must honour
    # LLM_MONITOR_FIXTURE, and it must fail loudly when that fixture is unusable rather than
    # quietly fall back to the live engine — which would test the live engine by accident.
    srv_src = open(os.path.join(UI, "server.py"), encoding="utf8").read()
    fixture_path = os.path.join(HERE, "fixtures", "engine.json")
    problems = []
    if 'os.environ.get("LLM_MONITOR_FIXTURE")' not in srv_src:
        problems.append("server.py does not read LLM_MONITOR_FIXTURE")
    if re.search(r"if _FIXTURE is not None:\s*\n\s*return _FIXTURE\.get\(path\)", srv_src) is None:
        problems.append("_get_json does not answer from the fixture")
    if "raise SystemExit(2)" not in srv_src:
        problems.append("an unusable fixture does not abort startup (silent fallback to the engine)")
    # The fixture must exist, parse, and cover the endpoints the payload needs.
    doc = None
    try:
        doc = json.load(open(fixture_path, encoding="utf8"))
    except Exception as exc:
        problems.append(f"fixtures/engine.json unreadable: {exc}")
    if isinstance(doc, dict):
        need = ("/health", "/metrics", "/props", "/slots", "/v1/models")
        absent = [p for p in need if p not in doc]
        if absent:
            problems.append(f"fixture is missing endpoints: {absent}")
        hw = ((doc.get("/metrics") or {}).get("hardware") or {})
        # The whole point of this fixture: gpu_* counters carry values, so the GPU panel's
        # measured path is reachable in a test even though this PC's driver reports none.
        dead = [k for k in ("gpu_util", "gpu_temp", "gpu_power", "gpu_mem_used")
                if hw.get(k) is None]
        if dead:
            problems.append(f"fixture gpu counters carry no value: {dead}")
    # Behaviour, not just text: a bad fixture path must stop the server from starting.
    try:
        bad_proc = subprocess.run(
            [sys.executable, os.path.join(UI, "server.py"), str(free_port())],
            cwd=UI, capture_output=True, text=True, timeout=30,
            env=dict(os.environ, LLM_MONITOR_FIXTURE=os.path.join(HERE, "fixtures", "nope.json")),
        )
        if bad_proc.returncode == 0:
            problems.append("a missing fixture file did not stop the server")
    except subprocess.TimeoutExpired:
        # The server stayed up, which is exactly the silent-fallback failure this guards.
        problems.append("the server kept running with an unusable LLM_MONITOR_FIXTURE")
    expect("engine-fixture-honoured", not problems, problems)

    # 16 — M81-T8 (audit-32 a32-02): a geometry read must follow an observable settle, never a
    # fixed sleep. Rather than ban time.sleep outright (the suite legitimately sleeps while polling
    # for an observable), assert the rule that matters: every viewport change is followed by a
    # settle_spans() before anything reads spans, with no sleep in between. Inserting a sleep(3.0)
    # after an override — the old pattern — fails this.
    src = open(os.path.join(HERE, "test_ui_browser.py"), encoding="utf8").read()
    lines = src.splitlines()
    problems = []
    change_at = [i for i, ln in enumerate(lines)
                 if "DeviceMetricsOverride" in ln and "ws.call" in ln]
    if not change_at:
        problems.append("no viewport overrides found — the geometry checks would not be pinned")
    for i in change_at:
        # A generous window: a viewport change may legitimately be followed by another settle
        # (e.g. settle_usage) before settle_spans, as long as no fixed sleep is involved.
        window = lines[i + 1:i + 9]
        joined = "\n".join(window)
        if "settle_spans(" not in joined:
            problems.append(f"line {i+1}: a viewport change is not followed by settle_spans()")
        for off, ln in enumerate(window):
            if "settle_spans(" in ln:
                break
            if re.search(r"time\.sleep\(\s*\d", ln) and "for _ in range" not in ln:
                problems.append(f"line {i+2+off}: a fixed sleep sits between a viewport change and "
                                f"its settle: {ln.strip()[:70]}")
    # And the settle helpers themselves must still be observable-driven.
    for helper in ("def settle(", "def settle_spans(", "def settle_render(", "def settle_chart(",
                   "def settle_usage("):
        if helper not in src:
            problems.append(f"settle helper {helper!r} is gone")
    for stamp in ("__lastLayout", "__lastRender", "__lastChartFetch", "__lastChartRender", "__lastUsage"):
        if stamp not in read("app.js"):
            problems.append(f"app.js no longer exposes the {stamp} observable the suite waits on")
    expect("geometry-read-settled", not problems, problems)

    if fails:
        print(f"[tests/ui static] FAIL {len(fails)}: {fails}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
