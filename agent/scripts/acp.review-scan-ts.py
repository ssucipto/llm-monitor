#!/usr/bin/env python3
# acp.review-scan-ts.py — Phase 1 TypeScript/JavaScript rule analyzer (M83 task-282 / F-105-02)
#
# Character-walker that strips comments and string literals BEFORE regex matching.
# This is NOT an AST or tree-sitter analyzer (F-105-02): rules cannot reason about
# scope, types, imports, or control flow. It implements exactly the Phase 1 TS/JS
# rules invoked by agent/scripts/acp.review-scan.sh:
#   EH-01 async fn must have try/catch or .catch() handler  (HIGH)
#   EH-02 catch blocks must not be empty                     (HIGH)
#   SC-01 no hardcoded secrets/tokens/passwords/API keys     (CRITICAL)
#   TS-01 no `any` in params, return types, var decls        (HIGH)
#   TS-02 exported functions need explicit return type       (HIGH)
#   AP-01 success responses use { data: T, meta?: M } envelope (HIGH)
#   NC-01 variables and functions must be camelCase          (MEDIUM)
#
# Contract: reads the file named in ACP_REVIEW_FILE, prints one finding per line as
#   filepath<TAB>line_num<TAB>rule_id<TAB>message<TAB>severity
# to stdout. Exits 0 always (findings are data, not control flow). Mirrors the
# line-based output convention of agent/scripts/acp.entropy-scan.sh --review-sc01.

import os
import re
import sys

filepath = os.environ.get("ACP_REVIEW_FILE", "")


def strip_comments_and_strings(src: str) -> str:
    """Blank out comment and string-literal spans, preserving line offsets.

    Newlines inside stripped spans are kept so line numbers stay aligned; every
    other stripped character becomes a space so column positions stay aligned.
    This keeps regexes from matching text that only appeared in a comment or a
    string (F-103-01)."""
    out = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        # line comment
        if c == "/" and nxt == "/":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        # block comment
        if c == "/" and nxt == "*":
            out.append(" ")
            out.append(" ")
            i += 2
            while i < n:
                if src[i] == "*" and (i + 1 < n) and src[i + 1] == "/":
                    out.append(" ")
                    out.append(" ")
                    i += 2
                    break
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            continue
        # string / template literal
        if c in "\"'`":
            quote = c
            out.append(" ")
            i += 1
            while i < n:
                ch = src[i]
                if ch == "\\":
                    out.append(" ")
                    i += 1
                    if i < n:
                        out.append("\n" if src[i] == "\n" else " ")
                        i += 1
                    continue
                if ch == quote:
                    out.append(" ")
                    i += 1
                    break
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def emit(line_num: int, rule: str, message: str, severity: str) -> None:
    print(f"{filepath}\t{line_num}\t{rule}\t{message}\t{severity}")


def main() -> None:
    try:
        raw = open(filepath, "r", encoding="utf-8", errors="ignore").read()
    except Exception as exc:  # noqa: bare handler is intentional for a scanner
        print(f"Error reading {filepath}: {exc}", file=sys.stderr)
        sys.exit(0)

    lines = raw.splitlines()
    code_lines = strip_comments_and_strings(raw).splitlines()

    # ── EH-01 / EH-02 — async handlers and empty catch blocks ────────────────
    # Track brace depth to find the body span of each async function.
    for idx, line in enumerate(code_lines):
        lineno = idx + 1
        # EH-01: async arrow/function declaration
        if re.search(r"\basync\b", line):
            # Look ahead to the end of this function for a handler.
            depth = 0
            started = False
            handled = False
            j = idx
            while j < len(code_lines):
                body = code_lines[j]
                for ch in body:
                    if ch == "{":
                        depth += 1
                        started = True
                    elif ch == "}":
                        depth -= 1
                if re.search(r"\btry\b", body) or re.search(r"\.catch\s*\(", body):
                    handled = True
                if started and depth <= 0:
                    break
                j += 1
            if not handled:
                emit(lineno, "EH-01", "async function without try/catch or .catch() handler", "HIGH")
        # EH-02: empty catch block on the same line
        m = re.search(r"\bcatch\b[^{]*\{\s*\}", line)
        if m:
            emit(lineno, "EH-02", "empty catch block — must log, rethrow, or return typed error", "HIGH")

    # ── SC-01 — hardcoded secrets (structured prefixes + obvious assignments) ─
    secret_prefix = re.compile(
        r"(ghp_|gho_|ghu_|ghs_|ghr_|xox[abpr]-|sk-[A-Za-z0-9]|AIza[0-9A-Za-z_-]{20,}|"
        r"AKIA[0-9A-Z]{16}|ya29\.|eyJ[A-Za-z0-9_-]{10,})"
    )
    secret_assign = re.compile(
        r"(?i)\b(api[_-]?key|apikey|secret|token|passwd|password|private[_-]?key|access[_-]?token)\b"
        r"\s*[:=]\s*[\"'][^\"']{8,}[\"']"
    )
    for idx, line in enumerate(lines):
        lineno = idx + 1
        if secret_prefix.search(line):
            emit(lineno, "SC-01", "hardcoded secret-like token prefix in source", "CRITICAL")
        elif secret_assign.search(line):
            emit(lineno, "SC-01", "hardcoded secret assignment in source", "CRITICAL")

    # ── TS-01 — `any` in params, return types, variable declarations ─────────
    for idx, line in enumerate(code_lines):
        lineno = idx + 1
        if re.search(r":\s*any\b", line) or re.search(r"\bas\s+any\b", line) \
                or re.search(r"\b<any>", line) or re.search(r"\bArray<any>", line):
            emit(lineno, "TS-01", "`any` in parameter/return/variable type — prefer a concrete type", "HIGH")

    # ── TS-02 — exported functions must have explicit return type annotations ─
    for idx, line in enumerate(code_lines):
        lineno = idx + 1
        m = re.search(r"\bexport\s+(async\s+)?(function|const|let|var)\b", line) or \
            re.search(r"\bexport\s+function\b", line)
        if not m:
            continue
        # a function-ish export that is an arrow or declaration needs `-> Type`
        looks_like_fn = re.search(r"\)", line) and (
            re.search(r"=>", line) or re.search(r"\bfunction\b", line)
        )
        if looks_like_fn and not re.search(r"\)\s*:\s*[A-Za-z_<>[\]|&]", line):
            emit(lineno, "TS-02", "exported function missing explicit return type annotation", "HIGH")

    # ── AP-01 — success response envelope { data: T, meta?: M } ──────────────
    for idx, line in enumerate(code_lines):
        lineno = idx + 1
        if re.search(r"\breturn\b[^;]*\{\s*(?!\s*data\s*:)", line) and \
                re.search(r"\b(sendJson|respond|jsonSend)\b", line):
            emit(lineno, "AP-01", "success response missing { data: T, meta?: M } envelope", "HIGH")

    # ── NC-01 — variables and functions must be camelCase (flag snake_case) ───
    for idx, line in enumerate(code_lines):
        lineno = idx + 1
        for m in re.finditer(
            r"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)", line
        ):
            name = m.group(1)
            if re.search(r"_", name) and not name.isupper():
                emit(lineno, "NC-01", f"identifier `{name}` is snake_case — use camelCase", "MEDIUM")
        for m in re.finditer(r"\bfunction\s+([A-Za-z_$][A-Za-z0-9_$]*)", line):
            name = m.group(1)
            if re.search(r"_", name) and not name.isupper():
                emit(lineno, "NC-01", f"function `{name}` is snake_case — use camelCase", "MEDIUM")


main()
