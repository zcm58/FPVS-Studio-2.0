# Vertical image visual angle in Setup

Status: Completed

Shared image-angle controls and height-only persistence repair implemented and
verified with the safe Windows source checks. Visible Qt acceptance remains unrun.

## Task and acceptance

Researchers must be able to set the vertical image angle alongside the horizontal
angle in Setup's Image Size step, then save/reopen and run with those dimensions.
Reuse the existing natural-aspect, exact-box, contain and cover geometry contracts;
keep old projects' width-driven natural aspect unchanged until explicitly edited.
No new project schema, timing behavior or engine path is needed.

The existing two-card Image Size editor and its full-screen preview share the
controls. Add an Image sizing selector and Image height (deg) field to the stimulus
card: natural width/height keeps source proportions, while stretch/fit/crop enables
both axes. Preserve calibration, condition/role overrides, transforms and text
settings. Image controls remain hidden for native AB character and masking editors.

Setup must still fit 1120x820 in both themes with all mode labels and state text.
The preview's control panel must fit the same acceptance size. Keep concise labels,
accessible tooltips and keyboard order; no additional explanatory paragraph is needed.
Registered Qt tests cover control states, document synchronization, persistence and
layout. No visible Qt environment has been authorized, so actual visual checks are
reported separately from non-Qt verification.

## Work

- GUI focused baseline: 164 passed.
- Existing backend supports both dimensions and all required fit policies.
- Found an existing height-only save/reopen defect: omitted null width acquired the
  model's width default on reload. Repair omission handling without changing explicit
  invalid-input validation or the serializer format.
- Shared editor/preview controls implemented with precise angle fields and explicit
  sizing modes. Unauthored axes show `From image`; unrelated calibration changes
  preserve geometry. AB/masking retain their existing controls.
- Model and engine tests prove save/reopen and rectangular-image rendering for all
  five sizing choices while retaining schedules and source bytes.
- Independent source review found no additional production issues. Registered tests
  cover both themes, mode states, precise axes, editor/preview synchronization,
  persistence, invalid-edit recovery and hidden AB/masking image rows.

## Verification

- Core focused: 918 passed, one Windows symlink-permission skip.
- Models/engine modules: 199 passed, one symlink skip; five rectangular-image cases
  separately rerun successfully after strengthening the source-aspect assertions.
- GUI focused: 164 passed; Ruff and compilation passed. The first post-change run
  hit a transient Windows `WinError 5` renaming an unrelated image-import staging
  folder; the complete focused rerun passed without changing import code.
- Final repo precommit (`-Workers 4`): 5,181 passed, 32 platform/dependency skips.
  Changed-file Ruff/compilation, all 267 Windows source type checks, nine Darwin
  adapter type checks and repository audits passed. Counts above overlap.
  No Qt/native presentation was run.

## Manual visible smoke

At 1120x820, open Image Size in Light and Dark themes. Select width-driven and
height-driven natural sizing, then each two-axis sizing mode. Edit unequal angles,
change calibration, open the full-screen preview from a two-axis mode, save/reopen
and inspect the resulting settings. The existing height-natural preview entry rule
is preserved; Configure Presentation still supplies its scaled source preview.
Check all fields and labels fit, errors restore previous values, and AB/masking retain
their own size controls. No real participant session or hardware is required.
