# macOS Test/Pilot display freeze

Status: completed

## Outcome and boundaries

Investigate the repeated physical Mac freeze during Cognitive Load Test Mode. Keep
Windows presentation unchanged and adapt only the Mac engine/display boundary.
Preserve compiled schedules, mandatory observed refresh verification, Retina geometry,
runtime finalization and project data. Do not repeat exclusive display capture merely
to reproduce a machine-wide lockup.

## Evidence and implementation

- The 20-second deadline covers the disposable refresh child, not playback. Current
  child output is discarded, leaving no persistent phase evidence after reboot.
- Installed PsychoPy 2026.2.5 waits without a deadline on its Mac DisplayLink callback
  inside `swapBuffers`. Failed DisplayLink initialization can leave the handler set.
- Pyglet 1.5.27 fullscreen captures the display with `CGDisplayCapture`, creates a
  shielding-level window and switches the OpenGL context to exclusive fullscreen.
- Adapt Mac presentation to a borderless primary-display-sized desktop window. Keep
  the request fullscreen and validate actual backing pixels; never silently use a
  smaller window if native geometry is unavailable.
- Bound the existing callback wait without disabling synchronization or copying the
  backend. Install the guard before the first flip for both verification and playback.
- Retain useful child diagnostics locally so future failures identify their phase.

## Verification

Run deterministic missing-callback/recovery and Windows-contract checks, Mac focused
verification and repo precommit. In the approved visible desktop, first inspect a
nonexclusive window, then test refresh and a task-owned copy of the downloaded project.
Observe abort/close and recovery. Record native evidence separately from automated
tests; no physical EEG/timing qualification follows from source tests.

## Progress

- Initial non-Qt regression selection: 52 passed.
- Mac adapter integration selection: 68 passed. Both Windows/Mac launch-confirmation
  Qt cases passed visibly at 700x380, including wrapped copy and long condition names.
- Mac focused: 1,430 passed/15 skipped; Windows mypy over 267 modules and Darwin
  adapter checks passed. Repo precommit: 5,026 passed/64 skipped/24 subtests before
  the final diagnostic-log regression case; final verification is recorded below.

## Native evidence, 2026-11-03

The local Apple Silicon Mac uses PsychoPy 2026.2.5 and Pyglet 1.5.27. A nonexclusive
1440x900 logical surface reported 2880x1800 backing pixels, Cocoa level 0 and
`fullscreen=False` at the Pyglet boundary. It observed 60.006 Hz, rendered 120 more
frames and closed normally. The OS display mode and project calibration were unchanged.

A deliberately disconnected callback raised the new explicit error after 1.091 s
and closed its native window. Retry through the production fresh-process probe
observed 60.005 Hz and exited normally. An exploratory second window in the same
process exposed an existing Pyglet Objective-C wrapper-cache error; production already
uses separate probe/session processes and one session window, so that unsupported
experiment is not claimed as a pass or a reason to patch dependency internals.

A task-owned copy of the Library Cognitive Load project passed real automatic refresh
verification and initialized foreground input and its presentation window. A supervised
interactive attempt waited for input and was stopped at three minutes. Computer Use
could inventory the desktop but could not target the unbundled Python window; its
first app-selection attempt timed out after the short probe had already exited.
The user was remote and could not supply local input. A subsequent real runtime run
used the public engine abort API five seconds after opening, honored abort during
`Backward-counting baseline` / `counting-ready`, exited normally and persisted an
aborted session plus exports. All 2,994 original project/stimulus input hashes matched.

The reported 08:57 freeze has no usable native Python stack. Unified logs show one
presentation child exiting before another window initialized and repeated denied
Input Monitoring requests. WindowServer continued logging. This supports playback
outside the probe deadline and unavailable input as contributors; it does not prove
a GPU/kernel freeze or the exact original stalled call. Child operation/readiness
logs now survive process exit through the existing bounded redacted support-log sink,
without separate crash-report registrations or participant payloads.

The upstream [PsychoPy 2026.2.5 backend](https://github.com/psychopy/psychopy/blob/2026.2.5/psychopy/visual/backends/pygletbackend.py)
contains the unbounded callback loop. Apple's
[CGDisplayCapture contract](https://developer.apple.com/documentation/coregraphics/cgdisplaycapture(_:))
describes its exclusion of other applications/system services from a captured display.

Literal Space/Escape/Command+Q/Command+Tab interaction and complete experiment
playback remain physical acceptance gates in the main Mac source plan. No claim of
EEG or physical timing qualification follows. This repair preserves native sync and
QC and cannot interrupt an arbitrary blocked native driver call.

## Final verification

Repo precommit passed: 5,027 tests, 64 platform/filesystem skips and 24 subtests.
Changed-file Ruff/compilation, Windows mypy (267 source modules), Darwin mypy
(eight adapter/engine owners), repository audits and documentation checks passed.
Harness configuration passed for all 15 scopes. Native and visible evidence above
is separate from those safe checks. Temporary projects, scripts and verifier runtime
are task-owned and removed after verification; original project data is preserved.
