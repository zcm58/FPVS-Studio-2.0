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
4. Retain reviewed session logs alongside the reported traceback, with a clear
   256 KiB diagnostic cap. Deliver every accepted byte to the private GitHub issue,
   using numbered comments when needed. Preserve redaction, explicit submission,
   receipt identity and automatic-crash privacy. Verify and deploy the corresponding
   feedback-service change before publishing the desktop release.
5. Run focused, visible approved checks and exact-source precommit/CI. Build and
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
  test checkout. The complete route passed 1,114 tests with four skips in the clean,
  short release checkout. The initial precommit invocation used the system Python
  for a nested audit; rerun with the approved Python environment on PATH for final source.
- Twelve new cursor regressions cover the built-in four-of-eight memory-selection
  task at simulated 100%, 125%, 150% and 200% content scaling. A bounded native
  renderer check passed windowed 1280x720 and fullscreen 1920x1080 at actual
  100% scaling, with nine framebuffer pointer observations per mode, selection
  revision and successful Submit. This does not qualify the reporter's Windows 10
  machine. Production cursor behavior remains unchanged.

## Reporting follow-up

The user explicitly added complete reasonable-sized GitHub error logs to 2.8.2.
Three visible regression tests reproduce losing collected session context when
accepting the popup error or refreshing logs. The feedback service also truncates
diagnostics to 2,048 bytes before constructing the GitHub issue. The coordinated
change retains the existing diagnostics field and receipt protocol, raises manual
limits to 256 KiB diagnostics / 1 MiB payload / 4 MiB local draft, and delivers
long text through resumable numbered GitHub comments. Existing logging retention,
feature limits, automatic-crash payloads and manual consent remain separate.
The larger local draft bound accommodates escaped text and a persisted accepted
error without rejecting an otherwise valid report before submission. Independent
review added coverage for repeated long errors, draft restart/refresh, another error
arriving during collection, and starting a second report in the same process.
Support/client/automatic-crash regression checks passed 131 tests with one existing
Windows symlink-permission skip. The approved visible reporting/error sweep passed
80 tests with one native-Cocoa skip; safe GUI-focused checks passed 180 tests.
Long-text redaction now avoids repeated rescanning, and a regression proves private
home-directory path tails are removed while traceback module filenames remain useful.

The feedback service implementation `c0854416` passed 33 tests and both deployment
dry runs. Staging preserved and reconstructed a near-1 MiB synthetic payload with
all 256 KiB of diagnostics. Production migration 0005 and Worker version
`bee800f6-2c43-466e-b5dd-528a179e4571` were deployed; the downloaded module matches
the committed bundle, all 17 bindings were preserved, and desktop health returned
HTTP 200 with intake enabled. Existing accepted reports retain their prior privacy.
No synthetic production issue or email was sent, and production CPU headroom is
not qualified by the local tests.

A read-only operations check found the maintenance heartbeat had stopped on
October 22, before this release. One documented generation-based restart restored
it, and its next automatic cycle advanced after 306 seconds. Retention counters
were consistent, with no overdue records or unfinished delivery. The original
stoppage's cause remains unknown; this records operational recovery, not a scheduler
code fix. The service deployment and recovery receipts are pushed through `c8b7dd0`.

## Final verification follow-up

Two complete precommit runs each passed 5,857 tests and 24 subtests with 33 skips,
but failed at different project-import directory commits with Windows access denied.
The same denial also reproduced in the isolated Library module. An instrumented
failure found no open Python streams or current-process file handles under staging;
with garbage collection disabled, the identical rename succeeded after a brief wait.
Independent review found no deterministic stream, image or archive lifetime leak.
The process responsible for the temporary denial remains unknown.

This reproduced release blocker adds one narrowly scoped repair: retry only brief
Windows directory-rename access/sharing failures, preserving the non-overwriting
commit, cancellation and persistent-error behavior. Focused regressions and a new
exact-source precommit/CI pass are required before packaging the final candidate.
The repair uses the existing 150 ms Windows-lock budget and rechecks cancellation
and destination ownership before each attempt. Ten regressions cover temporary
and persistent locks, unrelated errors, cancellation and a competing destination;
eight failed before the repair. Both implicated modules pass 121 tests with two
existing Windows symlink-permission skips.
