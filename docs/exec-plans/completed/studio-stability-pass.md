# Studio startup and worker stability

Status: Completed

## Scope and evidence

- An injected failure to start the optional logging thread stopped Studio before
  the GUI entry point ran. It also left the process exception hooks and logger
  settings changed. Diagnostic startup should leave Studio usable when its own
  resources are unavailable.
- A fake PsychoPy window constructor left a graphics object in the exception
  traceback. Keeping the exception until GUI delivery released the object on the
  receiving thread. Use the existing presentation-thread cleanup when window
  construction fails, including during the fullscreen refresh check.
- Studio already drains its Qt workers after `QApplication.exit()` returns from
  the event loop. The independent updater returned directly, including in the
  visible smoke check when its deadline could interrupt worker cleanup. Use the
  same app-owned drain and return the original exit code.

## Verification

- The startup tests inject failures to start either diagnostic worker. They
  verify that application startup still reaches the GUI entry point, and that
  local logging and crash capture remain available when only inventory fails.
- The focused engine suite passed 653 tests. The simulated constructor
  failures cover experiment presentation and the refresh probe. The tests
  preserve the exception identity, cause, and constructor traceback while
  checking the thread that releases the failed window. Real display drivers
  were outside this check.
- The safe focused GUI suite passed 187 tests. It checks the original exit
  code across zero, one, or multiple drain cycles.
- The focused updater suite passed 377 tests. Four Windows symlink tests
  skipped because this account cannot create symlinks.
- The Windows precommit suite passed 6,630 tests with 41 platform or permission
  skips. Windows and Darwin type checks and the repository audits passed.
- In an approved visible Qt session, run the GUI `full` tier filtered to
  `test_native_process_shutdown_drains_worker_threads` and
  `test_application_starts_cache_work_before_root_setup_and_drains_on_failure`.
  These use a synthetic window or stub startup. The process test destroys the
  window before exercising both quit and direct exit with active workers and
  checks the exit status and native teardown. This pass did not run native Qt.
