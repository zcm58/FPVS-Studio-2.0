# Per-Condition Stream Duration in Seconds

Status: Planned

## Purpose and confirmed decisions

Planning branch: `feat/condition-timing-and-reproducibility`. Implementation has not
started. Let each FPVS image or word condition have its own easily edited stream
duration, entered in seconds in the Timing & Session condition table.

Duration means the stimulation stream for **one presentation**. It includes blank
halves and within-stimulus sinusoidal contrast modulation. It excludes pre-stream
lead-in, instructions, participant tasks, waiting, breaks and feedback.
Repeated presentations are handled by the [repeat-count plan](per-condition-repeat-counts.md).

Changing a shared or condition-specific frequency preserves the requested duration.
If that duration cannot be represented by complete oddball cycles at the resolved
frame timing, **reject it and list valid durations**. Do not round, truncate the last
oddball cycle or silently substitute a different length.

## Current evidence and ownership

- `Condition.sequence_count` and `oddball_cycle_repeats_per_sequence` in
  `core/models.py` determine the current stream length.
- `core/compiler.py` compiles their product into one continuous RunSpec. Current
  seconds equal `sequence_count * cycles_per_sequence * oddball_every_n *
  frames_per_stimulus / refresh_hz`.
- `core/validation.py::validate_condition_repeat_cycle_consistency` currently rejects
  different sequence/cycle counts between conditions, and `gui/document.py` includes
  that check before saving. A UI editor alone cannot enable differing lengths.
- Guided Conditions does not expose stream duration. `Target Stimulus Repeats` is an
  advisory image-exposure target and must not be repurposed as a duration control.
- `core/frame_validation.py`, compiler fixation realization and duration guidance
  already own frame timing and feasibility checks.

## Implementation sequence

1. Define one authoritative condition-duration representation and compatible migration
   from saved cycle/sequence counts. Preserve each existing condition's actual stream
   duration and legacy continuous-sequence meaning; do not multiply it into session
   presentation count.
   Legacy projects can have no preferred refresh target. Retain their count-based
   timing until a valid refresh target is resolved; do not invent a 60 Hz display to
   assign historical seconds or silently freeze an estimated duration as authored truth.
2. Resolve seconds against the effective per-condition frequency from the
   [frequency plan](clear-presentation-frequency.md) and the compiled display refresh.
   Retain whole frames and complete oddball cycles as the execution contract.
3. Reject incompatible entries and display useful valid alternatives above/below the
   requested length. Selecting a listed alternative is an explicit user action.
   Define numeric precision deliberately: rounded display text for a valid choice,
   especially at 59.94 Hz, must remain usable without repeated validation failure.
4. Replace the inappropriate cross-condition uniformity restriction with appropriate
   per-condition validation while retaining paradigm/modifier-specific constraints.
5. Add per-condition seconds entry, effective duration, validation and recovery to the
   shared Timing & Session table. Refresh session estimates and fixation/stimulus
   exposure guidance from the same resolved counts.
6. Propagate requested/resolved timing consistently through persistence, templates,
   config/bundle interchange, RunSpec summaries and completed exports.

## Acceptance and verification

- Two eligible conditions can have different valid durations and save, reload,
  export/import and compile correctly.
- At exact 6 Hz with every fifth stimulus an oddball, 144 cycles represents a
  120-second stream. Legacy `sequence_count=2` with those counts remains one
  uninterrupted 240-second stream unless explicitly edited.
- Invalid/nonpositive/nonfinite values are rejected. Incompatible values list valid
  choices and do not mutate the project, reinterpret units or silently round.
- Changing frequency either preserves the requested valid seconds or rejects the
  coordinated edit with valid alternatives and no partial mutation. It never silently
  preserves image counts at the expense of the requested time.
- Stream duration excludes lead-in and participant screens/tasks. Session summaries
  distinguish stimulation totals from estimated overall elapsed time.
- Cover Continuous, 50% Blank and Sinusoidal images, word streams, supported display
  refresh rates, long/short conditions and fixation feasibility boundaries.
- Add registered GUI coverage for editing, validation, long messages and all eight
  steps at `1120x820` in both themes; run core/compiler/gui/project-I/O focused routes
  and repo precommit, with visible Qt/lab checks governed by existing rules.

## Scope limits

Do not change native AB burst/SOA timing, the separate pre-stream lead-in, task
durations, session presentation counts or image-exposure targets. Preserve specialized
masking/modifier constraints and report incompatible combinations rather than silently
weakening them. Resolve schema/version compatibility during implementation.
