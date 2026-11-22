# Reuse the key filter during timed passive fixation

Status: Planned

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
