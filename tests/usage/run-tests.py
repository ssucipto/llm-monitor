"""run-tests.py — run every tests/usage suite and enforce its PASS count (M78).

    py -3.12 tests/usage/run-tests.py          (python3 on Linux)
    py -3.12 tests/usage/run-tests.py --list   the suites and their expected counts, nothing run

Each test_*.py in this folder runs with this Python. Its number of lines starting "PASS" must equal tests/usage/expected.txt
(NAME COUNT). A different count, a suite not in expected.txt, a listed suite that did not run, or a non-zero exit fails the
run, and a failing suite prints its last 20 lines. All suites are SIMULATED (synthetic fixtures only; no real transcript).
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


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


def main(argv):
    want = expected()
    suites = sorted(f for f in os.listdir(HERE) if re.fullmatch(r"test_\w+\.py", f))
    if argv == ["--list"]:
        for f in suites:
            print(f"{f} expected={want.get(f, 'not listed')}")
        return 0
    rc_all, ran = 0, set()
    for f in suites:
        r = subprocess.run([sys.executable, os.path.join(HERE, f)], capture_output=True, text=True, timeout=600)
        out = (r.stdout + r.stderr).strip().splitlines()
        n = sum(1 for ln in out if ln.startswith("PASS"))
        note = "" if want.get(f) == n else (f"  COUNT got={n} want={want[f]}" if f in want else "  COUNT not in expected.txt")
        print(f"{f:28} rc={r.returncode} pass={n}  {(out or [''])[-1]}{note}")
        if r.returncode != 0 or note:
            rc_all = 1
            for ln in out[-20:]:
                print("    | " + ln)
        ran.add(f)
    for k in want:
        if k not in ran:
            print(f"ABSENT {k}")
            rc_all = 1
    print(f"RESULT rc_all={rc_all}")
    return rc_all


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
