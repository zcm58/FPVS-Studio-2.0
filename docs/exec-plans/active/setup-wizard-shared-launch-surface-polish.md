# Setup Wizard Shared Launch-Surface Polish

## Summary

Refine Setup Wizard presentation without changing Welcome or Home. The Setup Wizard
should share the same launch-surface border/background styling method as Welcome and
Home, then each wizard step should be compacted so its content fits the existing
compact window without clipping.

## Current Status

- [x] Step 1: Unify Setup Wizard outer styling with the shared launch-surface
  selector and border treatment used by Welcome/Home, including moving the top
  progress stepper inside the shared frame and keeping that frame at a stable
  expanding height instead of resizing it to each page. The progress stepper is
  anchored to the top of that shared frame, independent of each step's content.
- [ ] Step 2: Adjust Project vertical spacing so the full page fits inside the
  compact setup frame.
- [x] Step 3: Combine Conditions and Images into one compact Conditions workbench
  so creating/naming conditions, assigning base/oddball folders, and creating
  control conditions happen in one logical step. The wizard now uses six steps:
  Project, Conditions, Experiment, Fixation, Response, and Review.
- [x] Step 4: Remove the redundant standalone Images page and route old Images /
  Stimuli / Assets step aliases to Conditions.
- [ ] Step 5: Fix Experiment vertical clipping and spacing.
- [ ] Step 6: Fix Fixation vertical clipping and make the section more compact.
- [ ] Step 7: Widen Response content horizontally while preserving current controls.
- [ ] Step 8: Adjust Review spacing so the decision card fits cleanly.

## Implementation Notes

- Leave Welcome and Home unchanged.
- Prefer shared GUI component/theme selectors over local page stylesheets.
- Keep the main Setup window size policy unchanged.
- Do not change project schemas, compiler/runtime behavior, or setup validation rules.
- Use focused GUI tests and a manual `1040x680` smoke pass after each substantial
  layout slice.

## Verification Plan

- `python -m pytest -q tests\gui\test_layout_dashboard.py tests\gui\test_conditions_session_fixation.py`
- `python -m pytest -q tests\unit\test_harness_docs.py`
- Ruff on touched Python files.
- `.\scripts\check_gui.ps1`
- Manual smoke: open Setup at `1040x680`, visit all six steps, confirm no clipping,
  no required vertical scrolling, and bottom navigation remains visible.
