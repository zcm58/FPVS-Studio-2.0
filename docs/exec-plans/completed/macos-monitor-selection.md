# macOS experiment monitor selection

Status: Complete (source implementation; physical Mac acceptance remains unperformed)

## Workflow and acceptance

Extend the existing launch selector to macOS source Test/Pilot sessions. Discover
independently addressable active monitors when launching; prompt only for multiple
monitors and preselect CoreGraphics' current primary display on every invocation.
Continue carries that display through local calibration, refresh verification, the
bounded probe child and presentation. Cancel ends the launch before participant entry.
The explicit Check refresh rate action uses the same selection flow. No monitor
choice is persisted and no operating-system display settings are changed.

Reuse the existing compact dialog and Continue/Cancel actions at its 520 × 220
minimum and 560 × 240 default. Registered GUI coverage must check Mac and Windows
labels, primary/default selection, one-monitor bypass, cancellation, errors, changing
primary display and Home/Run/calibration/probe propagation. Preserve local test
resolution confirmation and existing fixed-rate, no-EEG, source-only Mac restrictions.

## Boundaries

- Runtime owns lazy native enumeration, CG display identities, selected mode detection
  and process/probe request validation. Enumeration must not reject a variable-refresh
  primary before an operator can choose a fixed-refresh external display.
- The existing transient display_device_name launch option carries macos:<CGDisplayID>.
  Compiled contracts and project formats remain unchanged.
- Engines map that native identity to current Pyglet screens, retaining nonexclusive
  Mac presentation and Retina backing validation. No screen-order assumptions or
  fallback to another display when the chosen display disappears.
- GUI owns the choice and calibration confirmation, preserving existing Windows work.

## Verification and manual acceptance

Run focused native/IPC/engine fake tests, GUI/macOS focused checks and repository
precommit. This Windows host cannot qualify native Mac presentation. Do not run Qt
locally without explicit approval. Record source checks separately from physical
multi-monitor acceptance.

Manual smoke on a Mac: launch with one monitor and confirm no selector; attach an
extended display and verify primary preselection, cancellation and presentation on
each display. Change the primary display, reorder displays above/left and use mixed
Retina/non-Retina scaling. Confirm calibration and refresh checks use the selection,
test disconnection before launch, and check Escape, app switching, probe cancellation,
cleanup and relaunch. Mirrored outputs should offer one independently drawable choice.

## Implementation record

- Reused the Home, Run and Check refresh rate selector on macOS. Native enumeration
  runs in the existing worker, uses CoreGraphics' primary identity and omits mirrored
  secondary outputs. A single independent display continues without a prompt.
- Carried the transient identity through local calibration, session launch and the
  bounded refresh child. Native mode checks and presentation resolve that same
  identity, with explicit failure if it disappears or the child reports another display.
- Mapped CoreGraphics identities to current Pyglet screens and verified the actual
  AppKit window display and Retina backing dimensions before the first presentation
  flip. Mixed-scale backing metadata is refreshed through the existing backend.
- Added fake native/IPC/engine regressions and registered GUI coverage for both
  platforms, primary changes, cancellation, selection propagation and minimum/default
  dialog sizes. Added the new non-Qt tests to the macOS verification scope.
- Focused native selection checks: 99 passed. Focused IPC/recovery checks: 145 passed.
  Focused engine checks: 260 passed, 1 existing version skip. GUI-scope non-Qt checks:
  180 passed. Targeted Windows and Darwin type checks and verification configuration
  validation passed. Documentation checks passed (13 tests).
- The complete macOS focused route passed: 1,787 tests, 27 platform/permission/version
  skips; changed-file lint/compilation and nine-target Darwin type checking passed.
- Repository precommit with four workers passed: 6,237 tests, 34 platform/permission/
  version skips, changed-file lint/compilation, 287-source Windows type checking,
  nine-target Darwin type checking, repository audits and documentation hygiene.
- Final read-only cross-layer review found no correctness blockers. `git diff --check`
  passed. Unrelated edits and retained user output were preserved. The harness left
  temporary directories under `build/test_env/`: `pytest-42204-a05f2777bb`,
  `pytest-34944-2dff7f9d7d` and `pytest-34944-46dcad3808`. Automatic approval review
  rejected their scoped cleanup with "blocked by policy"; those generated files
  remain in place.
- Native macOS execution, physical multi-monitor behavior and visible Qt checks were
  not run on this Windows host. The manual path above remains external acceptance;
  automated source/fake results do not qualify display timing or physical placement.
