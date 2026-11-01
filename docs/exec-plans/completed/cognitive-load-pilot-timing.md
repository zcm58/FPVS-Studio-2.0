# Cognitive Load Pilot Timing

Status: Completed

## User workflow and scope

Update the existing **Cognitive Load FPVS** project described as **Simran & Sarah
Pilot**. Preserve its six semantic-category, recognition-memory and angry-face
load/no-load conditions, stimulus sources, task order, geometry and trigger settings.
The built-in scaffold and reusable backward-counting defaults remain unchanged.

Each condition runs in three session blocks, with one 40-second stream per entry:
one sequence and 48 oddball cycles at 6 Hz with an oddball every fifth item. Keep
the existing per-block randomization. This produces 18 entries, including nine
counting entries with an endpoint question after each repetition.

All counting assignments subtract 3 from a seeded random integer in the inclusive
1000–2000 range. The active baseline remains 30 seconds and runs once before the
session's first entry. Counting starts immediately before each load stream; the
existing endpoint task remains the first task immediately after it.

All condition instructions and displayed fixation reminders use:

> There will be a cross at the center of the screen. The cross will change colors
> only ONCE throughout each condition. Press the space bar when you see the color change

Retain the recognition-memory instructions and make the counting assignment clear
on the load conditions.

## Implementation boundaries

- Add an optional persisted `FixationTaskSettings.target_onset_window` with
  `earliest_seconds_before_end` and `latest_seconds_before_end`. Require an enabled,
  visible cross and exactly one fixed target when this window is present.
- The pilot opts into a 10–3-second window before the stream ends. Compile one
  seeded random onset within the inclusive frame window, respecting target duration
  and minimum-gap edge buffers; reject an incompatible run rather than clipping
  the requested interval.
- Compilation owns the timing realization. `RunSpec` continues to contain concrete
  frame events; runtime and engines consume those events without project-specific
  behavior. Stimulus schedules and other fixation defaults remain unchanged.
- Apply the project settings through validated project models and preserve a
  recoverable copy of the original project file. Do not rewrite stimuli or results.

## Verification and acceptance

Non-Qt coverage checks model validation and serialization, inclusive onset boundaries,
seeded determinism, invalid windows, all five supported refresh targets and unchanged
default scheduling. Unused windows are omitted from model serialization to preserve
existing protocol fingerprints. Masking rejects an authored window rather than
silently omitting it.

The actual saved pilot compiles to 18 entries of 40 seconds at its configured 60 Hz,
one target 10–3 seconds before each stream offset, counting starts in range, and nine
immediate endpoint tasks. All displayed entry paths include the exact fixation
instruction, including counting-start screens that replace the ordinary gate. A
no-load-only selection has nine entries with no counting baseline or endpoint.
The original project file is backed up outside the repository; stimuli and existing
results were not rewritten.

- Core focused: 598 passed, one Windows symlink-privilege skip.
- Compiler focused: 482 passed; six additional refresh/window integration cases pass.
- Project-I/O focused: 430 passed, two symlink skips, one temporary bundle-directory
  rename failure (`WinError 5`). The identical Library test failure reproduces against
  an isolated, unmodified HEAD snapshot.
- Repo precommit with four workers: Ruff, compilation, mypy and repository audits
  pass; 4088 tests pass, with 12 Windows symlink-privilege skips. The Library rename
  test also passes in this completed broad run.
- Docs focused and final diff checks pass.

The temporary baseline snapshot remains in task scratch storage because automatic
approval review blocked its recursive cleanup with a policy rejection. No project
or repository data was deleted.

Visible/manual presentation checks have not run. Verify the participant screens,
color change and endpoint entry in a safe visible session before collection.
Physical display and trigger timing qualification remains separate. The new
authored field requires the updated source/app build; older installed builds reject
unknown fixation settings. No installed application was rebuilt or replaced.

## Experiment Library publication

Published [Cognitive Load FPVS 1.0.5](https://openfpvs.com/experiments/cognitive-load-fpvs/1.0.5)
on October 30, 2026, under the existing `cognitive-load-fpvs` identity. The clean
whole-project bundle contains all six conditions, 2,994 files and 37,087,736 bytes.
Earlier published versions remain intact. Catalog publication committed to private
Website `main` at `b55b4060651b959176e33d03823847bb12d820c2`; asset ID is `692902564`.
The exact SHA-256 is:

`12e38beeecb44a7f823bf2f66156000bf8839566e6694542706b14dfe40a6895`

The catalog explicitly requires Studio 2.5.7; the compatible packaged application
release is pending. Released 2.5.6 rejects the new authored fixation field and is
correctly prevented from downloading this version.

Preparation validates the clean bundle through canonical import/compilation.
The unchanged canonical offline validator and DPAPI signer ran with the updated
Studio Python environment, refreshed ClamAV definitions and verified the proof
against the existing public pin. The protected signer and installed toolchain were
not modified. The exact signed proof was registered in the existing D1; a read-only
query confirms its item/version/hash and absence of withdrawal. The enrolled native
Library client confirms the same live catalog item and verifies its signed proof.

Library focused verification passes 488 tests with three Windows symlink-privilege
skips. This publication required no new application or service source changes,
deployment, participant-data upload or physical presentation test.
