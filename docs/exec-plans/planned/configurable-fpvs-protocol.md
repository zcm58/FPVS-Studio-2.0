# Configurable FPVS Protocol

Status: Planned

## Summary

Make the current fixed protocol, `6 Hz` with an oddball every `5th` image and `146`
oddball cycles per condition, more configurable while preserving those values as the
default.

## User Workflow

Users can keep the default protocol or configure base frequency, oddball interval, and
condition length from setup. The UI should show derived values such as oddball frequency,
total stimuli, and condition duration before launch.

## Implementation Boundary

- Move base frequency and oddball interval from fixed template constants into explicit
  editable project/template settings.
- Keep defaults at `6 Hz`, oddball every `5th` image, and `146` oddball cycles.
- Keep timing represented in frames after compilation.
- Validate selected protocol settings against display refresh rate before launch.
- Keep session randomization, fixation scheduling, triggers, and asset resolution
  behavior unchanged except where derived timing values require recalculation.

## Tests

- Model and compiler tests for defaults and configured base frequency/oddball interval.
- Refresh-compatibility tests for supported and unsupported combinations.
- GUI tests confirming derived duration/oddball frequency update when settings change.
- Runtime preflight tests confirming unsupported timing cannot launch silently.

## Assumptions

- The first implementation does not attempt arbitrary waveform or contrast modulation.
- Existing projects without these fields migrate to the current defaults.
