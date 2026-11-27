# Preserve session launch modes in participant results

Status: Completed

Run and session summaries must report the Test Mode and Pilot Mode chosen at launch.
The workbook distinguishes these flags from the reserved administrative participant
IDs `0` and `00`. These IDs always stay outside the research-version guard, even
when old or partial records contain missing or incorrect mode flags.

The session checkpoint originally preserved the selected modes until the first
run finished. The run summary then supplied its default `False` Test Mode flag
to the session export. Runtime and PsychoPy now read both flags from launch
options, including when the participant cancels before playback. The version
guard checks the reserved IDs in historical results and condition history as
well as acquisition records. Stored files are read without migration.

## Verification

The launcher regression checks Test, Pilot and ordinary research runs, plus a
reserved participant launched in ordinary mode. It reads each run summary and
the generated participant workbook. Cancellation and failures after playback
have separate checks. A synthetic historical project with inconsistent mode
flags verifies that participant `000` still counts as a research visit and that
`0` and `00` do not. All 13 targeted checks passed under supported Python 3.10
and trial Python 3.11.18. The tests use synthetic engines and trigger backends.

Repository precommit passed 6,653 tests with 41 skips on Python 3.10. Ruff,
Windows and Darwin type checks, and the repository audits passed.
