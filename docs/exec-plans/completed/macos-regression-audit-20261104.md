# macOS regression audit

Status: Completed

Four confirmed defects repaired and source verification completed on Windows.
The separate physical Mac acceptance gates remain open in the Phase 1 plan.

## Scope and acceptance

Review the recent source-only macOS changes through Studio 2.6.1 for reproducible
crashes, broken workflows and unintended Windows/Linux behavior changes. Fix
confirmed defects while preserving authored projects, compiled timing, session
ordering, acquisition policy and persisted formats. Commit and push the verified
changes as requested; this task does not publish a release.

Review ownership is split across presentation/display/input, GUI launch/probe
lifecycle, runtime/process/recovery, and source bootstrap/portable adapters.
Each repair needs regression coverage at its owning boundary. Verification uses
the macOS focused baseline, implicated focused scopes and final repo
precommit. Qt and physical Mac/hardware checks remain separate; no visible test
environment has been authorized for this audit.

## Progress

- Clean starting checkout: `da46dba` on `master`.
- Baseline macOS focused verification and parallel source reviews completed.
- Confirmed: Mac display-link protection requires PsychoPy APIs absent from older
  versions that the installer still allowed. The Darwin-only minimum is now 2026.1;
  Windows/Linux dependency ranges stay unchanged. Setup can upgrade incompatible
  existing environments without a blanket dependency upgrade.
- Confirmed: normalization and Image Resizer did not share intake's Finder-metadata
  filtering. Signature-recognized metadata now follows the existing source-file
  filter; authored dot-prefixed images, source bytes and ordering remain intact.
- Confirmed: PsychoPy reports NumPy window dimensions on Windows/Linux as well as
  Mac. The old list/tuple-only branch skipped runtime's intended resolution guard.
  All platforms now retain that check; correct-size and use-current-size launches
  preserve their behavior. This is a pre-existing discrepancy exposed by the audit.
- Confirmed: saved-refresh readiness could block the local Mac display confirmation
  path. Home and Run now allow that step only if an approved refresh can resolve all
  validation errors and blocking timing warnings. Actual confirmed-display validation
  remains mandatory; Windows/Linux and Run's existing validation-error action remain
  unchanged. Model checks perform no filesystem/native-display I/O.

## Verification

- macOS focused baseline: 1,462 passed, 26 platform/dependency/native-opt-in skips;
  Darwin adapter type checks passed. The reporting-retention volume case completed.
- Preprocessing focused: 61 passed. Finder metadata regressions reproduced before
  the repair; source bytes and authored dot-prefixed images are covered.
- Package metadata/bootstrap/tooling: 64 passed, 17 platform skips. Dependency
  selection regression reproduced before the repair.
- Engine focused: 559 passed. Retina/display-link: 76 passed, one installed-dependency
  reproduction skip. Cross-platform matching/mismatching NumPy dimensions covered;
  an independent reviewer found no additional issue.
- GUI focused safe route: 164 passed; Mac document regressions: 27 passed. An
  independent review confirmed preserved platform, structural and actual-rate gates.
- Docs focused: 13 passed and hygiene checks passed.
- Final repo precommit (`-Workers 4`): 5,170 passed, 32 platform/dependency skips;
  changed-file Ruff/compilation, all 267 Windows source type checks, nine Darwin
  adapter type checks and repository audits passed. Counts above overlap and must
  not be added together.

## Visible acceptance not run

No Qt or PsychoPy window was opened during this audit. In an approved visible Mac
environment, exercise Home and Run with a synthetic project saved at an incompatible
lab refresh that fits the connected display: confirm **Check Local Display**, cancel
without writes, accept local calibration and reach the ordinary launch flow. Repeat
with a structural error and an incompatible confirmed rate; playback must stay
blocked. Check the status/button text at minimum/default sizes in both themes.
Registered fake-backed GUI cases cover these readiness states separately.

Physical display timing, literal keyboard interaction, hardware and the previously
deferred Mac acceptance gates remain outside this Windows source audit.
