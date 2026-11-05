# TriggerBox occupied-port recovery

Status: Completed

## Problem and evidence

A reported launch on COM4 failed in pyserial before marker output with Windows
`PermissionError(13, 'Access is denied.', None, 5)` while the vendor utility was open.
Windows COM access is exclusive. Studio cannot release another program's handle;
manual selection and metadata discovery cannot bypass that restriction.

Previously Detect checked only recognized driver names, skipping an explicitly
selected port whose driver metadata was generic or absent. Explicit Detect now
checks that selected port too, retaining the distinction from verified identity.

## Scope and acceptance

1. Reproduce denied access and manual-port omission with fake serial connections.
2. Keep automatic enumeration metadata-only; explicit Detect checks named candidates
   plus the operator's manual/custom COM selection without device-byte probes.
3. Explain exclusive ownership and retry in launch errors and visible setup status;
   preserve the raw error, selection, cancellation and preflight failure behavior.
4. Verify denied access followed by successful retry after the simulated owner
   releases COM4, with no alternate-port fallback or unrelated generic-port scan.
5. Update registered GUI coverage at 700x640 in both themes and run safe focused
   checks plus repo precommit. Visible Qt and physical EEG acceptance remain manual.

The triggers package retains discovery/error interpretation; GUI snapshots selections
before worker dispatch. No persisted formats, runtime marker timing or protocol change.

## Verification

- Baseline triggers focused: 254 passed.
- Pre-fix regressions: 18 failed, including the reported serialized Windows error
  and the unsupported manual-selection discovery request; two existing checks passed.
- Final focused checks: triggers 272 passed; safe GUI 168 passed; docs 13 passed.
- A runtime regression reproduces the reported COM4 error through the real adapter
  and confirms preflight aborts before presentation or any attempted markers.
- Windows all-source mypy (269 files), Darwin adapter mypy (9 files), changed-file
  Ruff/compilation and repository audits passed.
- Repo precommit was run in an isolated checkout because pre-existing, untracked
  user files fail changed-file Ruff in the main checkout; those files were untouched.
  The first long checkout hit Windows path limits. After shortening it, the full
  non-Qt run finished with 5265 passed, 32 skipped, 24 subtests passed and 17 failures
  confined to `test_project_bundle_update.py`'s deeply nested staging paths.
  Rerunning that entire module with `--basetemp=build/triggerbox-short-tmp` passed
  all 33 tests, including all 17 failures, without source changes. Thus 5282 distinct
  tests passed across the full run and targeted retry; this was not a single green
  full-suite invocation. Skips reflect host/platform/symlink and version restrictions.
- Independent trigger/lifecycle review found no routine leaked discovery handle.
- Registered GUI coverage includes denied-access recovery, captured manual selection,
  edits during a check and 700x640 layouts in both themes. Qt was not executed under
  the repository's visible-environment approval rule. No physical TriggerBox/EEG
  qualification or installer build was performed.

Manual acceptance: select TriggerBox COM4 in Recording Setup, run Detect with
Configuration/Test IO holding the port, verify visible close-and-retry instructions,
close that utility and Detect again. Apply and launch a short normal recording;
inspect saved EEG markers separately. Detect itself must send no marker bytes.
