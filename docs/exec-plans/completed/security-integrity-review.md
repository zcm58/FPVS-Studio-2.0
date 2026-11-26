# Security and study data integrity review

Status: Completed

## Changes

- Preserved working settings and stimulus files when a saved-version transaction
  or its rollback fails. Regression cases include a real SQLite reader, failed
  file replacement, another editor's save and volumes without hard links.
- Bound **Retry pending** to the selected Results enrollment and rechecked the
  queued report at dispatch. Applied the existing request deadline and cancellation
  policy to HTTP error bodies. Tests use a local transport and synthetic reports.
- Preserved existing workbooks on failed export, wrote literal summary text as
  text and stopped research CSV migration on malformed records. Reconciled the
  two legitimate journal entries for an interrupted backward-counting interval.
- Corrected results cleanup inventory and rollback around links, Windows junctions
  and workbooks created after inventory.
- Fixed a participant-launch callback that could continue after its Qt owner was
  destroyed during a nested save or confirmation. Both Home and Run stop launch
  when their owner is destroyed and retain the usual live-window error dialog.
- Raised the engine's GitPython minimum to 3.2.1. The [security contract](../../SECURITY.md)
  records the supported imaging stack's remaining advisory exposure.

## Verification

The Windows precommit run passed 6,673 tests, with 41 platform or permission
skips. The Windows and Darwin type checks and repository audits passed.

On the native Windows desktop, seven new regression cases exercised disposal
during participant confirmation or save. The ordinary asynchronous preview-to-run
case passed. Two shutdown cases, a failed condition-order save followed by retry,
and a simulated 144 Hz selected-display refresh check also passed. An isolated
check confirmed that participant history loads on a worker before confirmation.
All thirteen cases passed on both the supported Python 3.10 environment and the
independent Python 3.11 trial. The display routing check uses a fake engine.

Against baseline `f325278`, a seeded sample produced byte-identical compiled runs
at 60, 60.02 and 120 Hz. All 45 uncompressed parts across four workbook types
and a migrated CSV matched with fixed inputs and timestamps. Consolidation retained
all seven research sheets and the same source CSV and EEG bytes. Ordinary Results
requests, persisted settings, receipt and returned view matched the baseline.

On this Windows machine, 100 alternating completed Setup saves on each revision
had median times of 20.78 ms on the baseline and 19.66 ms on the revised code.
The fixture used eight conditions and six images. The successful saves and
restores preserved the working project and stimuli byte for byte.

The release installer, deployed services and physical acquisition have separate
acceptance requirements. An independent worktree tested Python 3.11 and Pillow
13. Existing studies retained their identity when opened with intact stimuli.
Regenerating images under the new Pillow changed the file hashes of four study
stimuli despite pixel-identical output. The dependency upgrade remains on the
[experimental branch](https://github.com/zcm58/FPVS-Studio-2.0/blob/codex/python311-pillow-trial/docs/exec-plans/completed/python311-pillow13-trial.md).
