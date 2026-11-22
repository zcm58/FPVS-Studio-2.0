# Reuse the key filter during timed passive fixation

Status: Completed

Date: 2026-11-22

## Workflow and evidence

A timed passive fixation step displays its scheduled frames and polls for Escape
after each flip. In the [PsychoPy task renderer](../../../src/fpvs_studio/engines/psychopy_tasks.py),
`_handle_keys` calls `_key_list_for_step` on each poll. For a timed step with
`response_kind == "none"`, that helper builds the same one-item Escape list on
every frame. A fake-window run through the real renderer counted 120 list
constructions across 120 fixation frames.

## Scope and behavior to preserve

Prepare one Escape filter per timed passive step and use it for the existing
polls. Check that the supported keyboard backends accept reuse of the filter
without mutating it. Keep the poll immediately after each flip, with the same
filter contents and `waitRelease` and `clear` arguments. Preserve first-flip
event clearing and clock reset, frame and terminal-event order, duration,
Escape and external abort semantics, and the result fields. Keep response-driven
and text input on their existing paths. The engine continues to consume the
resolved step under the [task rendering contract](../../ENGINE_INTERFACE.md#modular-task-rendering).

## Verification

- Compare fake-window draw/flip/poll order, poll arguments and task results before
  and after for a complete timed step, an Escape during fixation, and an external
  abort. Assert one filter construction for the 120-frame case. Exercise a
  response-driven step and text input to check the neighboring paths.
- Run engine focused verification and repo precommit. Treat the measured
  construction count as source evidence. Quantify display jitter or EEG timing
  only with physical timing evidence.

## Implementation and results

Each timed passive step prepares its Escape list before the render loop. The
renderer passes it to the existing poll after each frame flip. The supported
PsychoPy keyboard backends read the list without mutating it. Response-driven,
untimed, and text steps keep their original key filters.

Ten fake-window comparisons against the previous renderer matched the exact
result fields, first-flip clear and clock resets, draw/flip/poll order, poll
arguments, and terminal blanks. The cases include eight normal completions,
keyboard Escape, and external abort. A scheduled 120-frame fixation still
polled 120 times and built the Escape list once. All 77 runtime-task tests and
651 engine focused tests passed. These checks used fake clocks, windows,
and keyboards.

Repo precommit passed the Windows and Darwin type checks, repository audits,
and 6,622 unit tests with 41 platform or permission skips. Docs focused
verification passed all 13 checks.
