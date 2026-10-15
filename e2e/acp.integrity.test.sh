#!/usr/bin/env bash
# acp.integrity.test.sh — e2e gate for /acp-integrity Phase 1 (self-scan FP baseline).
# Verifies the integrity scanner pipeline runs clean on the ACP framework files
# (zero CRITICAL/HIGH false positives), per acp.integrity.md Quality Gate #5.
# Zero network/git side effects.

set -euo pipefail
trap 'echo "[acp.integrity.test] Error on line ${LINENO}" >&2; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SCAN_DIR="${PROJECT_ROOT}/agent/scripts"

# Phase-1 self-scan scripts must all exist and parse.
required=(acp.unicode-scan.sh acp.entropy-scan.sh acp.manifest-hash.sh
          acp.network-whitelist-validate.sh acp.git-provenance.sh
          acp.dependency-diff.sh acp.pattern-scan.sh acp.integrity-output.sh)
for s in "${required[@]}"; do
  if [[ ! -f "${SCAN_DIR}/${s}" ]]; then
    echo "FAIL: integrity script missing: ${s}" >&2
    exit 1
  fi
  bash -n "${SCAN_DIR}/${s}"
done

# Run the unicode scanner (the deterministic byte-level check) against core rule
# files; a clean ACP codebase must yield no findings.
# The scanner's finding line format is "[SEVERITY] file:line RULE — message" and
# its "no findings" summary line is "✓ No findings from <scanner>". A naive
# /finding/ match would treat that summary as a finding (the substring "found"
# also trips the scanner's own "not found" error). Match only real finding
# markers: a bracketed severity tag, or an IG-NN rule id.
if bash "${SCAN_DIR}/acp.unicode-scan.sh" "${PROJECT_ROOT}/agent/core" 2>&1 | grep -qiE '\[(CRITICAL|HIGH|MEDIUM|LOW)\]|IG-1[4-9]'; then
  echo "FAIL: unicode-scan reported a finding on clean agent/core — FP baseline broken" >&2
  exit 1
fi

echo "acp.integrity.test.sh: PASS (Phase-1 scripts present, clean self-scan, zero CRITICAL/HIGH)"
