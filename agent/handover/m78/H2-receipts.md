# Receipts: M78-H2 usage ledger

- handover: agent/handover/m78/H2-usage-ledger.md
- date: 2026-10-25
- HEAD: 0288055111dbe159b4a138ff68aad51651ef73d1
- RUN_ID: m78-H2

## Start checks (before step 1)

`git rev-parse HEAD` -> 0288055111dbe159b4a138ff68aad51651ef73d1 (drift line: one commit after git_commit 2f2aeb8, only this handover file)

```text
$ git diff --stat 2f2aeb8 HEAD
 agent/handover/m78/H2-usage-ledger.md | 270 ++++++++++++++++++++++++++++++++++
 1 file changed, 270 insertions(+)
$ git status --short
(empty)
```

Note: check.ps1 is written with a UTF-8 BOM so Windows PowerShell 5.1 reads the em-dash pattern in step 1's Check block as UTF-8 (without it, Select-String decodes ANSI cp1252 and the version-line count reads 0). The block content itself is verbatim.

### Step 1 - llm-monitor/usage_ledger.py - PASS
step-1.ps1 sha256=ece6e82c45dad16d35493fd67e4db5822c118a6a3477316c2e3c84e410195d99
step-1.out sha256=c775f7ce4b0e27fdc5af7f344ecc912bac191732d46bf03067f61aeb0d20e1d5
rc=0

```text
parse ok
1
1
CR 0
```

Matches Expected (parse ok / 1 / 1 / CR 0).

### Step 2 - llm-monitor/usage_ledger.py - PASS
step-2.ps1 sha256=a3f09b75718fc92c0af812ba2649483d911b924dc657844f5a69f880ea7c1266
step-2.out sha256=c775f7ce4b0e27fdc5af7f344ecc912bac191732d46bf03067f61aeb0d20e1d5
rc=0

```text
parse ok
1
1
CR 0
```

Matches Expected (parse ok / 1 / 1 / CR 0).

### Step 3 - llm-monitor/usage_ledger.py - PASS
step-3.ps1 sha256=cc554923ffb6557ba0b22512a9f04d76bfdf2c945575832dc096f8d9edc220cb
step-3.out sha256=4ae5d72177de8e1251d0ad40bb2660a8ffec5f6da708849961736e5c402f4abc
rc=0

```text
parse ok
1
1
test_usage_ledger.py         rc=0 pass=24  ALL PASSED (simulated)
RESULT rc_all=0
rc=0
CR 0
```

Matches Expected. Fix rounds used: 2 of the allowed 3 (code only, never the test): (1) `os.walk` loop variable shadowing in ingest_claude (TypeError on os.path.join); (2) ambiguous count columns in the Hermes JOIN — both sessions and session_model_usage carry input_tokens/output_tokens/cache_read_tokens, so the SELECT now qualifies them via table aliases. The last run is the evidence (earlier step-3 captures were overwritten).

### Step 4 - D:\Project\Homelab\agent\delegation\tools\mutation_proof.py - PASS
step-4.ps1 sha256=40fd0bbc76c712505540d61619d7e6ba20a1d0eeb0fb31013057c489c0e95c00
step-4.out sha256=23e33dae7217eb68d4a8f00f3a4af4ce3b9a9e867b027422e719d3649db0ea54
rc=0

```text
base: test_usage_ledger.py skipped (--no-base: new code, only the mutants prove the tests)
mutant 1 killed (assert) by test_usage_ledger.py
mutant 2 killed (assert) by test_usage_ledger.py
mutant 3 killed (assert) by test_usage_ledger.py
mutant 4 killed (assert) by test_usage_ledger.py
mutant 5 killed (assert) by test_usage_ledger.py
mutants: 5/5 killed
final: test_usage_ledger.py PASS 24
freeze: tests/usage/test_usage_ledger.py sha256=70b40e72b0a5804da3c277f94fed6b5c59ef068fc519f5f76dfbb4027b6cfd93
MUTATION PROOF OK
exit=0
```

Matches Expected exactly, including the freeze line (sha256 matches the test file's hash taken before this step: 70b40e72...b6cfd93). The whole output with the freeze line is pasted above as required.

### Step 5 - tests/usage/run-tests.py - PASS
step-5.ps1 sha256=085292f9634cc8d354982bdbd76072c232a8202667d1b7378c2bd3bca128cabf
step-5.out sha256=40f3d8f86b31af943eb811f15bdbfe48fbefe9f5f85468f6b411ee9da5b0ec8a
rc=0

```text
test_usage_ledger.py         rc=0 pass=24  ALL PASSED (simulated)
RESULT rc_all=0
run1 rc=0
test_usage_ledger.py         rc=0 pass=24  ALL PASSED (simulated)
RESULT rc_all=0
run2 rc=0
```

Matches Expected. The two runs are identical — no flake.

## Self-review (tier T1)

- Q1: no (llm-monitor/usage_ledger.py:54) — a missing Hermes DB returns status "missing" and a broken one "error: schema"/"error: locked" (lines 67-71), never zeros; summary turns a non-"ok" source into a None block (lines 199-200), never an empty block.
- Q2: no (llm-monitor/usage_ledger.py:111) — the budget_s time cap sets partial=True and is reported in the summary's "partial" field (line 213); it is never treated as having read everything.
- Q4: no (llm-monitor/usage_ledger.py:100) — this handover adds no auto action: every ingest/query runs only when a caller invokes it (H3 wires the dashboard), and each behaviour is gated by and covered in tests/usage/test_usage_ledger.py (24 cases, frozen at step 4).

## Finish

Cleanup: agent/scratch-m78 deleted (handover Permission); agent/delegation/runs/m78-H2 kept as evidence (captures live under D:\Project\Homelab\agent\delegation\runs\m78-H2).

git status --short:

```text
?? agent/handover/m78/H2-receipts.md
?? llm-monitor/usage_ledger.py
```

Exactly the two expected files: the module and the receipts. No commit, no push.

| step | file | verdict |
|------|------|---------|
| 1 | llm-monitor/usage_ledger.py | PASS |
| 2 | llm-monitor/usage_ledger.py | PASS |
| 3 | llm-monitor/usage_ledger.py | PASS |
| 4 | D:\Project\Homelab\agent\delegation\tools\mutation_proof.py | PASS |
| 5 | tests/usage/run-tests.py | PASS |

## Return to Claude

No FAIL, no NOT RUN. Notes, nothing changed beyond the permission:
- check.ps1 needed a UTF-8 BOM for step 1's em-dash Select-String pattern under Windows PowerShell 5.1 (system ACP is 1252): without it the version-line count reads 0 even though the file itself is BOM-less UTF-8 and correct. Worth knowing for future handovers whose Check blocks contain non-ASCII patterns; the check.ps1 content stays verbatim either way.
- The spec's Hermes SELECT lists unqualified column names; on a real state.db the JOIN makes input_tokens/output_tokens/cache_read_tokens ambiguous (both tables carry them), so the code qualifies them with table aliases — same columns, same semantics, required for the query to run at all.
- Questions: none.

Return to orchestrator.
