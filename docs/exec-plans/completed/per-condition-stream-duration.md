# Per-Condition Stream Duration in Seconds

Status: Completed

## Purpose and confirmed decisions

Planning branch: `feat/condition-timing-and-reproducibility`. Implemented on this feature branch. Let each FPVS image or word condition have its own easily edited stream
duration, entered in seconds in the Timing & Session condition table.

Duration means the stimulation stream for **one presentation**. It includes blank
halves and within-stimulus sinusoidal contrast modulation. It excludes pre-stream
lead-in, instructions, participant tasks, waiting, breaks and feedback.
Repeated presentations are handled by the [repeat-count plan](../planned/per-condition-repeat-counts.md).

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
   [frequency plan](../completed/clear-presentation-frequency.md) and the compiled display refresh.
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

## Execution progress and UI brief

- Frequency plan pushed as 3200a42. This plan adds seconds beside its frequency
  controls in the existing table; no new screen or change to AB timing.
- The author enters stream-only seconds and applies the timing draft. Errors retain
  the draft/project and show usable neighboring complete-cycle durations.
- Preserve existing legacy count timing until an actual refresh target is known.
- Verify core/compiler/config/bundle behavior, safe GUI checks and repo precommit;
  registered GUI coverage covers both themes at 1120x820 without local Qt execution.

## Implementation decisions

- `Condition.stream_duration_seconds` is optional. Null preserves legacy count-based
  timing; no load-time conversion assumes a monitor refresh target.
- `resolve_condition_stream_timing` is the core owner for exact counts/frames and
  resolved seconds. Every count/duration consumer uses this result.
- An explicit seconds edit normalizes the condition's continuous sequence/cycle
  counters to one stream of the resolved total cycles. This permits any complete-cycle
  duration without an artificial divisibility rule inherited from old sequence counts.
- Unchanged legacy sequence_count=2 and cycles=144 remains one continuous 240-second
  stream at exact 6 Hz. It never becomes two session presentations.
- Nine decimal places plus a 1e-6 frame absolute floating-point tolerance make valid
  choices at 59.94 Hz reusable as typed input; no relative cycle rounding is accepted.
- Explicit durations use Project 1.12/config 1.10 capability versions; absent optional
  fields preserve older payload shapes.

## Verification result

- Compiler focused: 549 passed. Core focused matrix: 156 passed.
- Consumer/config/bundle/masking checks: 162 passed; runtime/template checks: 108
  passed; final duration-default propagation regression run: 21 passed.
- Safe repository suite: 4053 passed, 12 Windows symlink skips, 24 subtests passed.
  Its two failures exposed generic schema expansion and AB diagnostic precedence.
  Both were fixed, with 193 compiler/AB regressions and 131 model/template/config
  regressions passing afterward (one expected Windows symlink skip in the latter).
- Final changed-file Ruff/compilation, full-source mypy and repository audits passed.
  The pre-existing untracked helper lint exclusions recorded in plan 1 remain the only
  difference from the standard precommit command; the full safe unit suite is unchanged.
- Registered GUI tests cover duration drafts, suggestions/typed values, cadence,
  template defaults and compact sizing. Qt and physical display checks were not run.
- Requested/resolved stream seconds are exported without changing participant task
  response exports. RunSpec remains the frame contract and runtime preflight independently
  checks its requested-duration metadata.
