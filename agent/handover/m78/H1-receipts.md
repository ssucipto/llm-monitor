# Receipts: M78-H1 records and contract

- Handover: `agent/handover/m78/H1-records-contract.md`
- Date: 2026-10-25
- HEAD at start: `4a42942f67b3a20a59a15e3dbe3b19f3bf792a52` (drift line verified: `git diff --stat 1f74fd4 HEAD` lists only the handover file; `git status --short` empty before step 1)
- RUN_ID: m78-H1 (captures in Homelab `agent/delegation/runs/m78-H1`)

### Step 1 - agent/milestones/milestone-78-usage-ledger.md - PASS
```
step-1.ps1 sha256=7b6d521055e23cf22d165c9d60679168e45bf8e69a8ac7b8621916068905f60e
step-1.out sha256=c05e883f2f01cc6ebe9977b7b1ff9255020f22bc9283334d7a35e31a26d750b4
rc=0
```
```text
3
CR 0
```
Matches Expected (3 / CR 0). File created verbatim from the handover's Create block (extracted programmatically from the handover file, lines 59-120, LF endings; no retyping).

### Step 2 - .gitignore - PASS
```
step-2.ps1 sha256=aa4452cd73517fae01623d59ac8c2104d6e32eeed7057c9dc436b83ebffcfb11
step-2.out sha256=66bceb253f05ed70a73008da91827d268bd657cbddb66c88a69776c05070b8ff
rc=0
```
```text
llm-monitor/usage.sqlite3
llm-monitor/usage.sqlite3-wal
CR 0
```
Matches Expected. Edit 2a applied with the patch tool; Find text occurred exactly once.

### Step 3 - tests/usage/test_usage_ledger.py - PASS
```
step-3.ps1 sha256=a26aab45c2f20f0e58633034008be1e79068d5e4fb2949c68addf1b67e0f2271
step-3.out sha256=1b0a4d9b211de32494b800cc30005d6f70024deeac63340dcd12e8537b3654b8
rc=0
```
```text
parse ok
CR 0
```
Matches Expected. File created verbatim from the handover's Create block (extracted programmatically, lines 180-330, LF endings). It cannot pass yet: usage_ledger.py is H2 (as the step states).

### Step 4 - tests/usage/expected.txt - PASS
```
step-4.ps1 sha256=c946128a2c407b17c38e27eeb60967ae76674e9ef79adf2f97e8036de13a329e
step-4.out sha256=ab975ca4b34c19625524dc7c57c1ba4e4b81220415a06f9a64d191fee61b104e
rc=0
```
```text
test_usage_ledger.py 24
CR 0
```
Matches Expected. Created verbatim (lines 354-355, LF endings).

### Step 5 - tests/usage/run-tests.py - PASS
```
step-5.ps1 sha256=aed90c49e9ffa1aa41c381e9694ea943e3c446052ee5794477b79e6d3dab923a
step-5.out sha256=8e3954353a7f26bda02d9e306a752eb823291dc7702ebf76cbd92157588bcf75
rc=0
```
```text
parse ok
test_usage_ledger.py expected=24
CR 0
```
Matches Expected. Created verbatim (lines 379-438, LF endings).

## Scope check (git status --short after cleanup)

```
M  .gitignore
?? agent/handover/m78/H1-receipts.md
?? tests/usage/
```

`tests/usage/` holds exactly the 3 new files of steps 3-5 (test_usage_ledger.py, expected.txt, run-tests.py). `agent/scratch-m78/` deleted (R2 / finish step 1); no file outside steps 1-5 changed; no commit, no push.

Note: `agent/milestones/milestone-78-usage-ledger.md` (step 1) does not appear in `git status --short` because the pre-existing rule `agent/.gitignore:19` (`milestones/**`) ignores it — verified with `git check-ignore -v` (rc=0). The file exists on disk (62 lines, step-1 Check passed); the repo's convention is that milestone files are machine-local. The handover's expected "4 new files" therefore shows as 3 untracked + 1 ignored.

## Summary

| Step | File | Verdict |
|---|---|---|
| 1 | agent/milestones/milestone-78-usage-ledger.md | PASS |
| 2 | .gitignore | PASS |
| 3 | tests/usage/test_usage_ledger.py | PASS |
| 4 | tests/usage/expected.txt | PASS |
| 5 | tests/usage/run-tests.py | PASS |

Self-review Q1/Q2/Q4: not required (tier T0, per local.execute.md step 3 "T1 and above"). No risk flag.

## Return to Claude
- No FAIL, no NOT RUN. All 5 Check blocks matched their Expected on the first run (no retries, R6 never triggered).
- Note, not changed: the handover's Start here points at `D:\Project\Homelab\agent\handover\m78\H1-records-contract.md` for the verbatim blocks, but that path does not exist on this PC — the only copy of the handover is in this repo (`C:\Project\llm-monitor\agent\handover\m78\H1-records-contract.md`, added by the drift commit 4a42942). Every Create block was extracted programmatically from that local copy by line range (helper `agent/scratch-m78/extract.py`, since deleted), so no code was retyped; the handover file's own line numbering is the reference.
- Note, not changed: `git status --short` groups the 3 new test files as `?? tests/usage/` because the folder is untracked; per-file listing: test_usage_ledger.py, expected.txt, run-tests.py.
- Note, not changed: `agent/.gitignore` line 19 (`milestones/**`) ignores the step-1 milestone file, so `git status --short` shows 3 untracked new files + 1 ignored (see Scope check note). No .gitignore rule was changed (no step names one for that).
- Question for H2: none blocking. The contract test imports `usage_ledger` from `llm-monitor/` (sys.path insert at test line 12), so H2's module path must be `llm-monitor/usage_ledger.py`.
Return to Claude
