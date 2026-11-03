# Mac Retina presentation geometry and fullscreen chrome

Status: completed

## Outcome

Correct the black first Cognitive Load task screen and hide the Dock/menu bar during
Mac presentation, keeping Windows primary and unchanged. Retain the nonexclusive
native window, display verification, compiled frame schedules and backing-pixel
calibration. Preserve normal macOS application switching and quit recovery. Add the
requested automatic resolution mismatch confirmation before Home/Run launches. The
user explicitly chose to save accepted target dimensions to the project; other
physical calibration and recording settings remain unchanged.

## Investigation

The refresh child completes and playback reaches window/keyboard readiness. The
expected first task has white text positioned from the 2880x1800 backing size.
A native shape/TextStim/TextBox2 framebuffer diagnostic renders all three, but at
twice the requested pixel geometry: the nonexclusive Retina window reports backing
pixels while the dependency's `setScale('pix')` and layout conversions double them
again under `useRetina=True`. Task body/footer positions consequently fall outside
the screen. The post-construction coordinate flag is normalized before stimuli are
created; native framebuffer storage, viewport, client size and content scale are
preserved. Constructor Retina selection remains enabled. A global view scale would
break normalized/height units and was not used.

## Work and verification

- Correct Mac pixel conversions at the existing adapter boundary; no per-widget
  or per-task coordinate adjustments.
- Use app-scoped native presentation options to hide Dock/menu bar and restore
  previous options on every exit. Never capture the display or disable recovery keys.
- Add fake-backed platform adapter tests and verify actual rendered pixel bounds,
  readable first-task text, graphics cleanup and native abort on a disposable project.
- Compare configured/detected backing dimensions in the existing local display
  confirmation for both launch paths. Save accepted target width/height/policy
  atomically before compile in the worker. Cancel/save failure preserves project data.
- Run focused Mac/engine checks, shared precommit and approved visible acceptance.
  Commit/push after verification; preserve original projects and settings.

The built-in display currently has fixed 60 Hz, with AppKit min=max 1/60 s. No VRR is
detected. External Adaptive Sync displays remain subject to the fixed-rate guard.

## Native evidence so far

The unchanged rectangle request (350x160 px) rendered at 700x320 before normalization
and exactly 350x160 afterward. Both legacy TextStim and TextBox2 now use the same
backing-pixel coordinates. AppKit requested/effective presentation options were 10
(HideDock|HideMenuBar) while active and returned to 0 after close.

The actual Cognitive Load first task (`counting-ready`) was captured from the native
front buffer. Its complete instructions and Space/Escape footer are visible inside
the 2880x1800 frame. The real runtime honored an automatic public abort after 20
frames, saved an aborted-session result and restored presentation options. No
original project data was edited by these native diagnostics.

Re-enabling the old coordinate flag in a disposable diagnostic reproduced a nearly
black first task, with only a clipped strip of glyphs along the top edge and the
footer outside the frame. The corrected native instructions occupy x=153..2723,
y=362..474; the footer occupies x=1021..1857, y=1642..1678. Both fit inside the native
2880x1800 backing frame. Final lifecycle verification again observed options 10 while
active, clean runtime abort/export and restoration to 0 after window close.

Presentation restoration is captured before activation and executes after Pyglet
closes its window. Tests simulate close resetting the options to zero and cover
activation/option-setting failures, callback failure and graphics/close failures.
Windows/Linux do not import AppKit or alter their existing coordinate/input paths.

## Resolution confirmation and acceptance

Both Home and Run now use the existing local display confirmation. Mismatch copy
shows configured/detected backing dimensions and makes **Update resolution and
continue** the primary action. Matching dimensions retain **Use for this test**.
`ProjectDocument.save_display_resolution` validates a candidate and uses existing
atomic persist-before-adoption ownership, preserving memory/disk on save failure.
The launch worker saves accepted pixel dimensions/policy before compiling the
local calibration copy. Physical width, viewing distance, preferred refresh and
recording settings remain as authored. Cancel performs no write.

Accepted Mac launches validate the new local copy during compilation rather than
blocking on the old display's validation report. Failed compilation/save stops before
playback; retry works. Windows retains its original early validation and launch path.
There are no new persisted fields, project paths or acquisition fallbacks.

## Verification

- Repo precommit: 5,059 passed, 64 platform/filesystem skips, 24 subtests. Changed-file
  Ruff/compilation, Windows mypy (267 modules), Darwin mypy (nine owners), repository
  audits and docs hygiene passed.
- Focused Mac before the final cleanup-edge cases: 1,459 passed/15 skips. The final
  shared suite includes those unit cases and the additional failure-restoration tests.
- GUI focused: 154 passed/10 skips; approved visible Mac resolution coverage: 36
  passed, including matching/mismatched, 520x360 and 600x380, long values, both launch
  surfaces/Test/Pilot, Cancel, save failure, stale validation and compile failure.
- The source guard and constructor tests exercise installed PsychoPy's actual
  coordinate formulas under fakes without opening graphics. Native rendered-pixel
  evidence above is separate from the safe suite and verifies the real first screen.
- An initial concurrent type-check attempt shared a cache across Windows/Darwin and
  produced invalid Windows-stub errors. An isolated cache and sequential type passes
  passed without any platform check waivers or Windows source changes.

Full human-driven sessions, physical keyboard/menu shortcuts, other displays/scaling
and EEG/physical timing qualification remain in the main Mac source acceptance plan.
Native diagnostics used automatic public abort; they do not claim a complete session
or manual keyboard acceptance. Temporary demo files/runtimes/caches are removed after
verification; one rendered-frame artifact is retained locally for review.
