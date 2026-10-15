#!/usr/bin/env bash
# acp.integrity-v2.test.sh — e2e gate for /acp-integrity Phase 2 prep scripts.
# Verifies the taint + memory preparatory scripts exist, parse, and run without
# crashing on the project. Phase-2 findings themselves are LLM-gated (REQUIRES_HUMAN_REVIEW)
# and are NOT asserted here — only that the deterministic prep harness is healthy.

set -euo pipefail
trap 'echo "[acp.integrity-v2.test] Error on line ${LINENO}" >&2; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SCAN_DIR="${PROJECT_ROOT}/agent/scripts"

for s in acp.taint-scan.sh acp.memory-scan.sh; do
  if [[ ! -f "${SCAN_DIR}/${s}" ]]; then
    echo "FAIL: Phase-2 prep script missing: ${s}" >&2
    exit 1
  fi
  bash -n "${SCAN_DIR}/${s}"
done

# Prep scripts run but must not crash; findings are advisory (human review).
bash "${SCAN_DIR}/acp.taint-scan.sh" "${PROJECT_ROOT}/llm-monitor" >/dev/null 2>&1 || {
  echo "FAIL: acp.taint-scan.sh exited non-zero" >&2; exit 1; }

echo "acp.integrity-v2.test.sh: PASS (Phase-2 prep scripts present, parse, run)"
