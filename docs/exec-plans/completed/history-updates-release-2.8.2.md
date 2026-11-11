# History compatibility, source updates and Studio 2.8.2

Status: Completed

Published Studio 2.8.2 on November 10, 2026, with source, packaged and public
release verification recorded below. The remote reporter's exact CSV and cursor
cause remain unconfirmed.

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
- Fifteen new history regressions pass after the reader repair
  (seven failed before; eight preservation checks already passed). They cover full
  and compact launches, current/legacy/reordered headers, Unicode and quoted fields,
  leading-zero participant IDs, retained timestamps, idempotent retries and atomic
  replacement failure. Unknown, duplicate and malformed columns still preserve bytes.
- The remote report also says no mouse appears when selecting objects to remember.
  Its retained diagnostics contain only the supplied history traceback, without
  the CSV header or display/backend details. The exact memory-selection route already
  enables a software pointer; no production cursor defect has been reproduced here.
  The report contains no project or task definition to establish its exact authored screen.

## Source and visible verification

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
commit, cancellation and persistent-error behavior. Focused regressions and the
final exact-source precommit/CI acceptance are recorded below.
The repair uses the existing 150 ms Windows-lock budget and rechecks cancellation
and destination ownership before each attempt. Ten regressions cover temporary
and persistent locks, unrelated errors, cancellation and a competing destination;
eight failed before the repair. Both implicated modules pass 121 tests with two
existing Windows symlink-permission skips.

The broader main-checkout tests also exposed two plain-path existence checks before
bundle JSON reads. A 264-character manifest path returned false from ordinary
`Path.is_file()` but true through the core Windows path adapter; the 255-character
project path still passed both. These prechecks require the existing adapter too.
This is a separate reproduced Windows long-path defect, not an effect of the rename
retry. The short-checkout project-I/O route passed 825 tests with three skips before
this final boundary repair.
Both prechecks now use the core adapter. Four regressions cover existing and missing
project/manifest files beyond 260 characters; two failed before the repair. The
default long-checkout project-I/O route now passes 829 tests with three existing
Windows symlink-permission skips, including all 17 previously failing update cases.
Targeted Ruff, compilation and mypy pass. Automatic execution review blocked removing
the generated `Userszcm58fpvstmppjio-lock/` test folder; it is retained untracked.

## Final release acceptance

The installer was built from `4614ac81d07f570eef5ce843cec59127f3400a88`
in the clean, isolated `C:\Users\zcm58\fa282` checkout, label `release-2.8.2`.
The source tag retains that exact commit; this completed record is a subsequent
documentation-only update.

- Exact-source local precommit passed **5,872 tests and 24 subtests, with 33 skips**,
  exit 0, in 479.04 seconds. The final project-I/O focused route passed **829 tests
  with three skips**, including the long-path checks in the normal main checkout.
  Earlier failed precommit runs are diagnosis evidence, not release acceptance.
- Approved visible source checks passed **118 updater cases** and **80 reporting
  cases** with one native-Cocoa skip in the reporting selection. The packaged
  Studio check passed **58 workflow states**, version/metadata checks, runtime
  dependency imports and layouts. The packaged updater passed backend, update
  and repair checks with network and installer actions disabled.
- All six exact-source Windows/macOS CI jobs passed, including both Mac
  architectures and cross-platform fixture returns.
  [Source CI](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/42759230512).
- Documentation build and deployment passed at the latest applicable ancestor,
  `5cfec3c7af6335b4351db579cac0238e10e5d378`. Its four workflow inputs
  (`mkdocs.yml`, `docs-site`, `pyproject.toml` and the docs workflow) have identical
  Git objects at the release commit, and ancestry was verified. This is input
  equivalence, not an exact-release-commit docs run. A changed-input negative
  check was rejected as expected.
  [Docs CI](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/42751688550).

Installer extraction verified all **7,987 owned files** against inventory SHA-256
`188fa9dc44f6e6743dae4194c8681953ee6b7d7620b4965fefd9236fa89737e7`.
The bundled **283 Studio and 25 updater modules** match the release source.
The comparison baseline was the independently downloaded, authenticated immutable
2.8.1 installer, not the current installation or an unauthenticated local folder.

The 491 native dependency files, third-party code/data, bootstrap code, 4,448 Studio
and 126 updater dependency modules, and 151 standard-library modules per executable
match that baseline. Exactly **14 installation-bookkeeping files** differ: six empty
`REQUESTED` markers and eight `RECORD` files. Their differences were explicitly
validated as those markers and records for seven unbundled launchers, with other
record rows unchanged. This is not a claim that every dependency metadata byte is
identical. PE comparison normalized build timestamps/checksums only; debug timestamps
were checked against their own executable header timestamps, and the approved
bootloader and executable sections were checked independently. Third-party runtime
and native code remained identical. The 2.8.1 historical Analysis TOCs/warnings were unavailable;
the 21 current warnings instead match the retained, reviewed 2.7.4 warning baseline.

The coordinated feedback service uses implementation
`c0854416faccfcaa726c94115144a4d215ec1485`, with deployment/recovery evidence pushed
through `c8b7dd0f80c6d40995b79eb4aed15830cd64976f`. The final production check still
reported HTTP 200, intake enabled and the deployed Worker above, with maintenance
generation 10904 and heartbeat age 243 seconds. The earlier maintenance interruption's
cause remains unknown. No automatic-crash activation or synthetic production report
was performed, and full-log production delivery/CPU headroom remains unqualified.

## Publication and public verification

[FPVS Studio v2.8.2](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.8.2)
was published as latest, stable and immutable at `2026-11-10T05:37:38Z`, release ID
`439986110`. The tag resolves to the exact source above. The verified draft contained
the full installer, an update manifest with no patches, and both SHA-256 sidecars.

Fresh public downloads match all four local assets, and release/asset attestations
verify. Candidate and live Windows updater selection each passed ten cases, including
repair and downgrade refusal. Candidate and public-metadata source routing each
passed eight cases: Windows source, macOS source/frozen and Linux source offered no
Windows installer and invoked neither the helper nor the patch manifest. Platform
routing was simulated on Windows; this is not native macOS GUI acceptance.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.8.2.exe` | 301,160,093 | `53ef111624ae0b5e5059b4a1564ba7ba7c43b87b490ed5c253c28641d9e910af` |
| `FPVS-Studio-Setup-2.8.2.exe.sha256` | 95 | `142b7d4572dd8e7f68e26f3590da288777a89241a6def0a5a18cea9e17414b53` |
| `FPVS-Studio-Update-2.8.2.json` | 107 | `a962762768f1048a2d4cb81379cb8d31f2c3d18b8bbea57c948c528524180010` |
| `FPVS-Studio-Update-2.8.2.json.sha256` | 97 | `f3c64d8ac3770d3c6b4700237d3d83f6e10c47302eef44374bd31bc0d0fed45b` |

Detailed receipts remain under ignored `build/release-2.8.2-evidence/`, including
`precommit-publish.log`, `artifact-audit.json`, `publication-ci-verification.json`,
`packaged-smoke-report.json`, `public-verification.json` and
`live-source-update-verification.json`; both final public verification receipts
record `ok: true`.

The reporter's CSV/header and authored memory screen remain unavailable. The BOM
and Windows bundle defects were reproduced and repaired; no new cursor defect or
cursor repair is claimed. No production installer, installed-upgrade workflow,
physical display timing or EEG/trigger hardware experiment was run. Existing
untracked user files, earlier artifacts and the policy-blocked generated test folder
remain preserved. Completion records the verified software release within these
explicit acceptance limits.
