# Clear Presentation Frequency and Condition Overrides

Status: Planned

## Purpose and confirmed decisions

Planning branch: `feat/condition-timing-and-reproducibility`, created from `master`
at `11640cb`. This plan records the user interview; implementation has not started.

Make stimulus presentation frequency easy to find and edit for FPVS image and word
conditions. New experiments retain a shared default of 6 Hz. Conditions normally
inherit that shared frequency, with an explicitly confirmed per-condition override.
Native Attentional-Blink rate/SOA behavior is outside this feature.

Put the shared experiment frequency above a per-condition timing table in
**Timing & Session**. Group effective frequency, stream duration in seconds and
presentation count for each condition there, rather than distributing the controls
across Design, Conditions and Timing. Distinguish stimulus frequency from monitor
refresh rate and show inherited versus custom values clearly.

Before applying a condition-specific frequency change, show this requested warning
with Yes/No buttons, defaulting to No:

> Warning: you're about to change the stimulus presentation frequency of this condition. It will not match the other conditions in your experiment. Are you sure?

No leaves the previous value intact. Yes applies only the selected condition's
validated override. Offer a clear return to the shared experiment frequency.
Changing frequency preserves the requested stream duration, not the image count;
the [duration plan](per-condition-stream-duration.md) owns representability errors.

## Current evidence and ownership

- `core/models.py::ProtocolSettings.base_hz` already owns the shared 6 Hz default;
  `Condition` currently has no frequency override.
- `core/compiler.py` resolves ordinary condition timing from the project protocol.
- `gui/experiment_designer_dialog.py` exposes the small image-only `Stream rate`
  control; `gui/document_conditions.py` currently applies it project-wide.
- `gui/runtime_settings_page.py` has a `Base rate` editor, deliberately hidden for
  image-only projects. Word authoring uses that same project setting.
- `core/frame_validation.py`, `core/validation.py` and `core/contrast_modulation.py`
  own frame quantization and presentation-mode feasibility. Reuse those owners.

## Implementation sequence

1. Add a compatible optional condition override and one core-owned effective-rate
   resolution path. Preserve saved shared rates and existing projects without
   overrides; do not reset customized experiments to 6 Hz.
2. Use the resolved rate consistently in compilation, validation, display previews,
   oddball-rate summaries, duration calculations, fixation feasibility and exports.
   Runtime/engines continue consuming frame-based compiled contracts.
   Replace shared frame-count assumptions in session compilation and fixation
   guidance with that same per-condition resolver.
3. Expose the shared rate and per-condition inherited/custom state in Timing & Session
   using existing components. Remove the editable Design rate control or make it
   read-only; it must not bypass the warning, duration validation or chosen edit location.
4. Add the confirmation and reset-to-shared flow. A shared-rate edit updates inherited
   conditions; explicitly overridden conditions retain their values until reset.
   Validate every affected condition before committing a shared-rate draft. An invalid
   shared edit, override or reset lists valid durations and leaves all saved values
   untouched; allow coordinated frequency/duration drafts to apply atomically.
5. Preserve complete oddball cadence, existing approximation reporting and mode rules:
   rate cannot exceed refresh, 50% Blank needs an even frame count, Sinusoidal needs
   its minimum frame count, and image-only modes remain unavailable to word conditions.

## Acceptance and verification

- A new project shows a shared 6 Hz frequency; an existing customized project keeps
  its saved rate. All unmodified conditions inherit the shared value.
- Declining the warning changes no condition/project value. Accepting a valid override
  changes only that condition. Reset restores inheritance.
- Image and word conditions compile with their own effective rates. Requested and
  realized frequencies remain visible when display quantization differs.
- Frequency changes never silently change the requested duration or loosen fixation,
  oddball, masking/modifier or display constraints. Report infeasible combinations.
  Invalid changes to either shared or per-condition timing commit no partial edits.
- Cover source/compiled/config/bundle round trips and mixed inherited/custom conditions.
- Registered GUI coverage checks warning acceptance/rejection, drafts, summaries and
  all relevant states at the eight-step wizard's `1120x820` size in both themes.
- Use core/compiler/gui/project-I/O focused routes and repo precommit. Qt and physical
  display checks require their existing approved visible/lab environments.

## Dependencies and scope limits

Coordinate the single Timing & Session layout with the duration and repeat-count plans.
Do not add a new top-level screen or change native AB timing, participant tasks or
unrelated visual design. Preserve trigger codes, meanings and stimulus-role anchoring
while core recompiles event frames/counts for the new timing; retain hardware pulse
spacing validation. Update canonical workflow/RunSpec docs
and compact architecture/routing guidance when implementation changes those contracts.
