# Engine Interface

The engine layer is the only place that may talk to presentation backends such
as PsychoPy. Runtime owns flow and calls engines through
`src/fpvs_studio/engines/base.py`.

## Boundary Rules

- Runtime passes compiled `RunSpec` objects and project roots into engines.
- Engines render transition, instruction, break, feedback, completion, and
  condition playback screens.
- Engines render one fixation tutorial practice attempt when runtime asks for it;
  runtime owns the tutorial state machine and metrics.
- Condition-start transition screens are manual participant gates: runtime passes
  `continue_key="space"` and engines render `Press Space to begin.`
- Engines may receive runtime options, but runtime-only options must not be
  persisted into `RunSpec`.
- Engines may report the active session window size so runtime can block launches
  whose configured display resolution does not match the actual fullscreen display.
- Engines expose a neutral refresh-measurement method. PsychoPy implements it with a
  temporary fullscreen probe window; measured values do not leak PsychoPy types across
  the engine boundary. Runtime combines that stability observation with the exact
  Windows rational display mode; engines do not classify `59.94` versus `60`.
- PsychoPy imports must remain lazy and local to engine implementations.
- Engines return core-owned execution summaries; exporters stay outside engine
  code.
- Runtime may pass one `ResolvedTaskStep` at a time to `render_task_step(...)`.
  Engines return `TaskEngineInput`; they do not own module ordering, repeats, retries,
  branching, validation, scoring, abort policy, or response export.
- Engines apply compiled image/word transforms and geometry at presentation time. They
  must not write transformed stimulus assets or infer authoring inheritance.
- A compiled pre-stream fixation phase is rendered after the participant gate and
  before the stream clock starts. Frame-zero stimuli and condition triggers retain
  their existing alignment.

## First Files

- Interface: `src/fpvs_studio/engines/base.py`
- Registry: `src/fpvs_studio/engines/registry.py`
- PsychoPy implementation facade: `src/fpvs_studio/engines/psychopy_engine.py`
- PsychoPy helpers:
  - `src/fpvs_studio/engines/psychopy_loader.py`
  - `src/fpvs_studio/engines/psychopy_tasks.py`
  - `src/fpvs_studio/engines/psychopy_text_screens.py`
  - `src/fpvs_studio/engines/psychopy_stimuli.py`
  - `src/fpvs_studio/engines/psychopy_timing.py`
  - `src/fpvs_studio/engines/psychopy_metadata.py`
  - `src/fpvs_studio/engines/psychopy_window.py`
  - `src/fpvs_studio/engines/psychopy_triggers.py`
- Runtime caller: `src/fpvs_studio/runtime/launcher.py`
- Boundary test: `tests/unit/test_import_boundaries.py`

Keep `PsychoPyEngine` as the public implementation surface. Prefer adding or editing
focused helper modules for lazy loading, text screens, stimuli, timing, metadata, window
construction, or trigger behavior before expanding the facade. Avoid splitting the frame
loop unless the new seam has focused tests and preserves frame-accurate behavior.

PsychoPy stimulus preparation occurs before timed playback. Image and text objects are
keyed by their complete resolved render identity, including role transform and resolved
word height, so the frame loop only selects and draws prepared objects. Horizontal and
vertical mirrors use PsychoPy's native flip properties; 180-degree rotation uses native
orientation. Cover geometry is cropped centrally in memory during preparation and never
writes a project file.

## Modular task rendering

Runtime converts authored degrees or window-height fractions into calibrated pixel
positions and sizes before calling the engine. Exact layouts preserve authored
coordinates; responsive layouts arrive as already-positioned grids. The PsychoPy task
renderer supports instructions, study displays, single/multiple image or text choices,
short/long text, numeric input, rating scales, raw keys, and unskippable timed feedback.
It uses Arial consistently, prepares task images through contained project-relative
path resolution, and returns stable selected ids plus raw key/text/numeric and mouse/RT
details. It uses native editable text controls for shifted characters, Unicode, and
multiline long text; long text submits through the visible Submit control. Task clocks
and keyboard clocks reset and carried events clear on the first task flip, without
altering the FPVS run clock, compiled frame sequence, or flip-locked trigger schedule.
