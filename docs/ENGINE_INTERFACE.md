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
  PsychoPy's NumPy dimensions are accepted on all platforms; Mac reports realized
  backing pixels. The explicit use-current-resolution policy remains unchanged.
- Engines expose a neutral refresh-measurement method. PsychoPy implements it with a
  temporary fullscreen probe window; measured values do not leak PsychoPy types across
  the engine boundary. Runtime combines that stability observation with the exact
  Windows rational display mode; engines do not classify `59.94` versus `60`.
  On Mac, runtime owns the bounded refresh subprocess. Mac window constructors set
  `checkTiming=False` to avoid a second unbounded implicit measurement after required
  preflight; Studio's frame-based QC remains independent of that constructor check.
  `psychopy_macos_display` bounds the backend's DisplayLink polling without disabling
  synchronization and selects foreground `event` keyboard input for Mac Test/Pilot.
  Missing callbacks fail explicitly; Windows retains its original backend/input path.
  The Mac keyboard adapter replaces only the returned device's event dispatcher:
  it delivers every queued string key name to PsychoPy's existing parser and receiver.
  This avoids the legacy dispatcher's timestamp-pair name mismatch and dropped batch
  entries. Foreground muting, response filters, clearing and clocks remain intact;
  no keyboard class or Windows dispatcher is patched.
- PsychoPy imports must remain lazy and local to engine implementations.
- Windows/Mac window creation resolves the runtime device identity against Pyglet's current
  screens for both refresh probing and session playback, explicitly using the Pyglet
  backend. With no explicit selection,
  it resolves the native primary monitor. Missing or ambiguous selections fail before
  PsychoPy can silently substitute screen zero. Selection remains a launch option,
  outside compiled schedules. See [runtime display policy](RUNTIME_EXECUTION.md#session-flow).
  Mac additionally confirms actual NSWindow placement and realized backing dimensions
  before the first flip; mixed-DPI cached metadata is refreshed through the existing
  nonexclusive backend resize path and revalidated.
- Engines return core-owned execution summaries; exporters stay outside engine
  code.
- Production playback requires a backend declaring `emits_external_markers`; the legacy
  `emits_hardware_triggers` property remains compatible for existing serial adapters.
  Unicorn UDP declares external output without claiming a direct hardware connection.
  The unchanged flip callback submits one prepared marker at each compiled event;
  payload preparation, receiver qualification and acquisition exports stay outside it.
  Test/Pilot uses null output. Neither capability nor a successful send establishes
  receiver delivery or EEG sample timing. See [Runtime execution](RUNTIME_EXECUTION.md#trigger-behavior).
- Runtime may pass one `ResolvedTaskStep` at a time to `render_task_step(...)`.
  Engines return `TaskEngineInput`; they do not own module ordering, repeats, retries,
  branching, validation, scoring, abort policy, or response export.
- Native scene runs use `prepare_condition(...)` before their timed pre-task screens.
  The engine retains one prepared condition until `run_condition(...)` consumes it,
  then releases it normally; abort/session close also releases unconsumed resources.
  Scene playback adds no ordinary blank warmup. Timed scene task screens receive
  resolved frame counts; terminal screens clear at their duration boundary. See
  [Masking](MASKING.md) for the authored flow and checkpoint timing.
- `ResolvedTaskStep.font_family` is the engine-neutral Arial/Open Sans choice compiled
  from the authored step. An engine must use it consistently for every text surface in
  that step; it must not substitute a machine-dependent font path into the contract.
- Engines apply compiled image/word transforms and geometry at presentation time. They
  must not write transformed stimulus assets or infer authoring inheritance.
- Experimental attentional-blink playback expands a target-pair slot into contiguous
  T1, Base-image separator, and T2 events. Engines follow each event's compiled onset
  and duration; they do not divide the slot again. Resolve image geometry through
  `core.run_spec.event_presentation`, including the separate T2 source resolution in
  resource preparation and graphics-budget estimation. The full contract lives in
  [RunSpec](RUNSPEC.md#experimental-attentional-blink-slots).
- Engines apply sinusoidal contrast only when the explicit compiled image presentation
  mode requests it. The envelope is core-owned and frame-count-derived; engines must not
  infer it from the full-cycle on/off split or recompute it from a nominal frequency.
- A compiled pre-stream fixation phase is rendered after the participant gate and
  before the stream clock starts. Frame-zero stimuli and condition triggers retain
  their existing alignment by default. Opted-in AB distractor marking uses one
  neutral condition-marker flip at compiled frame `-1`, followed immediately by
  stream frame zero and its distractor marker. See [RunSpec](RUNSPEC.md#triggerevent).
- A PsychoPy condition may not begin until every unique render variant and both
  immutable fixation colors have been created, drawn once to force deferred upload or
  glyph work, the back buffer has been cleared, and queued GPU work has completed.
  Conservative RAM/graphics-budget checks run before and after upload. A measured
  rejection blocks frame zero; unavailable or ambiguous telemetry proceeds as an
  explicit `unverified` warning and does not claim hardware qualification.
- The engine owns exactly one condition cache at a time. It releases textures, masks,
  pixel-buffer objects (PBOs), legacy display lists, retained in-memory crops, prepared
  draw plans, and strong references, then calls `glFinish()` after deletion before
  runtime can advance. Cleanup failure closes the graphics context and surfaces an error;
  it is not treated as a successful release.
- Each PsychoPy window belongs to its presentation thread. The Pyglet adapter in
  `psychopy_graphics_lifetime.py` guards texture and buffer finalizers: collection on
  another thread, or after the originating window closes, queues deletion in the
  shared object space instead of issuing native GL calls. Context activation drains
  those queues before resource preparation, after untimed screens and before close;
  no new collection or deletion barrier runs inside condition playback or between
  an authored timed scene fixation and its prepared stream. Late references retained
  by exception tracebacks remain guarded after close. Python's process-wide garbage
  collection policy is otherwise unchanged.
- Engine exception boundaries release completed traceback-frame locals on the
  presentation thread before closing the context or delivering errors to the GUI.
  This also releases partial PsychoPy constructors whose direct display-list
  finalizers are not managed by Pyglet. Exception messages and stack locations remain
  available; native objects are not retained just to preserve traceback locals.
- Transition, feedback, break and completion screens create their heading, body and
  footer stimuli once per screen, update the countdown only when its displayed text
  changes, and release them on continue, cancellation and exceptions. They never
  allocate a replacement set of text stimuli on every display refresh.
  Their heading, body and footer flow as separate measured blocks using pixel
  units and top anchors. Wrapping follows the actual viewport with screen margins;
  rendered bounds determine spacing instead of fixed vertical offsets. Layout
  recomputes when the viewport or countdown text changes. Font fitting stops at a
  readable minimum (16 px footer, proportionally larger heading/body); content
  that still cannot fit raises an actionable error rather than clipping or adding
  pages. Authored text, continuation keys and countdown behavior remain unchanged.

## First Files

- Interface: `src/fpvs_studio/engines/base.py`
- Registry: `src/fpvs_studio/engines/registry.py`
- PsychoPy implementation facade: `src/fpvs_studio/engines/psychopy_engine.py`
- PsychoPy helpers:
  - `src/fpvs_studio/engines/psychopy_loader.py`
  - `src/fpvs_studio/engines/psychopy_graphics_lifetime.py`
  - `src/fpvs_studio/engines/psychopy_tasks.py`
  - `src/fpvs_studio/engines/psychopy_task_cursor.py`
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

Before creating either the temporary refresh probe or the session window, the PsychoPy
helper queries the selected Pyglet screen and passes its native pixel dimensions as the
fullscreen `size`. This avoids PsychoPy interpreting its own `800x600` constructor
default as the requested fullscreen size. Windows/Linux retain warning-only sizing
delegation if enumeration fails. Mac requires known logical screen dimensions and
uses a borderless desktop-sized window at `(0, 0)` with Retina backing pixels, rather
than Pyglet's exclusive capture/shielding path. Actual backing pixels must still match
the local calibration. No system display mode is changed.
The Mac adapter changes PsychoPy's coordinate-only `useRetina` flag after the native
surface is realized, before creating stimuli. This removes the dependency's second
factor-of-two transform; pixel, normalized, height and mouse conversions share the
same backing-pixel convention. The constructor still requests Retina backing storage,
and framebuffer size/content scale are unchanged. App-scoped HideDock/HideMenuBar
options provide fullscreen presentation and restore on every exit without capture
or disabled recovery shortcuts.

Production launch settings enable graphics-memory verification. The engine rejects
known software renderers and uses Windows DXGI per-process budgets plus physical-RAM
availability with conservative headroom and estimation factors. When multiple DXGI
entries could represent the active OpenGL renderer, every compatible candidate must
pass; the engine does not guess one. Missing/failed telemetry is `unverified`, not a
pass: playback continues after the resource-preparation barrier, while the uncertainty
is written to run/session warnings and readiness metadata. Known software rendering or
measured insufficient graphics/system-memory headroom remains a pre-onset rejection.
Experiment Test Mode can explicitly disable this machine qualification without claiming
timing-valid hardware.

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
and queued GPU work finish before frame zero. The production memory gate runs before and
after upload; measured insufficiency rejects launch, while diagnostic uncertainty is
preserved as `unverified`. This removes those known jobs from the timed loop, but it
cannot control later operating-system scheduling, graphics-driver behavior, display
scanout, or physical pixel response.

The timed plan is compiled before frame zero: stimulus/fixation draw selection,
sinusoidal image contrast operations, and trigger lookup do not traverse validated
models per frame. During playback, Python GC is paused, interval/key/target data is
collected as primitive values, and core result models are constructed after the
terminal flip. Default and target fixation crosses are separate pre-primed stimuli, so
changing the secondary attention task does not mutate a PsychoPy property on every FPVS
frame.

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

During playback, Studio captures intervals from PsychoPy's returned flip timestamps
with PsychoPy's optional interval recorder disabled. The separate refresh probe uses
PsychoPy's own recorder. Studio evaluates and reports playback timing after the run.

After playback, the engine derives the optional `RunExecutionSummary.playback_cadence`
from the measured stream flips, beginning at frame zero and ending at the neutral
terminal flip. Warmup and any pre-stream marker flip are outside this span. A
missing measured boundary leaves the cadence unavailable even if another timing
consumer can use a fallback timestamp. See [playback cadence reporting](RUNTIME_EXECUTION.md#playback-cadence-reporting).

Without a photodiode, returned flip times and recorded trigger markers are software and
electrical evidence, not proof of photon onset. They cannot measure panel scanout or pixel
response latency, so the engine must not claim physical display-onset accuracy from them.

## Modular task rendering

Runtime converts authored degrees into nominal task pixels. Window-height fractions
and responsive grids use the realized presentation viewport when available.
Responsive grids bound image and shape sizes and text wrapping to their cells.
Before the first flip, the PsychoPy task renderer uniformly reduces positioned
content that exceeds the viewport's usable area, including choice hitboxes and
positioned prompts. The same fit applies in Test/Pilot and recording. Timed FPVS
stimulus geometry uses its own calibrated rendering path.
The task renderer supports instructions, study displays, single/multiple image or text choices,
short/long text, numeric input, rating scales, raw keys, and unskippable timed feedback.
It applies the resolved Arial or Open Sans family to headings, prompts, item and option
labels, editable response text, validation messages, submit controls, and footers. Arial
is the compatibility default. Open Sans is loaded from FPVS Studio's bundled regular
font and registered with both the Pyglet `TextStim` path and PsychoPy `TextBox2`; the
renderer does not rely on a host installation. It prepares task images through
contained project-relative path resolution and returns stable selected ids plus raw
key/text/numeric and mouse/RT details. It uses native editable text controls for shifted
characters, Unicode, and multiline long text; long text submits through the visible
Submit control. Task clocks and keyboard clocks reset and carried events clear on the
first task flip, without altering the FPVS run clock, compiled frame sequence, or
flip-locked trigger schedule.

Pyglet task screens retain native mouse presses and their pixel positions until the
renderer consumes them, including a press and release delivered between polls. Capture
is armed as the first visible-flip callback, before keyboard clearing can dispatch
more native events. Pre-swap clicks remain ignored. Capture passes events through to
PsychoPy controls and is removed on every exit. Recognition selectability and
submission rules stay authored.
Capture uses the presentation window's native event pump without reading PsychoPy's
separate legacy mouse state. Each press uses current window dimensions and content
scaling so its hit-test coordinates match the visible choice after a resize or DPI change.
This path is shared by image/text single choice, multiple choice and rating screens
from any condition modifier, plus editable-text submit controls.

Text-choice hit testing accounts for left/right alignment inside Pyglet's wrapping
frame and for overflowing lines, using the actual rendered content width. The native
containment check retains ownership of vertical bounds; image/shape and ordinary
centered text tests are unchanged. Missing aligned-text metrics fail explicitly.

Cursor presentation is engine-owned. Windows/Pyglet mouse-response screens use a
high-contrast `ImageMouseCursor` drawn into the presented frame, covering both local
and remote viewers without depending on a hardware cursor overlay. Pyglet retains
ownership of pointer coordinates, motion, scaling, focus/leave handling and native
cursor bookkeeping; click capture and hit testing are unchanged. Other platform and
backend paths retain their native pointer behavior. Projects store no cursor setting.

Each response screen restores its previous cursor and visibility on completion,
Escape, rendering errors and input-setup failures. The pointer's owned texture is
created and released on the presentation thread, with cursor restoration and texture
cleanup attempted independently. Unsupported software-cursor setup fails explicitly.
Timed feedback and FPVS playback do not install a software response cursor.
Regression checks cover repeated recognition/feedback transitions and queued clicks.
Visible acceptance requires an actual moving pointer and aligned clicks; neither
`mouseVisible=True` nor Windows `CURSOR_SHOWING` proves that the participant sees it.
Session and refresh-probe teardown explicitly restores visibility before closing the
native window, including after setup, measurement or graphics-cleanup errors. This
avoids relying on PsychoPy's restoration after backend teardown, which can fail first.
Window close is still attempted if pointer restoration fails; that failure is logged
and propagated when close succeeds.
The native capture repair first shipped in Studio 2.5.0; Library compatibility guards
are documented in [Experiment Library](EXPERIMENT_LIBRARY.md).

Each task screen reuses its text and controls across frames, updating them when the
response, selection or validation state changes. Task graphics use the same
deterministic texture, pixel-buffer and display-list cleanup as condition stimuli.
Cleanup runs after completion, cancellation and rendering errors, rolls back partially
prepared item sets, and attempts every item without replacing an existing presentation
error. Input-state restoration covers setup failures too and attempts every restoration
even when another cleanup step fails. Numeric input rejects NaN, infinity and overflow before
step validation or result construction, allowing the participant to correct the entry.
