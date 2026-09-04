# Sinusoidal Contrast Modulation

Status: Completed

## Approved Decisions (2026-09-04)

- Implement this as the third presentation mode alongside `Continuous Images` and
  `50% Blank Between Images`. The user-facing label is `Contrast Modulation`; the
  compiled value explicitly identifies sinusoidal contrast modulation.
- Use true contrast modulation, not opacity. The first release supports image
  conditions only and requires the project presentation background to be neutral gray
  (`#808080`) whenever any condition selects the mode.
- Sample one complete raised-cosine cycle from the compiled frame count:
  `0.5 * (1 - cos(2*pi*k/N))` for local frame `k` in a cycle of `N` frames. Normalize
  the sampled values only when an odd `N` would otherwise miss the continuous peak,
  so the displayed maximum is exactly 1.0. This is equivalent to `sin^2(pi*k/N)`
  before odd-sample normalization.
- Derive the envelope only from `frames_per_stimulus`. Do not hard-code 6 Hz or any
  refresh rate. At 60 Hz, authored base rates of 4, 5, and 6 Hz therefore compile to
  15-, 12-, and 10-frame envelopes respectively; approximate frame ratios continue to
  use the existing nearest-whole-frame policy and exported realized-rate warning.
- Add an explicit mode to `DisplayRunSpec`, with a continuous default for backward
  compatibility. Do not infer sinusoidal mode from `on_frames`/`off_frames`, because it
  uses the full cycle just like continuous presentation.
- Do not change the base/oddball role schedule, stimulus identity per cycle, trigger
  frames, fixation schedule, lead-in, sequence duration, or terminal offset flip.

## Summary

Add a third presentation mode that modulates each image with Rossion-style sinusoidal
contrast across its compiled stimulus cycle. The existing continuous and 50% blank
modes remain available and behaviorally unchanged.

## User Workflow

Users choose one of three presentation modes for each image condition. With `Contrast
Modulation`, the selected image remains assigned for the entire stimulus cycle while
its contrast rises smoothly from neutral gray to full contrast and returns toward
neutral gray. The Experiment step exposes Neutral Gray and validation explains that it
is required for this true contrast mode. Word conditions do not offer this choice.

## Implementation Boundary

- Extend the editable enum and supported template metadata with a sinusoidal value.
- Compile the explicit mode into `RunSpec` without changing base/oddball frame
  scheduling. Preserve loading of older compiled contracts by defaulting a missing
  mode to continuous.
- Keep a pure, deterministic, frequency-agnostic contrast-envelope helper in core.
- Validate image-only support and the neutral-gray background in core and runtime
  preflight; GUI controls reflect these rules rather than owning them.
- In PsychoPy playback, retain and draw the same prepared `ImageStim` for the full
  cycle while assigning its precomputed contrast value before each draw.
- Keep PsychoPy imports and rendering behavior inside `src/fpvs_studio/engines/`.
- Keep existing continuous and 50% blank hot paths unchanged.

## Tests

- Unit-test envelopes for 15, 12, and 10 frames (60 Hz at 4, 5, and 6 Hz), plus other
  compiled frame counts: first frame zero, sampled midpoint/full peak, final frame near
  zero, symmetry, bounds, and deterministic repetition.
- Compiler tests confirm all three modes reach `RunSpec`, sinusoidal events retain full
  cycle timing, and frequency changes alter only the derived frame envelope/cadence.
- Validation and preflight reject sinusoidal word conditions and non-neutral
  backgrounds with actionable messages; continuous and blank rules remain unchanged.
- Fake PsychoPy tests confirm `ImageStim.contrast` follows the precomputed per-frame
  sequence, stimulus identity changes only at cycle boundaries, and continuous/blank
  behavior remains unchanged.
- Registered GUI tests confirm the third mode appears for image conditions, is not
  selectable for words, persists through save/reopen, and fits the existing Setup
  minimum/default sizes without clipping.

## Non-Goals

- Luminance or RMS equalization.
- User-authored envelope shape, phase, amplitude, or protocol-specific frequency
  presets.
- Opacity fades or support for contrast-modulated words in the first release.
- Any change to the existing whole-frame cadence calculation.

## Progress

- [x] Approve scientific/product defaults and frequency-agnostic behavior.
- [x] Implement core/compiler/preflight contract and tests.
- [x] Implement PsychoPy playback and tests.
- [x] Implement GUI authoring/persistence and registered coverage.
- [x] Update canonical documentation and complete safe verification.

## Implementation Record (2026-09-04)

- Added the explicit third mode to editable project state and compiled `RunSpec`, with
  backward-compatible loading of older run contracts.
- Added core-owned frequency-agnostic raised-cosine samples, minimum-cycle validation,
  image-only and neutral-gray gates, and a reusable Contrast Modulation profile.
- Added precomputed PsychoPy contrast draw operations while leaving the continuous and
  blank playback paths, event identities, triggers, fixation, and terminal flip intact.
- Added image-only GUI selection, atomic word fallback to Continuous, neutral-gray
  authoring and guidance, profile persistence, and Setup Wizard review text.
- Focused verification passed for core (124 passed, 1 Windows symlink-permission skip),
  compiler (102 passed), project I/O (51 passed), runtime (180 passed), engine (170
  passed), GUI Ruff/compilation, and docs (9 passed). Repository precommit passed Ruff,
  compilation, mypy across 133 source files, audits, and 673 unit tests with the same
  Windows symlink-permission skip.
- Registered pytest-qt coverage was added but not executed locally under the repository
  policy. A visible PsychoPy playback smoke remains the hardware-facing acceptance
  path.
