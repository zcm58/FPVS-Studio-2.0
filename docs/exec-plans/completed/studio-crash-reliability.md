# Studio crash reliability

Status: Completed

## Scope and evidence

The user requested current upstream changes and diagnosis and repair of Studio crashes,
including online features. Master includes origin/master through ac62fa8 via merge
313d9b4. Windows recorded native ucrtbase fatal exits and one shiboken access violation;
existing Python session logs contain no native stack. Network failures are caught, but
ordinary GUI workers are outside the updater's application shutdown coordinator.

## Implementation boundaries

- Reproduce worker teardown and startup in explicitly approved visible synthetic Qt
  subprocesses, with isolated settings and no production HTTP or PsychoPy launch.
- Keep all GUI workers alive until native thread completion and drain shutdown through
  the existing application coordinator without waiting on the GUI thread.
- Preserve presentation thread reuse and public task signals; protect callbacks after
  requester widgets disappear.
- Add bounded local native/Qt diagnostics through the existing support seam if needed
  to distinguish remaining native failures. Preserve privacy and explicit submission.
- Inspect online startup, cancellation, invalid responses, and local dependency/installer
  consistency. Fix demonstrated problems; report external-state limitations accurately.

## Verification and progress

- [x] Merge latest upstream, preserving local changes.
- [x] Review Windows crash events, support logs, current worker and online lifecycles.
- [x] Run focused gui/library/data-sharing/updates checks.
- [x] Obtain explicit approval for visible synthetic Qt verification.
- [x] Reproduce failures and add regression coverage.
- [x] Repair demonstrated crash paths and add useful diagnostics.
- [x] Run focused checks, repo precommit, and approved visible Qt coverage.
- [x] Update canonical ownership/workflow docs and summarize evidence and residual risks.

## Reproductions and repairs

- A synthetic QWidget deletion with an active BackgroundTask aborts with Qt's
  `QThread: Destroyed while thread ... is still running`. Disposable/progress threads
  and task owners now belong to the app coordinator, with stale-requester result guards.
- On the installed dependency version (Qt/Shiboken 6.11.2), releasing presentation
  wrappers at QThread.finished reproduced access violations (shiboken offset 0x17471;
  the installed Studio event used 0x1747a). Waiting for native cleanup outside the GUI
  before releasing wrappers removes this race. This also applies to online UpdateJob
  workers. Matching module/nearby offsets supports this diagnosis but does not prove
  that every historical installed crash had the same cause; no native dumps survived.
- Shutdown previously ignored a five-second presentation wait failure and released
  running-worker references. The app now drains all tasks asynchronously with no cutoff.
- Default LibraryClient construction could raise before its startup job existed when
  per-user cache settings were invalid. Construction now occurs in the existing worker
  and produces the recoverable/offline prompt.
- Native faults and Qt messages were missing from Python-only session logs. Local
  native capture and Qt warnings/fatal breadcrumbs now use the support logging seam,
  preserving privacy, retention, explicit review and submission.
- The local development environment contains Qt 6.10.2, below the source's minimum
  6.11.2. An isolated ignored build/crash-check-deps directory supplies exact 6.11.2
  dependencies for verification; production dependency bounds were not changed.
- Actual installed metadata/inventory are 2.4.1 with matching critical Qt DLL hashes,
  but the Windows uninstall registration reports 1.5.3. This can affect updater/repair
  selection. The trust guard stays strict; registry identity is not fabricated.

## Final verification

- Repo precommit: Ruff, compilation, mypy and repository/docs audits pass; 2,860 non-Qt
  tests pass, 11 skips for unavailable Windows symlink permissions. The final support
  changes were included. After QSettings harness changes, repo focused passes (52 tests),
  driver/registry checks pass (20 tests), and CheckConfig passes (14 scopes).
- GUI focused: 17 pass. Docs focused: 10 pass.
- Exact Qt 6.11.2 visible crash/startup/online coverage: 149 pass, including window
  destruction while busy, quit/direct exit, a six-second presentation task, 30-cycle
  background/presentation/online reuse with forced GC, real Studio bootstrap with fake
  Library responses, invalid startup cache settings, and native fatal capture.
- Setup/closing follow-up: 169 pass, three requested 1448x1086 window sizes are clamped
  to 1448x1061 by this Windows desktop; one stale fake importer signature was corrected
  and rerun successfully. The separate timing-editor case that timed out in the broader
  combined GUI run passes independently (two variants). All targeted native and online
  runs after the fix completed without an unexpected native crash.
- The full GUI tier is not green: earlier combined runs exposed existing GUI assertions
  and a timeout. This work does not claim comprehensive visual acceptance. Changed
  workflows use existing Library prompt geometry (640x420/700x460); the prompt's ready,
  busy, error and connected layout tests pass. No presentation engine, live HTTP,
  real lab credentials, installer launch or physical hardware acceptance was performed.
- Native diagnostic capture is tested in a child process; its intentional Qt fatal
  event leaves a redacted local breadcrumb and pre-abort thread tracebacks. Normal
  fault handlers alone do not reliably capture Windows fast-fail exits.

## Delivered source files

Production: `gui/workers.py`, `gui/update_lifecycle.py`, `gui/thread_completion.py`,
`gui/library_access_dialog.py`, `gui/application.py`, `gui/qt_diagnostics.py`, and
`support/diagnostics.py`. Tests: `tests/conftest.py`, GUI workers/startup/Library/
diagnostics/update/Welcome modules, `tests/qt_test_files.txt`, and support unit coverage.
Architecture, agent routing, GUI/support contracts and related active plans are updated.

The downloaded comparison dependencies and temporary probes are removed after testing;
ignored XML/log reports retain the verification evidence. Source fixes remain reviewable
in the working tree. The installed 2.4.1 executable was not rebuilt or replaced, and no
changes were pushed. Every reproduced crash path in this investigation is fixed; the
historical events without native dumps cannot all be attributed conclusively.

## Verification environment follow-up

Windows QSettings ignores the harness's APPDATA override. Explicit INI UserScope and
SystemScope paths are now set only for opted-in Qt runs, and native startup subprocesses
also set their paths. The actual Studio INI retained its pre-test timestamp (16:18:27)
and original non-synthetic root; no evidence of an on-disk preference change was found.
A read-only hash/temporary backup was used for verification; the file hash stayed
37555D400BEACF3C8ED98A03C41EA18FA95C1F65071C8CA7B11F9FCCF696AF7A.
A regression checks the actual
QSettings file location against the workspace profile. Ordinary collection remains
Qt-free (the registry/driver checks pass, 20 tests).
