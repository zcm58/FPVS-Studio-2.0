# Image Equalizer

Status: Completed

## Workflow and decisions

Implement the authorized grayscale subset of the earlier luminance/RMS investigation.
Researchers optionally resize/crop images, then open Image Equalizer from Tools,
including before opening a project. They add input/output folder pairs and run one
batch. All folders share automatic mean intensity and RMS contrast targets. Original
images and existing destination files are preserved. Monitor calibration remains the
researcher's responsibility. This is digital intensity matching, not photometry.

Use Pillow's 8-bit grayscale conversion and an affine mean/standard-deviation match.
Use mean 128 and the smaller of the median input standard deviation and the common
no-clipping limit. Measure the entire canvas. Reject flat, transparent, animated,
unsupported-depth and corrupt images explicitly. Report achieved saved-PNG statistics
and the chosen target. No project schema, manifest or runtime changes.

## Implementation and verification

1. Pure preprocessing service: preflight all paths/files, analyze then transform using
   a bounded thread pool, exclusive PNG/report writes and owned-file rollback.
   Verify numerical targets, deterministic parallel results, cancellation, collisions,
   invalid images and preservation with temporary-directory tests.
2. Small shared-shell dialog: folder-pair table, Add/Remove, Equalize Images, Cancel/
   Close, persistent status and accessible full paths. Use existing ProgressTask
   lifecycle. Minimum 960x640, default 1120x720, long paths and empty/busy/error/success
   states. Register Qt tests; visible execution requires separate authorization.
3. Update current product mission/spec, workflow and ownership routing. Keep the v1
   archived specification historical. Run preprocessing/gui/docs focused checks and
   repository precommit; document any unavailable checks precisely.

## Acceptance

- Implemented the service, standalone dialog, Welcome/MainWindow Tools entries and
  registered GUI tests. Updated current mission/spec routes and corrected the stale
  eight-step Setup description. Archived the superseded investigation.
- Passed: 91 preprocessing checks (including 30 equalizer checks), 180 GUI-safe checks,
  13 documentation checks, 88 repository checks (one Windows symlink-permission skip),
  verification config, changed-feature Ruff/compilation,
  Windows source mypy (289 files), Darwin source mypy (9 files) and repository audits.
  The final high-depth decoder change also passed focused mypy.
- Initial focused runs hit sandbox temporary-path length errors in existing fixtures;
  reruns with a short task-owned temporary root/basename passed.
- The precommit driver stops at six pre-existing E501 errors in user-owned
  `.codex-tmp/cognitive-load-library-2026-10-29/prepare.py` and
  `src/fpvs_studio/engines/standalone_contrast_example.py`. Neither file was changed.
  Remaining precommit commands were run separately. The broad safe suite reported
  failures and a worker crash near 99%, then stopped making progress; it was interrupted
  and is not claimed as passing. A serial first-failure diagnostic (explicitly excluding
  the 1500-session reporting stress test) passed 681 tests before the unchanged
  `test_triggerbox_real_pyserial_transport_preserves_all_codes_and_reconnects` failed:
  the sandbox denies its localhost socket with WinError 10013. Other broad-run failures
  were not individually triaged. No recording or reporting code was changed.
- With explicit user approval on 2026-11-16, all nine registered native Windows Qt
  checks passed with a clean process exit. Coverage includes two folder pairs through
  real background workers, cancellation after output creation, complete rollback and
  successful retry, original hashes, output statistics, menu access before/after
  project creation, and all dialog states at 960x640 and 1120x720 in Light and Dark.
- Reproduced and fixed a menu-test teardown error: the test now drains controller
  background jobs before Qt disposes the application. No lifecycle production change
  was needed. Updated the new dialog to use the current shared text roles and heading
  alignment after integrating the latest default branch.
- Direct visible desktop review at 960x640 and 100% scaling (96 DPI, 3440x1440 display)
  verified the light-theme empty, busy, success and failure states, native selection of
  two input folders and a custom output, four saved grayscale PNGs, and rejection of
  a repeated batch into occupied destinations. Full paths remain accessible when
  elided. Higher display scaling and macOS visual acceptance were not performed.
- Expanded visible verification passed all 22 cases, including the affected Tools
  menus and Welcome layouts. Windows emitted a handled `0x8001010d` diagnostic during
  Qt event processing; the same diagnostic reproduced on unchanged `master` at
  `0bdc3ca` (11 baseline cases passed). Both runs exited successfully. The isolated
  nine-case Image Equalizer module passed without that diagnostic.
- Based the update on default-branch `master` at `0bdc3ca` and ran precommit in
  an isolated checkout containing only this feature. Changed-file Ruff/compilation,
  Windows mypy (290 files), Darwin mypy (9 files), harness and documentation audits
  passed. The full non-GUI suite reached 98% before its worker exited while running
  `test_1500_acknowledged_sessions_retire_exact_history_and_keep_latest`, exactly
  600 seconds after starting that test, matching its explicit timeout. Reporting
  source/tests are unchanged from `master`. The runner then stopped making progress
  and was stopped. Full precommit is not claimed as passing; focused acceptance is
  recorded separately from this existing reporting stress-test limit.
- Final focused runs on the integrated feature tree passed: preprocessing 91,
  GUI-safe 180, documentation 13 and repository 88, with one Windows symlink-permission
  skip. No Image Equalizer assertion failed. All temporary GUI fixture originals and
  completed-output hashes were independently verified after the native batch run.

## GUI polish, 2026-11-16

- Replaced the nested page shell with a shared DialogHeader and one flat layout.
  Folder actions sit above the table; status and footer share its margins. Preserved
  all folder, processing, cancellation and output behavior.
- Passed 180 GUI-focused checks, nine visible Qt cases and 13 documentation checks.
  Layout coverage uses complete light/dark palettes, two long folder pairs, both
  documented sizes and ready/busy/error/cancel/success states. The native Qt process
  emitted the previously baseline-reproduced Windows `0x8001010d` diagnostic and
  exited successfully with all assertions passing.
- Direct visible review confirmed the light-theme populated layout at 960x640 and
  dark-theme empty layout at 1120x720, at 100% Windows scaling. Keyboard focus remained
  visible. No clipped controls or nested page frames remained. Processing was covered
  by the real-worker batch/cancellation tests. Higher scaling and macOS were not checked.
