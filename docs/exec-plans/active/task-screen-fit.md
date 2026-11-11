# Fit pre- and post-condition task screens

Status: Active

Use the realized PsychoPy viewport for participant task layouts in both Test/Pilot
and recording. Preserve timed FPVS geometry and compiled timing. The reported
case is Creatine's exact eight-image choice grid at 1920×1080, 31 cm screen width,
and 80 cm viewing distance.

- Resolve responsive placement and window-height fractions from the drawable
  viewport. Verify against smaller and differently shaped viewports.
- Fit positioned task content before its first flip. Verify that the Creatine
  grid and its prompt fit at the reported calibration and that the rendered
  targets accept clicks at simulated 100%, 125%, and 150% content scales.
- Run engine and runtime checks and repository precommit. For visible acceptance,
  run the same short Creatine Test/Pilot at 125% and 150% on the affected laptop.
  Check the study screen, all eight options, click alignment, and the transition
  into the timed image stream.

Engine focused verification passed all 629 tests. Runtime focused verification
reported 1,114 passes, four skips, and two failures. Both failures passed in
a serial rerun using a short temporary path. Windows and macOS type checks,
repository audits, and docs focused checks passed. The repository-wide pytest
run reported failures and was stopped before its summary to shorten verification.
Visible laptop acceptance remains pending.
