#!/usr/bin/env bash
# run-e2e-tests.sh — top-level e2e runner for /acp-ci e2e-smoke + e2e-matrix steps.
# Runs the deterministic integrity e2e gates. --skip-network is accepted (default
# behavior; these tests already make zero network calls).

set -euo pipefail
trap 'echo "[run-e2e-tests] Error on line ${LINENO}" >&2; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}"

# accept (and ignore) --skip-network for parity with the ci-steps invocation
for arg in "$@"; do
  case "${arg}" in
    --skip-network) ;;
    *) echo "run-e2e-tests.sh: unknown arg ${arg}" >&2; exit 2 ;;
  esac
done

pass=0
for t in "${PROJECT_ROOT}/e2e/acp.integrity.test.sh" "${PROJECT_ROOT}/e2e/acp.integrity-v2.test.sh"; do
  if [[ -f "${t}" ]]; then
    bash "${t}"
    pass=$((pass + 1))
  else
    echo "run-e2e-tests.sh: e2e test missing: ${t}" >&2
    exit 1
  fi
done

echo "run-e2e-tests.sh: ${pass} e2e tests passed"
