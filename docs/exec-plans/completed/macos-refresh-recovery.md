# Bounded macOS refresh verification

Status: Completed

## Outcome and boundaries

Prevent a stalled fullscreen refresh probe from holding the Mac display and keeping
Studio shutdown pending indefinitely. Keep Windows primary, its measurement behavior
unchanged, and retain native-mode plus actual fullscreen verification. Do not change
project/session formats, frame schedules, Cognitive Load settings, or experiment data.

The existing Mac process adapter will own a bounded, cancellable refresh-only child.
Use that same adapter for automatic preflight as well as Setup detection, so a stuck
probe can be killed/reaped without killing a presentation session or acquired output.
Add optional cancellation to the existing progress task only for the Mac check.

## Acceptance

- [x] Setup and automatic Mac preflight share the protected refresh-only process.
- [x] A stalled child times out; cancellation/shutdown kills and reaps only the probe.
- [x] Invalid/failed/canceled measurements never verify a rate or start playback.
- [x] Windows dispatch and normal session finalization retain their existing behavior.
- [x] Safe fake/real non-graphics IPC tests cover timeout, cleanup, retry and cancellation;
  registered visible Qt tests cover Cancel and shutdown without PsychoPy windows.
- [x] Focused and precommit checks pass; commit/push integrate any remote changes.

## Investigation and physical limits

The installed pyglet 1.5.27 Mac fullscreen backend calls `capture_display()` and uses
a shielding-level window. Studio's subprocess wait has no timeout, the refresh dialog
has no Cancel action, and automatic preflight measures inside an otherwise unbounded
session process. PsychoPy's frame-count cap cannot bound a blocked native flip or
window close. These defects match the symptom; the exact GPU/OS stall has not been
reproduced. No relevant native hang report was found in the available Studio logs.

Do not rerun the reported physical fullscreen probe during this repair. Previous
visible-Qt approval covers fake-only widget checks; physical display/timing and kernel
hang resolution remain unqualified until a separately controlled acceptance run.

## Implementation and verification (2026-11-02)

- Runtime's public verifier dispatches the real Mac PsychoPy engine to the existing
  Mac refresh transport, including automatic session preflight. The child calls the
  private in-process verifier on its main thread, avoiding recursion. Windows/Linux
  continue through their original in-process verification path.
- Only refresh requests use a polled child with a 30-second deadline and cancellation.
  Stalled/canceled children are killed and reaped before private transport cleanup.
  Session execution retains its existing finalization behavior and has no forced
  refresh deadline. Failed preflight occurs before participant-visit reservation.
- Mac window kwargs disable the duplicate constructor timing check; required native
  mode/fullscreen observation, fixed-rate validation and compiled-frame QC remain.
- Mac Setup supplies a Cancel action and a thread-safe event. Shutdown and owner
  destruction also signal cancellation; late success cannot mark a canceled rate
  verified. Default progress tasks retain their non-cancelable behavior.
- A targeted native Qt rerun exposed a destruction-callback crash while disposing a
  completed task. Completion now detaches the owner callback before deleting the task.
  All seven isolated cancellation/cleanup cases then passed, followed by the entire
  58-case worker/Display suite. The suite's six Windows keyboard-focus assertions
  initially failed under Mac's native tab policy; its explicit test adapter now uses
  Windows tab behavior and restores the original app hint afterward, without changing
  macOS settings or product focus behavior.
- Targeted fake-engine/process checks: 207 passed. Focused Mac route: 1,405 passed,
  16 platform/native/filesystem skips. Repo precommit: 5,002 passed, 64 skips,
  24 subtests; Ruff, compilation, Windows mypy (266 files), Darwin adapter mypy,
  GC/docs/harness audits passed. An extra Darwin pass covered the verifier, settings
  editor and worker modules. Verification configuration passed. Counts overlap.
- Real non-graphics children prove timeout/cancel kill, reaping, transport cleanup and
  successful retry. Visible tests used fake measurements and synthetic projects at
  1120x820; no fullscreen PsychoPy measurement or hardware was run. The longer timeout
  message and Cancel controls fit their tested surfaces.

The physical OS freeze is not claimed reproduced or fully qualified. A system-wide
GPU/kernel deadlock may exceed user-space recovery; the separate Mac Phase 1 plan
retains physical display/presentation acceptance. The repaired software no longer
waits indefinitely on its disposable measurement process.

## Native CI evidence

[Run 41583072217](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/41583072217)
on source commit `79756a4` passed all six jobs. Primary Windows precommit passed
5,051 tests, 15 platform skips and 24 subtests. Apple Silicon and Intel each passed
1,411 checks with ten platform skips after clean managed-Python/engine installs.
Both cross-OS bundle chains passed. These are native software/service and synthetic
transfer results; no hosted fullscreen presentation window or EEG hardware was used.
