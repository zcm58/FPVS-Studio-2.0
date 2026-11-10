# History compatibility, source updates and Studio 2.8.2

Status: Active

## Scope and acceptance

The user reported a Windows 10 / Studio 2.8.1 launch failure while updating
`session_condition_history.csv`, requested pulling remote changes and publishing
a bugfix release, and added source/macOS update guidance and missing participant
instruction/answer cursors. The remote reporter's CSV is unavailable; distinguish
reproduced compatibility defects from an unconfirmed diagnosis of that exact file.

1. Reproduce the history error using valid history, repair compatible reading,
   and prove preservation of timestamps, participant identities, old rows and
   retry-safe commits. Continue refusing unknown or malformed tables without data loss.
2. Prompt source checkouts and macOS to pull changes and restart. Keep installer
   download/repair exclusive to packaged Windows, including cached or direct actions.
3. Investigate the reported memory-object selection screen using Studio's built-in
   four-of-eight image-memory workflow and shared response renderer;
   preserve intentional stimulus/feedback cursor hiding and existing response semantics.
   Do not claim a cursor repair without reproducing a production defect.
4. Run focused, visible approved checks and exact-source precommit/CI. Build and
   publish 2.8.2 through the draft/hash/immutable-release workflow, then verify public
   downloads, attestations and updater selection. Record source-update behavior too.

Preserve unrelated untracked files, earlier release artifacts, user projects and
research records. Use synthetic projects, no actual hardware or production installer.
Retain blocked-cleanup directories. Do not automatically pull a user's source checkout
from the application or force-close another application's serial port.

## Diagnosis

- Latest remote master `c7e5e22` and all remote tags were fetched; master fast-forwarded
  successfully while the two existing untracked paths were preserved.
- A valid UTF-8 history with a leading byte-order mark reproduces the exact error.
  The reader treats that marker as part of the first column name. All 13 historical
  Studio-generated header schemas are subsets of the current schema; no missing
  rename migration was found. Delimiter edits also fail safely and are not silently
  reinterpreted. The reporter's actual header remains unknown.
- Existing export/durability baseline: 46 passed.
- Fifteen new history regressions failed before the reader repair and pass afterward
  (seven failed before; eight preservation checks already passed). They cover full
  and compact launches, current/legacy/reordered headers, Unicode and quoted fields,
  leading-zero participant IDs, retained timestamps, idempotent retries and atomic
  replacement failure. Unknown, duplicate and malformed columns still preserve bytes.
- The remote report also says no mouse appears when selecting objects to remember.
  Its retained diagnostics contain only the supplied history traceback, without
  the CSV header or display/backend details. The exact memory-selection route already
  enables a software pointer; no production cursor defect has been reproduced here.
  The report contains no project or task definition to establish its exact authored screen.

## Local verification in progress

- Updates-focused checks passed 384 tests with four symlink-permission skips;
  safe GUI checks passed 180 tests. The approved visible updater sweep passed
  118 cases on the native Windows desktop, including simulated source/macOS states,
  direct/stale installer guards, failure/cancel guidance and minimum/default layouts.
- Packaging-focused checks passed 192 tests; documentation checks passed 13 tests.
- All 620 engine-focused tests passed. The wrapper's changed-file lint included an
  unrelated user-owned untracked example, so the registered engine pytest selection
  was run directly; changed tracked Python files passed Ruff separately.
- Runtime-focused checks passed 1,113 tests with four symlink-permission skips;
  one existing checkpoint assertion exceeded the Windows path limit in the long
  test checkout. The same test passed with a shorter temporary path. Repeat the
  complete route in the clean, short release checkout before publication.
- Twelve new cursor regressions cover the built-in four-of-eight memory-selection
  task at simulated 100%, 125%, 150% and 200% content scaling. A bounded native
  renderer check passed windowed 1280x720 and fullscreen 1920x1080 at actual
  100% scaling, with nine framebuffer pointer observations per mode, selection
  revision and successful Submit. This does not qualify the reporter's Windows 10
  machine. Production cursor behavior remains unchanged.
