# Receipts — M78-H4 (millisecond timestamps in the usage ledger)

- handover: agent/handover/m78/H4-ms-timestamps.md
- date: 2026-10-25
- HEAD: 020bbfd3bbed1cf14b61d69c8a13b45cd5c546bf (git_commit 93b967d8f2ddc0d9260ba081c065d2bc6a41b89a + drift commit adding only this handover; `git diff --stat 93b967d HEAD` lists only agent/handover/m78/H4-ms-timestamps.md; `git status --short` was empty before step 1)
- RUN_ID: m78-H4
- executor: strata-iq3s (headless Hermes)

### Step 1 - llm-monitor/usage_ledger.py - PASS
step-1.ps1 sha256=81ae683dd6fb8d5ecbb3ae00c57ab53131db1e676cfaf2973d536f81a20db560
step-1.out sha256=b168771cd52f428c2df1662f83a53e11c6b3ae9d409174d11266f993215d735e
rc=0

```text
parse ok
1
2
1
CR 0
```

Edits 1a-1d applied with the patch tool, each Find text matched exactly once (file is LF; CR count 0 confirms line endings kept).

### Step 2 - tests/usage/test_usage_ledger.py - PASS
step-2.ps1 sha256=bfef2fe11f0aa777eb88cf6061a38e893a500e16f0c1af6c67606842a5eed665
step-2.out sha256=25c2f96e5c0b0f28491b5f92541c1531a0a8683750bbb91b5fb6825f273736e6
rc=0

```text
parse ok
1
CR 0
```

Edit 2a applied with the patch tool; the Find line occurred exactly once; the block was copied verbatim from the handover.

### Step 3 - tests/usage/expected.txt - PASS
step-3.ps1 sha256=0e836810ec8a119c8c926c8c736f90deb0afd2f7dea0c2d87b48eb001ea31928
step-3.out sha256=11006be2506ea4470db24b68eced4d7b014a611bd999b756bdcac31011788502
rc=0

```text
test_usage_ledger.py 29
test_usage_api.py 4
CR 0
```

Edit 3a applied with the patch tool (anchor `test_usage_ledger.py 24` occurred exactly once; file is LF).

### Step 4 - CHANGELOG.md - PASS
step-4.ps1 sha256=81eafefd4271300b5dab4eda706058d3b524e7a13b214dd2b4cfcdc8f48b5971
step-4.out sha256=222723917a6576741a31c060c6703ec2f227a88af2f50cce41e9136d0c66270f
rc=0

```text
applied 1 edit(s) to CHANGELOG.md (CRLF kept)
1
CR 262
```

Edit 4a applied only by apply_edits.py (first and only run on this file; CRLF kept, CR count 262 matches Expected).

### Step 5 - D:\Project\Homelab\agent\delegation\tools\mutation_proof.py - PASS
step-5.ps1 sha256=9da2554c5cd9fa7d8a74f88c869e73cc08474985fa912003663c0f875b66a8f2
step-5.out sha256=a7ef053e37e5a7e73a17b8774d28e1c276de76f1980051c354022e9451f0239b
rc=0

```text
base: test_usage_ledger.py FAIL(5 cases) OK
mutant 1 killed (assert) by test_usage_ledger.py
mutant 2 killed (assert) by test_usage_ledger.py
mutant 3 killed (assert) by test_usage_ledger.py
mutant 4 killed (assert) by test_usage_ledger.py
mutant 5 killed (assert) by test_usage_ledger.py
mutants: 5/5 killed
final: test_usage_ledger.py PASS 29
freeze: tests/usage/test_usage_ledger.py sha256=ad546599a05952d00f054174d9324d754881b80c0be319ee520f50f80bbf1c59
MUTATION PROOF OK
exit=0
```

Whole output pasted (it is step-5.out verbatim; the terminal echo of my shell's own `exit=$?` after the wrapper is not part of the capture). The proof built and removed its own temp trees; no test, module or mutant was changed.

### Step 6 - tests/usage/run-tests.py - PASS
step-6.ps1 sha256=4f0fe7c2a59a17b1e889f7f4d9ac9cce6d79c2ad4d897decf775543f8759bdd7
step-6.out sha256=5b0f645dd01e5a048d62ddfb25b3b08681749005c1c556b892b273185c86da82
rc=0

```text
test_usage_api.py            rc=0 pass=4  ALL PASSED (simulated)
test_usage_ledger.py         rc=0 pass=29  ALL PASSED (simulated)
RESULT rc_all=0
rc=0
```

Read-only step: both usage suites, exact counts match Expected (4 and 29), rc_all=0.

## Finish

Cleanup: `rm -rf agent/scratch-m78` (deleted; `D:\Project\Homelab\agent\delegation\runs\m78-H4\` kept as evidence). No commit, no push. No process touched; 8080/8081/8090 untouched; usage.sqlite3 untouched; ~/.claude and the Hermes state.db never read.

`git status --short` at the end (matches Expected: the 4 modified files of steps 1-4, plus the receipts):

```text
 M CHANGELOG.md
 M llm-monitor/usage_ledger.py
 M tests/usage/expected.txt
 M tests/usage/test_usage_ledger.py
?? agent/handover/m78/H4-receipts.md
```

| Step | File | Verdict |
|------|------|---------|
| 1 | llm-monitor/usage_ledger.py | PASS |
| 2 | tests/usage/test_usage_ledger.py | PASS |
| 3 | tests/usage/expected.txt | PASS |
| 4 | CHANGELOG.md | PASS |
| 5 | mutation_proof.py (read only) | PASS |
| 6 | tests/usage/run-tests.py (read only) | PASS |

Self-review (tier is T0, so not required; answered anyway):
- Q1: no — an unparseable or zone-less timestamp returns None (usage_ledger.py:99-102) and the record is skipped and counted, never stored with no time and never reported as ok (usage_ledger.py:143-146); the repair only acts when the DELETE actually removed rows (usage_ledger.py:49).
- Q2: no — no new limit or cap; the existing 5 s ingest budget still sets partial=True (usage_ledger.py:121-123), unchanged by this handover.
- Q4: yes, gated and tested — the one new auto action (the connect-time repair) runs only when `DELETE ... t IS NULL` has rowcount > 0 (usage_ledger.py:49-50), so it fires once and is a no-op on a clean DB; covered by tests/usage/test_usage_ledger.py:175 (repair removes the rows and resets cursors) and :181 (re-read happens once, no double count, a clean connect keeps the cursors).

## Return to Claude (orchestrator)

- No FAIL, no NOT RUN. All 6 Checks matched Expected byte-for-byte; mutation proof: base fails 5 cases by assert, 5/5 mutants killed, final PASS 29, freeze sha256=ad546599a05952d00f054174d9324d754881b80c0be319ee520f50f80bbf1c59 (matches the Expected freeze line).
- Noticed, not changed: nothing outside steps 1-4 was touched; `git status --short` above is the whole scope. The apply_edits.py run on CHANGELOG.md was its first and only run.
- Questions: none.

Return to Claude

