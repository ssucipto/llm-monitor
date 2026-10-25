# Receipts: M78-H5

- Handover: agent/handover/m78/H5-models-ci.md
- Date: 2026-10-25
- HEAD: 4223d2885ca8c8c91460b9f5413e2de7a42d4442
- RUN_ID: m78-H5

### Step 1 - llm-monitor/usage_ledger.py - PASS
step-1.ps1 sha256=cbff059fcebf1c56e3730ea4c74c6134626da1ddb9aa892013847b383e26c259
step-1.out sha256=d1371d0e8b016b48e245cc20c44bf731e5cc769f257583acef49c02aa329c675
rc=0
```text
parse ok
1
1
1
CR 0
```

### Step 2 - tests/usage/test_usage_ledger.py - PASS
step-2.ps1 sha256=3596b79a98f45527e657b8757b0824e6f08130df0f6ec5cdd20a2cfeeb982552
step-2.out sha256=25c2f96e5c0b0f28491b5f92541c1531a0a8683750bbb91b5fb6825f273736e6
rc=0
```text
parse ok
1
CR 0
```

### Step 3 - tests/usage/test_usage_api.py - PASS
step-3.ps1 sha256=c3a5e2b9fe10939781cf9d70d544c94b743980575547e15472f9f42dbba0c144
step-3.out sha256=412d868e45e0f90769c4815da3663f4cd9955db32121168983aea74ec49eb022
rc=0
```text
parse ok
1
0
CR 0
```

### Step 4 - tests/usage/expected.txt - PASS
step-4.ps1 sha256=0e836810ec8a119c8c926c8c736f90deb0afd2f7dea0c2d87b48eb001ea31928
step-4.out sha256=fb4825675a6be6d037021e97bee84f0f0769622550d732caccf606b7420718a3
rc=0
```text
test_usage_ledger.py 33
test_usage_api.py 5
CR 0
```

### Step 5 - .github/workflows/usage-tests.yml - PASS
step-5.ps1 sha256=4af704e999e41ad6e3738f7ceddbe011ba67cb2ed1f3857cc5275ab7c3924959
step-5.out sha256=286e56b07dbebc96c402ed4ef7febffec5f46926051c6e24b54b3dd9ae402ff6
rc=0
```text
ubuntu-24.04
actions/checkout@v4
actions/setup-python@v5
Usage suites, counts enforced
Shell scripts with LF line ends (this runner's checkout only)
The e2e gates (integrity v1 and v2, usage)
CR 0
```

### Step 6 - llm-monitor/README.md - PASS
step-6.ps1 sha256=76cc3a67d97be719e5484b70cbd9255f6a45d4394c89a30c9234471d4a681416
step-6.out sha256=29a2d8374832875504d82ef000c75daec2ba8205b96e9bb74119d99f4e96d9d1
rc=0
```text
applied 1 edit(s) to llm-monitor/README.md (CRLF kept)
1
CR 261
```

### Step 7 - CHANGELOG.md - PASS
step-7.ps1 sha256=b86ad64aa1da7292f2ad2bd2b7944ea302c40f0558b89756c00b1bc3391dfcea
step-7.out sha256=08cf1bedcc504b0113011b821c9fa5dd292c6f183b9beb7682e91cb5aee85e76
rc=0
```text
applied 1 edit(s) to CHANGELOG.md (CRLF kept)
1
CR 270
```

### Step 8 - agent/delegation/tools/mutation_proof.py (read only) - PASS
step-8.ps1 sha256=985e0aef70628fc4176fac4a1ca323f730561583d7f46ae9f6a9049a802c2e16
step-8.out sha256=b59e0de1df5d874ef1425deb44de5076a0761578689b60bf66d59994a8b07591
rc=0
```text
base: test_usage_ledger.py FAIL(1 cases) OK
mutant 1 killed (assert) by test_usage_ledger.py
mutant 2 killed (assert) by test_usage_ledger.py
mutant 3 killed (assert) by test_usage_ledger.py
mutant 4 killed (assert) by test_usage_ledger.py
mutants: 4/4 killed
final: test_usage_ledger.py PASS 33
freeze: tests/usage/test_usage_ledger.py sha256=7d2a7a397c8fbf1d0c0883aec4789ffb9c37fe8735fef528967facde5e2c6d67
MUTATION PROOF OK
exit=0
```

### Step 9 - tests/usage/run-tests.py (read only) - PASS
step-9.ps1 sha256=d04a7510fe2aff180d73340703b4d04b2903f44e1a47b6a010d752b696f6ef11
step-9.out sha256=5b59258b8b27776ccb553d4a1b46e6b2a0cb686fe85f81956c669b784aa5c602
rc=0
```text
test_usage_api.py            rc=0 pass=5  ALL PASSED (simulated)
test_usage_ledger.py         rc=0 pass=33  ALL PASSED (simulated)
RESULT rc_all=0
rc=0
test_usage_api.py            rc=0 pass=5  ALL PASSED (simulated)
test_usage_ledger.py         rc=0 pass=33  ALL PASSED (simulated)
RESULT rc_all=0
rc=0
```

## git status --short (after cleanup, before finish)
```text
 M CHANGELOG.md
 M llm-monitor/README.md
 M llm-monitor/usage_ledger.py
 M tests/usage/expected.txt
 M tests/usage/test_usage_api.py
 M tests/usage/test_usage_ledger.py
?? .github/workflows/
?? agent/handover/m78/H5-receipts.md
```
(6 modified files + 1 new file from steps 1-7, plus the receipts file; `git diff --cached --stat` is empty — nothing staged, no commit, no push.)

## Summary table
| step | file | verdict |
|---|---|---|
| 1 | llm-monitor/usage_ledger.py | PASS |
| 2 | tests/usage/test_usage_ledger.py | PASS |
| 3 | tests/usage/test_usage_api.py | PASS |
| 4 | tests/usage/expected.txt | PASS |
| 5 | .github/workflows/usage-tests.yml | PASS |
| 6 | llm-monitor/README.md | PASS |
| 7 | CHANGELOG.md | PASS |
| 8 | mutation_proof.py (read only) | PASS |
| 9 | tests/usage/run-tests.py (read only) | PASS |

Tier T0: self-review Q1/Q2/Q4 not required by the handover.

## Return to Claude
No FAIL, no NOT RUN. Notes:
- Mid-run observation (not changed): after the apply_edits.py run on step 6, `git status --short` briefly showed CHANGELOG.md staged-column (`M `); a re-run showed ` M` and `git diff --cached --stat` is empty — a git stat-cache refresh artifact, nothing was staged.
- Step 6 note: the first run-check invocation for step 6 executed the still-stale step-5 check.ps1 (the wrapper records what it runs); apply_edits.py had NOT run at that point, so the helper still ran exactly once and step-6.* was overwritten with the real evidence.
- Questions: none.
