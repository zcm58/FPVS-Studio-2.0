# Sinusoidal Contrast Modulation

Status: Planned

## Summary

Add a presentation mode that modulates each stimulus with Rossion-style sinusoidal
contrast across the stimulus cycle. The current continuous and 50% blank modes remain
available; sinusoidal modulation becomes an explicit user-facing choice.

## User Workflow

Users choose a condition template or presentation mode that describes the stimulus
contrast behavior. When sinusoidal mode is selected, each image fades in from the
background, reaches full contrast at the middle of its cycle, and fades back out by the
end of the cycle.

## Implementation Boundary

- Add a new duty-cycle or presentation-mode value for sinusoidal contrast.
- Compile the mode into `RunSpec` without changing base/oddball frame scheduling.
- In PsychoPy playback, draw the same image for the full stimulus cycle while updating
  contrast frame-by-frame from a deterministic sinusoidal envelope.
- Keep PsychoPy imports and rendering behavior inside `src/fpvs_studio/engines/`.
- Keep existing continuous and 50% blank behavior unchanged.

## Tests

- Unit tests for the sinusoidal contrast envelope: first/last frame near background,
  midpoint at full contrast, deterministic values for a fixed frame count.
- Compiler tests confirming the selected mode reaches `RunSpec`.
- Fake PsychoPy engine tests confirming `ImageStim.contrast` changes per frame in
  sinusoidal mode and remains unchanged in continuous mode.
- GUI tests confirming the mode is selectable only where supported and persists through
  save/reopen.

## Assumptions

- The first implementation follows contrast modulation only; it does not add luminance
  equalization or protocol-frequency configurability.
- Frame timing remains locked to the existing compiled frame schedule.
