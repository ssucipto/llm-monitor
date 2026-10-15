#!/usr/bin/env bash
# ci-validate.sh — validate the CI runtime matrix itself (ci.yml) is well-formed.
# Referenced by agent/scripts/acp.ci-steps.sh (_ci_step_ci_validate).
# Zero network/git side effects.

set -euo pipefail
trap 'echo "[ci-validate] Error on line ${LINENO}" >&2; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CI_YAML="${PROJECT_ROOT}/agent/configurables/ci.yml"

if [[ ! -f "${CI_YAML}" ]]; then
  echo "ci-validate.sh: agent/configurables/ci.yml not found" >&2
  exit 1
fi

python3 - "$CI_YAML" <<'PY'
import sys, re
text = open(sys.argv[1], encoding="utf-8").read()
# Reuse the ci.yml shape check: every tier step id must be declared under steps:.
tiers, steps, section, cur_tier, cur_step = {"static":[],"fast":[],"full":[]}, set(), None, None, None
for raw in text.splitlines():
    line = raw.rstrip()
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    if re.match(r"^tiers:\s*$", line): section="tiers"; continue
    if re.match(r"^steps:\s*$", line): section="steps"; continue
    if section=="tiers":
        m=re.match(r"^  (static|fast|full):\s*$", line)
        if m: cur_tier=m.group(1); continue
        m=re.match(r"^    - (\S+)\s*$", line)
        if m and cur_tier: tiers[cur_tier].append(m.group(1)); continue
    if section=="steps":
        m=re.match(r"^  ([a-z0-9-]+):\s*$", line)
        if m: steps.add(m.group(1)); continue
undeclared=[t for t in (tiers["static"]+tiers["fast"]+tiers["full"]) if t not in steps]
if undeclared:
    print(f"ci.yml references step ids not declared under steps:: {sorted(set(undeclared))}")
    raise SystemExit(1)
if not any(tiers.values()):
    print("ci.yml declares no tier steps — refuse (empty plan cannot gate)")
    raise SystemExit(1)
print(f"ci.yml OK: {len(steps)} steps declared, tiers static/fast/full = {len(tiers['static'])}/{len(tiers['fast'])}/{len(tiers['full'])}")
PY
