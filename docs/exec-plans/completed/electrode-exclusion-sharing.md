# Electrode and participant session reporting

Status: Completed

Source implementation, safe verification and publication are complete in
[Studio 2.4.6](release-2.4.6.md), committed and pushed to master. The published
installer and direct 2.4.5 patch contain the exact verified source candidate.
Sibling OpenFPVS acceptance is complete, including the approved three-lab dummy
study and the subsequent load-on-demand website refinement.

## Authorized scope

Capture nullable reviewed electrode exclusions and user-authorized age, sex,
handedness and colorblind status from each new completed research session in an
approved sharing scope. Freeze the launch values before presentation, keep random
subject UUIDs stable per local project/study, preserve saved opt-out and never backfill.
All existing project categories qualify independently of fixation-stat eligibility.

## Ownership and contract

- `core/data_sharing.py`: strict legacy 1.0, electrode 1.1 and participant 1.2 envelopes.
- `data_sharing/storage.py`: private bounded atomic subject mapping and immutable outbox.
- `runtime/data_sharing.py`: launch/terminal/commit proof and recovery from frozen evidence.
- `runtime/run_worker.py`, `acquisition_evidence.py`, `core/project_config.py`: one immutable
  launch snapshot and nullable completed-session Toolbox handoff.
- `runtime/session_export.py`, `participant_history.py`: explicit recorded flag distinguishes
  reviewed empty lists from unknown historical CSV evidence.
- Sibling OpenFPVS owns authentication, additive storage, lab-scoped aggregation and private UI;
  Toolbox owns explicit recording association and actual processing/interpolation outcomes.

Canonical field, null and privacy semantics live in `docs/DATA_SHARING.md`. Raw PIDs,
names, notes, questionnaire answers and EEG never enter these report envelopes.

## Verification

1. Verify old wire/outbox bytes and strict new nullable fields with neutral model/storage tests.
2. Verify every category, independent fixation eligibility, repeated visits and unchanged retries
   with fake runtime/transport tests. Confirm launch mutations cannot change captured evidence.
3. Verify full/compact completed handoffs and history round trips, including legacy unknown values.
4. Run data-sharing, runtime, project-io and docs focused routes, then safe repo precommit.

Final source gates pass: Ruff, compilation, all 235 source modules under mypy, harness
audits and docs hygiene. Safe precommit passed 3,042 tests and 20 subtests, with 11 Windows
symlink privilege skips. Its unchanged 1,500-session archival stress case passed in the
preceding full run and was reused rather than repeated (one deselection in the final run).
The final export-header regression also passes. Focused reporting coverage passed 251
tests excluding that same stress case; GUI's non-Qt route passed 17 and docs passed 10.

Four actual synthetic runtime reports and their completed handoffs are retained in
ignored `build/electrode-fixture/`: one known participant's two visits plus two separate
subjects, including known/empty/unknown electrode snapshots and nullable demographics.
All share the compiled study/protocol; earlier immutable report bytes were not rewritten.

The user subsequently authorized and completed the Studio 2.4.6 release sequence.
Its fresh safe precommit passed 3,043 tests and 20 subtests with 11 existing Windows
symlink skips, including the archival stress case. Authenticated installer/patch
extraction, frozen source and native dependency audits, six public asset digests,
signed attestations and 11 updater cases pass. Visible Qt, installed upgrade and
physical EEG qualification remain unrun. Synthetic local exports and live dummy
acceptance do not qualify physical EEG.
