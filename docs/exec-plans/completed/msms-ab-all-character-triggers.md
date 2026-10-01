# MSMS AB All-Character Triggers

Status: Completed

## Requested Behavior

- Preserve the nine-second, 90-character MSMS bursts, six T1 presentations from
  2.1 seconds at 1 Hz, and five T2 presentations after T1s 2 through 6.
- Use SOA100/300/500 condition codes 1/2/3, T1 code 55, T2 code 56, and
  distractor code 57 on every distractor, including the first character and the
  letter replacing the omitted first T2.
- Publish an incremental experiment release without replacing version 1.1.0.

## Implementation

Added an optional native-AB distractor marker code, absent from legacy serialized
settings. The compiler emits all character onsets and reserves frame -1 for a
condition-start marker on one neutral flip immediately before stream frame zero.
This resolves the first-character collision without multiple marker bytes on one
flip or changing the nine-second stream. Negative frame indices are otherwise invalid.

Core owns marker planning and validation; runtime checks the complete schedule
and preserves trigger records; the engine emits the pre-stream marker and all
stream markers through callOnFlip. The run clock remains continuous from the
pre-stream marker, excluding prior warmup. Character onset measurements remain
relative to the first stream flip. GUI reconstruction preserves the opt-in.

The external project update used a separate backup and a source hash guard.
Publishing used the existing clean-bundle and immutable catalog workflow, retaining
the minimum Studio 2.2.4 gate until a compatible application release exists.

## Verification

- Compiler/preflight checks across all SOAs and refresh rates: 91 markers per
  burst, comprising one condition, six T1, five T2, and 79 distractors.
- Fake PsychoPy plus fake external transport verifies flip order, bytes, logs,
  warmup exclusion, neutral lead-in, unchanged stream frames, and failure handling.
- Legacy serialization/scheduling regressions, GUI preservation registration,
  focused scopes, and repo precommit without local Qt or physical hardware.
- Compile all 72 external-project runs, inspect the sanitized prepared bundle,
  publish a new version, and read back the live catalog metadata.

## Results

- Compiler baseline: 369 tests passed.
- Compiler focused: 406 passed. Engine focused: 366 passed. Runtime/preflight:
  111 passed. GUI focused: seven safe checks passed; registered Qt tests not run.
- Final AB core/config/marker tests: 168 passed, including 21 fake-playback cases
  covering serial/UDP submissions, marker write failure, missing lead-in flip
  timestamps, and delayed marker-to-stream timing QC.
- Repo precommit: Ruff, compilation, mypy (212 files), repo audits and documentation
  hygiene passed. Non-Qt suite: 2537 passed, 11 Windows symlink-privilege skips, one
  sandbox named-pipe access failure. That isolated multiprocessing-lock test passed
  outside the sandbox. Later config/GUI changes received focused verification and
  a fresh successful full-source mypy check.
- Completed `.fpvsconfig` exports preserve the restricted frame -1 marker; ordinary
  trigger CSV and acquisition logs retain it without relabelling it as stream onset.
- Physical display/EEG reception and visible Qt acceptance remain unverified.

## Local Project And Publication

- Updated `D:/FPVS Studio Root (external drive)/msms-ab-test/project.json` after
  verifying source SHA-256
  `f1dc0fbb004165a7840a753c694478410f083f606cfa1596f21747257091ebf1`.
- Backup: `project.before-msms-all-character-triggers-20261001.json` beside it.
- All 72 runs validated at 60, 120, and 240 Hz, each nine seconds with 91 distinct
  marker frames. The stream itself still contains exactly 90 character onsets.
- Published MSMS AB Test **1.1.1**, retaining 1.1.0, at
  `https://github.com/zcm58/FPVS-Studio-Library/releases/tag/msms-ab-test-v1.1.1`.
- Catalog commit: `7f6c46b8b510b352821dd0ab8946b313f813f081`.
- Bundle: 3218 bytes, SHA-256
  `44c385546903312f9370a6cedbff0e9deaed094a63ac53114cd08e91ba829144`.
- Exact bundle and report retained under
  `build/library-publications/msms-ab-test-1.1.1/`; only project and native manifest
  are included, with local participant/calibration settings sanitized by the exporter.
- Enrolled live Library catalog readback verified version, size, checksum, previous
  version retention, and minimum Studio 2.2.4. No application version/release changed;
  the user's updated source checkout supports the local project.
