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
- A timing-valid PsychoPy condition may not begin until its condition-local graphics
  owner reports ready. Readiness means every unique render variant and both immutable
  fixation colors have been created, drawn once to force deferred upload/glyph work,
  the back buffer has been cleared, queued GPU work has completed, and the conservative
  RAM/graphics-budget gate has passed both before and after upload.
- The engine owns exactly one condition cache at a time. It releases textures, masks,
  pixel-buffer objects (PBOs), legacy display lists, retained in-memory crops, prepared
  draw plans, and strong references, then calls `glFinish()` after deletion before
  runtime can advance. Cleanup failure closes the graphics context and surfaces an error;
  it is not treated as a successful release.

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
  - `src/fpvs_studio/engines/graphics_readiness.py`
  - `src/fpvs_studio/engines/windows_graphics_budget.py`
- Runtime caller: `src/fpvs_studio/runtime/launcher.py`
- Boundary test: `tests/unit/test_import_boundaries.py`

Keep `PsychoPyEngine` as the public implementation surface. Prefer adding or editing
focused helper modules for lazy loading, text screens, stimuli, timing, metadata, window
construction, or trigger behavior before expanding the facade. Avoid splitting the frame
loop unless the new seam has focused tests and preserves frame-accurate behavior.

PsychoPy stimulus preparation occurs automatically after the participant's Space gate
and before technical warmup or timed playback. Image and text objects are keyed by their
complete resolved render identity, including role transform and resolved word height,
so the frame loop only invokes preselected bound draw calls. Horizontal and vertical
mirrors use PsychoPy's native flip properties; 180-degree rotation uses native
orientation. Cover geometry is cropped centrally into a retained Pillow RGB/RGBA image
during preparation and never writes a project file.

Production launch settings enable graphics-memory verification. The engine rejects
known software renderers and uses Windows DXGI per-process budgets plus physical-RAM
availability with conservative headroom and estimation factors. When multiple DXGI
entries could represent the active OpenGL renderer, every compatible candidate must
pass; the engine does not guess one. Missing/failed telemetry is `unverified`, not a
pass. Experiment Test Mode can explicitly disable this machine qualification without
claiming timing-valid hardware.

The prepared cache spans both kinds of memory used by real presentation hardware:
decoded/retained process data in ordinary system RAM and uploaded OpenGL textures in a
discrete GPU's VRAM or an integrated GPU's shared system RAM. Cleanup deterministically
releases FPVS Studio's process-owned objects and graphics handles. It does not attempt
to purge Windows' global filesystem page cache, which is outside the process and can be
reclaimed by the operating system.

OpenGL does not provide a cross-driver promise that these uploaded textures stay pinned
in VRAM for the whole condition. The driver still owns residency decisions; the engine's
strong references, pre/post memory checks, priming draws, and synchronization are the
available software controls.

The readiness barrier means image decoding, stimulus construction, initial draw/upload,
and queued GPU work finish before frame zero; the production memory gate must also pass
before and after upload. This removes those known jobs from the timed loop, but it cannot
control later operating-system scheduling, graphics-driver behavior, display scanout, or
physical pixel response.

The timed plan is compiled before frame zero: stimulus/fixation draw selection and
trigger lookup do not traverse validated models per frame. During playback, Python GC
is paused, interval/key/target data is collected as primitive values, and core result
models are constructed after the terminal flip. Default and target fixation crosses are
separate pre-primed stimuli, so changing the secondary attention task does not mutate a
PsychoPy property on every FPVS frame.

Only PsychoPy's PTB and ioHub keyboard backends provide fixation timestamps used for
same-clock RT scoring. The `event` or an unknown backend uses whole-condition frame
fallback. Runtime exports both the detected `keyboard_backend` and the resulting
`fixation_rt_scoring_source`; the engine does not silently treat an `event` timestamp as
hardware timing.

After the last compiled frame, the engine performs one neutral background/default-
fixation flip. This offset boundary is not a `RunSpec` frame and emits no trigger. It
removes the final image in continuous mode, closes the final blank in 50%-blank mode,
captures responses made during the last frame, and supplies the missing duration for
that frame. The final `frame_intervals` list therefore covers every completed compiled
frame.

Without a photodiode, returned flip times and recorded trigger markers are software and
electrical evidence, not proof of photon onset. They cannot measure panel scanout or pixel
response latency, so the engine must not claim physical display-onset accuracy from them.

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
