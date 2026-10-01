# MSMS AB Repeated Targets

Status: Completed

## Authorized Workflow

Update the existing MSMS AB Test project to nine-second bursts at 10 Hz.
Present the same T1 digit at 2.1, 3.1, 4.1, 5.1, 6.1 and 7.1 seconds.
Omit T2 following the first T1; present the same T2 digit after the remaining
five T1 presentations, retaining each condition's 100/300/500 ms SOA.
Retain the two recall questions, 24 bursts per SOA and session randomization.

## Implementation

- Add explicit optional repeated-target metadata to native AB settings and RunSpec:
  target_count (default 1), target_interval_slots (default None), omit_first_t2
  (default false). Existing single-pair schedules retain their behavior.
- Core describes the entire burst, samples one digit pair per burst, compiles every
  event and marker, and assigns repeated pairs separate cycle indices for observed
  SOA reporting. Target positions describe the nominal first pair, even when omitted.
- Recall compilation and reporting accept repeated presentations of one unique digit
  per target role. Engines continue to consume compiled frame events.
- Preserve repeated-target timing through Design edits and show an accurate preview.
- Validate the updated external project in a staged copy, retain the original as a
  backup, and apply only the requested experiment edits to the known project root.

## Verification

- Compiler baseline: 346 tests passed.
- Assert 540 frames at 60 Hz, 90 characters, six T1 and five T2 markers, all exact
  SOAs and onsets, constant target identities, and distractors in the omitted slot.
- Cover project/config/RunSpec roundtrips, recall answer keys and reports, per-pair
  onset exports, and GUI apply/preview preservation with registered Qt coverage.
- Run compiler/runtime/GUI/docs focused checks and repo precommit. Do not run Qt or
  PsychoPy locally without an approved visible environment. No hardware markers.

## Progress

Implemented repeated-target scheduling, exact Design retiming, preview and Review
summaries, recall answer keys, runtime preflight, and per-pair observed timing.
The user revised the initial six-second request to nine seconds with the first T1
at 2.1 seconds. New starter defaults and default serialized contracts are unchanged.

Updated the existing external-drive MSMS AB Test project and retained its original
as `project.before-msms-nine-second-timing-20261001.json` in the same project folder.
Verified all 72 entries in the saved project at 60/120/240 Hz: nine seconds each,
six T1/five T2, exact onsets, marker alignment, repeated identities and recall keys.

Verification: compiler focused 369 passed; targeted AB runtime/report 91 passed;
six further export cases passed; GUI focused seven safe checks plus Ruff/compilation
and targeted mypy passed. Docs focused nine passed. Repo precommit Ruff, compilation,
mypy (212 source files), audits and docs passed. Its safe suite had 2458 passes,
11 Windows symlink-privilege skips, and two Windows access errors (normalization
directory replacement and reporting-lock named pipe). Both failed tests passed
isolated reruns, with explicit sandbox escalation for the named-pipe test.

Registered Qt layout/behavior tests were extended but not run locally. Visible
GUI/PsychoPy/physical marker timing remains unverified; follow `docs/GUI_WORKFLOW.md`
for manual acceptance. Changes are available in the source checkout; no installed
application executable or release package was rebuilt.

## Experiment Publication

Published the revised experiment on October 1, 2026 as `msms-ab-test` version
`1.1.0`. No earlier MSMS AB catalog entry or release existed on the Library server.
The published release is
[`msms-ab-test-v1.1.0`](https://github.com/zcm58/FPVS-Studio-Library/releases/tag/msms-ab-test-v1.1.0),
confirmed by catalog commit `a2ea76a5cad3f6a71debd94961dd91d0daebf0a9`.

The canonical clean publisher produced `msms-ab-test-1.1.0.fpvsbundle` (3206 bytes),
SHA-256 `154212859964eb5c0856e542cce1b7a9fd433c3984909979f336baa157050a07`.
It contains only `project.json` and `stimuli/manifest.json`, with local participant
selections and machine/profile settings sanitized. No logs, runs or backup project
were uploaded. The source project remained unchanged. Prepared bytes and review
metadata are retained under `build/library-publications/msms-ab-test-1.1.0/`.

The catalog minimum Studio version is `2.2.4`: released `2.2.3` lacks the repeated
target fields and rejects them. This is a protective download gate pending a
compatible packaged release, not evidence that Studio 2.2.4 has been released.
The current updated source checkout can use its existing local project; a checkout
still reporting 2.2.3 cannot download this release through the gated Library UI.

Publication verification: Library focused 225 passed, three Windows symlink skips;
clean import and all 72 bundled entries compiled with exact timing at 60/120/240 Hz;
publisher dry run passed; GitHub confirmed immutable asset and catalog publication;
the enrolled live Library client listed version 1.1.0 with the exact prepared hash.
