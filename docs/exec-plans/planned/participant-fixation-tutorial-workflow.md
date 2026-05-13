# Participant Fixation Tutorial Workflow

Status: Planned

## Summary

Add a required participant tutorial before experiment playback when the fixation
accuracy task is enabled. The tutorial teaches the participant to press Space when the
fixation cross changes from the configured base color to the configured target color
(`blue` to `red` with current defaults). The experiment does not begin until the
participant completes three successful practice detections.

## User Workflow

When the participant launches a session with fixation accuracy enabled, the session
starts with:

```text
Thank you for participating in our experiment today! Your task is to press the space bar
each time you see the cross change colors from blue to red. Ready to try it? Press space
to continue!
```

After the participant presses Space:

1. The engine shows the fixation cross in the base color.
2. After a short delay, the cross changes to the target color.
3. The participant must press Space within one second of the color change.
4. A successful response advances to the next practice prompt.
5. A missed response shows:

```text
Please press the space bar when you see the cross change colors.
```

Then the tutorial waits through a five-second cooldown and restarts from the first
practice attempt.

Successful attempts use these prompts:

```text
Great job! Let's try this again. Press space to continue.
```

```text
Great! Let's practice one more time, then we'll start the experiment.
```

After the third successful attempt, the participant sees their tutorial accuracy and
average reaction time, followed by:

```text
You're now ready to begin the experiment. When you're ready, please press space to
continue.
```

Pressing Space on that final screen starts the normal experiment flow.

## Implementation Boundary

- Run the tutorial once per launched session, before the first condition-start screen.
- Only run the tutorial when `RunSpec.fixation.accuracy_task_enabled` is true for the
  session. If the accuracy task is disabled, preserve the existing launch flow.
- Keep `RunSpec` single-condition and do not add tutorial state to condition schedules.
- Keep FPVS base/oddball image timing unchanged. Tutorial practice frames are outside
  stimulus playback and must not shift compiled condition frame indexes.
- Keep runtime in charge of the tutorial state machine:
  - required successes: `3`
  - response window: one second from target-color onset
  - failure behavior: show correction prompt, wait five seconds, reset success count
    to zero
  - final summary text: accuracy percentage and average hit RT
- Keep PsychoPy drawing and keyboard polling inside the engine boundary. Add a narrow
  engine method for one fixation tutorial attempt instead of moving PsychoPy code into
  runtime.
- Reuse the active session window so the participant does not see a new display open
  between tutorial and experiment.
- Use the project fixation style for cross size, line width, base color, target color,
  and response key. Current defaults already express the requested blue-to-red task.
- Do not add a GUI toggle in the first implementation. The tutorial is part of the
  fixation accuracy task behavior.
- Do not emit condition triggers during tutorial practice. If a future hardware marker
  is needed for tutorial attempts, that should be a separate trigger plan.
- Keep tutorial metrics lightweight. Prefer participant-facing summary only; if audit
  persistence is needed, add session-level tutorial fields rather than per-condition
  artifacts.

## Proposed Code Areas

- `src/fpvs_studio/engines/base.py`
  - Add an engine interface method for a single fixation tutorial attempt.
  - Return a small result object with hit/miss, reaction time, and aborted state.
- `src/fpvs_studio/engines/psychopy_engine.py`
  - Render tutorial instruction/cooldown/final text screens using the existing text
    screen helpers.
  - Render a fixation-only practice attempt using the existing fixation stimulus
    construction and keyboard polling style.
- `src/fpvs_studio/runtime/run_worker.py`
  - Insert tutorial orchestration after `engine.open_session(...)` and display
    resolution verification, before the first condition transition screen.
  - Abort cleanly if Escape is pressed during tutorial screens or attempts.
- `src/fpvs_studio/runtime/fixation.py`
  - Reuse or add small helpers for tutorial accuracy and mean RT formatting if that
    avoids duplicating condition-feedback calculations.
- `tests/unit/runtime_launcher_helpers.py`
  - Extend the stub engine with tutorial attempt capture/results.

## Tests

- Runtime unit test: fixation accuracy enabled runs the tutorial before the first
  condition transition and does not call `run_condition` until three successful
  attempts have completed.
- Runtime unit test: fixation accuracy disabled skips tutorial and preserves current
  launch ordering.
- Runtime unit test: a missed tutorial attempt shows the correction/cooldown path and
  resets the required-success count.
- Runtime unit test: Escape during tutorial aborts the session before condition
  playback and records a clear abort reason.
- Engine fake-PsychoPy test: a response within one second of target onset returns a hit
  and reaction time.
- Engine fake-PsychoPy test: no response inside the one-second window returns a miss.
- GUI or launcher smoke test: launching a ready project with fixation accuracy enabled
  still uses the normal fullscreen session path and does not expose new setup controls.

## Verification

- Run focused runtime tests for the tutorial state machine.
- Run focused PsychoPy-engine fake tests for tutorial drawing and key timing.
- Run existing fixation scoring and runtime launcher tests to confirm condition
  feedback/export behavior is unchanged.
- Run `python -m ruff check src tests` after Python edits.
- Run `python -m pytest -q tests\unit\test_harness_docs.py` if this plan or related
  harness docs are edited during implementation.

## Assumptions

- The tutorial belongs to the fixation accuracy task. Projects with fixation accuracy
  disabled should not force a response tutorial.
- The participant response key is the configured fixation response key, currently
  Space by default.
- Tutorial attempts are practice only; they are not FPVS stimulus events and are not
  part of the EEG trigger schedule.
- The first implementation keeps the tutorial mandatory when accuracy scoring is
  enabled. A future setting can make it optional if lab workflow requires that.
