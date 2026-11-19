# Fit pre- and post-condition task screens

Status: Active

## Current baseline

The fix shipped in [Studio 2.9.1](../completed/release-2.9.1.md) and remains in
3.1.0. Test/Pilot and recording use the same engine path. The renderer uses the
realized PsychoPy viewport for responsive placement and window-height fractions,
and fits positioned content and hitboxes together before the first flip. The
reported Creatine case has an eight-image choice grid at 1920 × 1080, 31 cm screen
width and 80 cm viewing distance.

## Remaining acceptance

- [ ] On the affected laptop, use a copied Creatine setup and run the short
  fullscreen Test/Pilot at both 125% and 150% Windows scaling with the reported
  resolution and calibration. Verify the study screen, prompt and all eight
  options fit, clicks align with their intended choices, and the test transitions
  to and from the timed image stream as authored.
- [ ] Record the build, display mode, Windows scale, drawable viewport if
  available, and observations at each scale. Note clipping or click drift with
  the exact screen and scale if either recurs.

Close when the laptop operator and engine maintainer confirm the two native
runs against the [participant task renderer contract](../../ENGINE_INTERFACE.md#modular-task-rendering).
Simulated DPI scales and packaged smoke provide separate regression evidence.

## Verification record

November 19 follow-up on the Studio 3.1.0 feature branch passed 648 focused
engine tests, including the Creatine image grid at simulated 100%, 125% and
150% scales and native-handler click mapping. The authored Creatine fixture
compiled at the reported 31 cm screen width and 80 cm viewing distance
from an isolated copy of its configuration and stimuli. The office PC has
not been identified as the affected clipping laptop. Acceptance still
requires both Windows scales on the affected laptop.

At 150% Windows scaling on the office PC, the fullscreen engine reported a
1280 × 720 drawable viewport. Both copied Creatine image and word grids fit
their prompts and eight choices after the first draw. Synthetic mouse events
through the native window handlers selected the intended target in each grid.
The isolated check exercised the choice renderer. The complete Test/Pilot
transitions and physical clicks on the affected laptop remain open.

Engine coverage exercises smaller and differently shaped viewports, the exact
Creatine grid and prompt, and clicks at simulated 100%, 125%, and 150% content
scales. Timed FPVS geometry and compiled timing are outside the fit calculation.

Engine focused verification passed all 629 tests. Runtime focused verification
reported 1,114 passes, four skips, and two failures. Both failures passed in
a serial rerun using a short temporary path. Windows and macOS type checks,
repository audits, and docs focused checks passed. The repository-wide pytest
run reported failures and was stopped before its summary to shorten verification.
