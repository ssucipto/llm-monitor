#!/usr/bin/env python3
# acp.taint-scan.py — Taint source/sink extractor + heuristic obvious-sink detector
# (M58 / acp-integrity Phase 2 prep, IG-45–IG-50)
#
# This is the DETERMINISTIC PREP layer only. Cross-file taint flow needs SAST-grade
# reasoning and is LLM-gated in Phase 2 (verdict: REQUIRES_HUMAN_REVIEW). The script
# here does two things, per agent/wiki/integrity-rules.md:
#   1. EXTRACT taint SOURCES and SINKS as data (never asserted as findings):
#        <file>:<line> SOURCE <desc>
#        <file>:<line> SINK <desc>
#   2. Heuristic OBVIOUS-SINK detection — a source and a sink on the SAME line, or
#      an inline interpolation into an exec/query/path/redirect sink. These are the
#      only lines promoted to finding records by acp.taint-scan.sh (IG-45–IG-49).
#
# Output contract consumed by acp.taint-scan.sh:
#   <file>:<line>:IG-NN:<message>          -> finding record (heuristic obvious sink)
#   <file>:<line> SOURCE <desc>            -> prep data (printed, not a finding)
#   <file>:<line> SINK <desc>              -> prep data (printed, not a finding)
#   ACP_FINDING_COUNT=<n>                  -> machine summary
#   ACP_MARKER_COUNT=<n>                   -> machine summary
# The .sh wrapper strips the ACP_* lines and routes the rest. Exit 0 always: findings
# are data, control flow is not (the .sh decides severity/CI via ig_finalize_scan).

import os
import re
import sys

target = os.environ.get("ACP_TARGET", "")

SOURCES = [
    # (regex, description)
    (re.compile(r"\binput\s*\("), "input() read from user"),
    (re.compile(r"\bsys\.argv\b|\bargv\[|\bprocess\.argv\b"), "command-line argument"),
    (re.compile(r"\brequest\.(json|form|query|body|args)\b|\breq\.(json|body|params|query)\b"), "HTTP request body/param"),
    (re.compile(r"\b(os\.environ|getenv|process\.environ|process\.env)\b[\[\.(]"), "environment variable"),
    (re.compile(r"\b(stdin|sys\.stdin|readline\s*\()"), "standard input"),
    (re.compile(r"\bfetch\(|\.json\(\)|requests\.(get|post)\b"), "network response body"),
]

SINKS = [
    # (regex, ig_rule, description)
    (re.compile(r"\b(cursor\.execute|cursor\.executescript|execute\s*\(|\.query\s*\(|SELECT |INSERT |UPDATE |DELETE )"), "IG-45", "SQL/NoSQL query sink"),
    (re.compile(r"\b(subprocess\.(run|call|check_output|Popen)|os\.system|os\.popen|child_process|exec\s*\(|spawn|shell\s*=\s*True)\b"), "IG-46", "shell/command execution sink"),
    (re.compile(r"\b(open\s*\(|os\.path\.join|shutil\.(copy|rmtree|move)|Path\s*\(|sendfile|serve|StaticFile)\b"), "IG-47", "filesystem path sink"),
    (re.compile(r"\b(redirect|Location|30[1-9]|window\.location|set ?header.*location|Set-Cookie)\b", re.IGNORECASE), "IG-48", "URL redirect sink"),
    (re.compile(r"\b(urlopen|requests\.(get|post)|http[s]?\.request|fetch\(|axios|curl)\b"), "IG-49", "network call sink"),
]

# An "obvious" same-line taint: a source token and a sink token co-occur on one
# line, OR an f-string/%-format/interpolation feeds a sink directly. This is a
# deliberately conservative single-line heuristic; multi-line flows are left to
# the LLM Phase-2 pass (we do NOT claim them here).
INTERP = re.compile(r"\bf[\"']|%\s*\(|\$\{|\bformat\s*\(|\+\s*\w+\s*\+|%\s*\w+")


def scan_line(text: str):
    """Return (has_source, has_sink_rule, has_interp)."""
    has_source = any(rx.search(text) for rx, _ in SOURCES)
    sink_rule = None
    for rx, rule, _ in SINKS:
        if rx.search(text):
            sink_rule = rule
            break
    has_interp = bool(INTERP.search(text))
    return has_source, sink_rule, has_interp


def emit(rel: str, line_no: int, kind: str, desc: str) -> None:
    print(f"{rel}:{line_no} {kind} {desc}")


def emit_finding(rel: str, line_no: int, rule: str, message: str) -> None:
    print(f"{rel}:{line_no}:{rule}:{message}")


def main() -> None:
    finding_count = 0
    marker_count = 0

    if not target or not os.path.exists(target):
        # Nothing to scan is not a crash; emit empty summary and exit clean.
        print(f"ACP_FINDING_COUNT={finding_count}")
        print(f"ACP_MARKER_COUNT={marker_count}")
        return

    files = []
    if os.path.isfile(target):
        files = [target]
    else:
        for root, dirs, fnames in os.walk(target):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", ".venv", "venv", "__pycache__"}]
            for fn in fnames:
                if fn.endswith((".py", ".js", ".ts", ".tsx", ".mjs", ".cjs", ".sh")):
                    files.append(os.path.join(root, fn))

    root_parent = os.path.dirname(target) if os.path.isdir(target) else ""
    for path in sorted(files):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                lines = fh.readlines()
        except Exception:
            continue
        rel = path
        if root_parent and path.startswith(root_parent):
            rel = path[len(root_parent):].lstrip("/\\")
        for idx, line in enumerate(lines, start=1):
            stripped = line.rstrip("\n")
            # Skip obvious comment lines for the finding heuristic (comments are
            # not executable sinks); still record nothing from them.
            code = stripped.lstrip()
            is_comment = code.startswith("#") or code.startswith("//") or code.startswith("*")
            has_source, sink_rule, has_interp = scan_line(stripped)
            if has_source:
                emit(rel, idx, "SOURCE", next(d for rx, d in SOURCES if rx.search(stripped)))
                marker_count += 1
            if sink_rule:
                emit(rel, idx, "SINK", f"{sink_rule} {next(d for rx, r, d in SINKS if rx.search(stripped) and r == sink_rule)}")
                marker_count += 1
            if not is_comment and sink_rule and (has_source or has_interp):
                desc = next(d for rx, r, d in SINKS if rx.search(stripped) and r == sink_rule)
                emit_finding(rel, idx, sink_rule, f"obvious same-line taint into {desc}")
                finding_count += 1

    print(f"ACP_FINDING_COUNT={finding_count}")
    print(f"ACP_MARKER_COUNT={marker_count}")


main()
