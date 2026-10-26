"""run-tests.py — run every tests/ui suite and enforce its PASS count (M79-T8).

    py -3.12 agent/tests/ui/run-tests.py          (python3 on Linux)
    py -3.12 agent/tests/ui/run-tests.py --list   the suites and their expected counts

Same discipline as tests/usage/: each test_*.py here must print exactly the number of PASS
lines listed in expected.txt (NAME COUNT). A different count, a suite not listed, a listed
suite that did not run, or a non-zero exit fails the run.

A suite may instead print "NOTRUN <reason>" and exit 0 to declare it could not run (e.g. no
browser installed). That is a VISIBLE skip: it never counts as a pass, it is reported in the
summary line, and SKIPS_ARE_FAILURE (default False) can make it fail the run.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# A skipped suite (NOTRUN) fails the run when True. Flip deliberately; do not use it to hide gaps.
SKIPS_ARE_FAILURE = False


def expected():
    out = {}
    for i, ln in enumerate(open(os.path.join(HERE, "expected.txt"), encoding="utf8").read().splitlines(), 1):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        p = s.split()
        if len(p) != 2 or not p[1].isdigit():
            print(f"expected.txt: bad line {i}: {ln!r}")
            sys.exit(1)
        out[p[0]] = int(p[1])
    return out


def main():
    exp = expected()
    if "--list" in sys.argv:
        for name, n in sorted(exp.items()):
            print(f"{name}: {n}")
        return

    suites = sorted(n for n in os.listdir(HERE) if n.startswith("test_") and n.endswith(".py"))
    ran = {}
    skipped = []
    failed = False
    for s in suites:
        r = subprocess.run([sys.executable, os.path.join(HERE, s)], capture_output=True, text=True)
        lines = r.stdout.splitlines()
        notrun = next((ln for ln in lines if ln.startswith("NOTRUN")), None)
        passes = sum(1 for ln in lines if ln.startswith("PASS"))
        ran[s] = passes
        if notrun is not None and r.returncode == 0:
            skipped.append((s, notrun.split(None, 1)[1] if len(notrun.split()) > 1 else "?"))
            print(f"SKIP {s}: {notrun} (expected {exp.get(s)} checks NOT executed)")
        elif r.returncode != 0 or passes != exp.get(s):
            failed = True
            print(f"FAIL {s}: exit={r.returncode} passes={passes} expected={exp.get(s)}")
            for ln in (r.stdout + r.stderr).splitlines()[-20:]:
                print("   ", ln)
        else:
            print(f"ok {s}: {passes}/{exp[s]}")

    for name in exp:
        if name not in ran:
            failed = True
            print(f"FAIL listed suite did not run: {name}")

    if skipped and SKIPS_ARE_FAILURE:
        failed = True
        for s, why in skipped:
            print(f"FAIL skip not allowed: {s} ({why})")

    if failed:
        print("[tests/ui] FAIL")
        sys.exit(1)
    if skipped:
        print(f"[tests/ui] PASS with {len(skipped)} SKIP: " + ", ".join(f"{s}({w})" for s, w in skipped))
    else:
        print("[tests/ui] PASS")


if __name__ == "__main__":
    main()
