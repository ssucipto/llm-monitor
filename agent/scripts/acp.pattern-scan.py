#!/usr/bin/env python3
"""acp.pattern-scan.py — deterministic companion for acp.pattern-scan.sh.

Part of /acp-integrity v1.1 (M64 route-180). Rewritten 2026-11-13: the script
shipped since M64 referenced this file but it never existed in git history, so
the exfiltration/persistence category (IG-04, IG-07..IG-13, IG-21..IG-26) was
never deterministically enforced (audit-42 finding INT-01).

v1.0 contract (matches acp.integrity.md Category 9 policy for literal rules):
single-file, windowed pattern matching — grep-equivalent best effort. Cross-file
taint flow is IG-45..50 and deferred to v2.0; do not read clean output as proof
of absence.

Invariant per rule: a dangerous sink appears within the same file within the
rule's line window of its named source (or, for stateless rules, on any line).
False-positive controls: default path exclusions shared with review-scan, and
inline suppression `acp-integrity-ignore: IG-XX - reason` on the finding line
or the line above (reason required; missing reason does not suppress).

Output contract: one `file:line:IG-XX:message` per finding, then
`ACP_FINDING_COUNT=N`. Severity is assigned by acp.integrity-output.sh.
"""
import os
import re
import sys

TARGET = os.environ.get("ACP_TARGET", ".")

EXCLUDE_PARTS = re.compile(r"(^|[\\/])(\.git|node_modules|__pycache__|\.venv)([\\/]|$)")
EXCLUDE_NAME = re.compile(r"(test|spec|fixture|__mocks__|\.generated\.|\.min\.js)", re.I)
CODE_EXT = (".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs", ".py", ".sh", ".ps1")

NET = re.compile(r"(fetch\s*\(|https?\.request\s*\(|urlopen\s*\(|requests\.(get|post|put|delete)\s*\(|httpx\.|curl_exec\s*\()")
SECRETISH = r"(auth_token|api_key|apikey|access_token|client_secret|secret_key)"
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASS|CRED|AUTH)", re.I)

# (rule, regex, message, window_lines_after_source) — window 0 = single line only
RULES = [
    ("IG-04", re.compile(r"\b(eval|new\s+Function)\s*\(\s*(res|response|data|body|payload|content|fetched|html|srcdoc|script_text)\b"),
     "eval()/Function() of network-response-shaped data", 0),
    ("IG-07", re.compile(r"(process\.env\.([A-Za-z_]+)|environ\[|getenv\(\s*)"),
     "secret-named environment read within window of a network call (possible env exfiltration)", 12),
    ("IG-08", re.compile(r"(\.readFileSync?\s*\(|\.read_text\s*\(|\.read_bytes\s*\()"),
     "file read within window of a network call (possible file exfiltration)", 12),
    ("IG-09", re.compile(r"(clipboard\.readText|pyperclip\.paste|Get-Clipboard)"),
     "clipboard read within window of a network call", 12),
    ("IG-10", re.compile(r"(localStorage\.getItem|sessionStorage\.getItem)"),
     "web storage read within window of a network call", 12),
    ("IG-11", re.compile(rf"({SECRETISH}).*?(console\.(log|info|debug)|print\s*\(|url\s*=\s*[\"'`][^\"'`]*\{{)|(https?://[^\"'`\s]*[?&](key|token|api_key)=)"),
     "credential-like value logged or embedded in a URL", 0),
    ("IG-13", re.compile(r"(desktopCapturer|ImageGrab\.grab|mss\.mss\s*\(|screencapture)"),
     "screen-capture API within window of a network call (verify feature context)", 20),
    ("IG-21", re.compile(r"((child_process\.)?(exec|execSync)|subprocess\.(run|call|Popen|check_output|check_call))\s*\(\s*(f?['\"`][^'\"`]*(\$\{|%s|\"\s*\+|'\s*\+))"),
     "dynamic (interpolated) command passed to a shell-exec sink", 0),
    ("IG-22", re.compile(r"(writeFile|write_text|write_bytes|open\s*\([^)]*[\"'][wWaA])"),
     "file write within window of a system path", 6),
    ("IG-23", re.compile(r"(crontab\s+-|schtasks\s+/create|systemctl\s+(enable|link)|launchctl\s+load)"),
     "persistence: scheduled task / service registration", 0),
    ("IG-24", re.compile(r"(process\.argv\[1\]|__file__|sys\.argv\[0\])"),  # acp-integrity-ignore: IG-24 - pattern definition literal, not a sink
     "self-path reference within window of a write sink (possible self-modification)", 6),
    ("IG-25", re.compile(r"(\brequire\s*\(\s*[^'\"()\s]|\bawait\s+import\s*\(\s*[^'\"]|importlib\.import_module\s*\(\s*[^'\"]\w)"),
     "dynamic require()/import() with non-literal module", 0),
    ("IG-26", re.compile(r"(ptrace|VirtualAllocEx|WriteProcessMemory|LD_PRELOAD)"),  # acp-integrity-ignore: IG-26 - pattern definition literal, not a sink
     "process-injection primitive", 0),
]

SYS_PATH = re.compile(r"(/etc/|C:\\+Windows|~/.bashrc|~/.profile|/usr/local/bin|/root/)")
IGNORE = re.compile(r"acp-integrity-ignore:\s*(IG-\d+)\s*-\s*\S")  # reason required


def iter_files(root):
    if os.path.isfile(root):
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not EXCLUDE_PARTS.search(os.path.join(dirpath, d))]
        for name in filenames:
            p = os.path.join(dirpath, name)
            if p.endswith(CODE_EXT) and not EXCLUDE_NAME.search(name):
                yield p


def scan_file(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return
    for idx, line in enumerate(lines):
        if IGNORE.search(line):
            continue
        prev = lines[idx - 1] if idx else ""
        for rule, rx, msg, window in RULES:
            m = rx.search(line)
            if not m:
                continue
            if f"acp-integrity-ignore: {rule} -" in line or f"acp-integrity-ignore: {rule} -" in prev:
                continue
            if rule == "IG-22" and not any(SYS_PATH.search(l) for l in lines[max(0, idx - 3): idx + window]):
                continue
            if rule == "IG-24" and not any(re.search(r"(writeFile|write_text|write_bytes|open\s*\([^)]*[\"'][wWaA])", l)
                                           for l in lines[max(0, idx - window): idx + 1]):
                continue
            if rule in ("IG-07", "IG-08", "IG-09", "IG-10", "IG-13"):
                if not any(NET.search(l) for l in lines[idx + 1: idx + window + 1]):
                    continue
            if rule == "IG-07":
                name = m.group(1) or lines[idx]
                if not SECRET_NAME.search(name):
                    continue
            yield f"{path}:{idx + 1}:{rule}:{msg}"


def main():
    count = 0
    for f in iter_files(TARGET):
        for finding in scan_file(f):
            print(finding)
            count += 1
    print(f"ACP_FINDING_COUNT={count}")
    sys.exit(0)


if __name__ == "__main__":
    main()
