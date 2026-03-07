# Initial Codex Prompt for FPVS Studio

You are working inside the **FPVS Studio** repository. Before editing anything, read the following files if they exist:

1. `AGENTS.md` at the repo root
2. all nested `AGENTS.md` files in subdirectories you touch
3. `docs/FPVS_Studio_v1_Architecture_Spec.md`
4. `docs/REPO_SCAFFOLD_PLAN.md`

Your job in this first implementation pass is to create the **repository scaffold and the engine-neutral project/data model layer** for FPVS Studio. Do not try to finish the whole application in one step. Build a strong, clean foundation that future GUI and runtime work can safely depend on.

## Product context

FPVS Studio is an open-source desktop application for configuring and running **fast periodic visual stimulation (FPVS)** experiments. It is meant to be user friendly for non-programmers. The user should work entirely through a GUI and should never have to interact with PsychoPy directly.

The high-level architecture for v1 is:

- **PySide6** for the desktop app shell and future GUI
- **PsychoPy** as the hidden presentation engine for timing-critical stimulus delivery
- a **presentation-engine adapter** so the runtime can later be swapped to `pyglet` or `GLFW` without rewriting the project model, GUI, or session export

## Locked v1 decisions

These are not open for reinterpretation in this pass:

### Protocol template
There is exactly one built-in v1 protocol template:

- `template_id = "fpvs_6hz_every5_v1"`
- base rate = `6.0 Hz`
- oddball every `5th` image
- oddball rate = `1.2 Hz`

The user does **not** edit base or oddball frequency in v1.

### Duty-cycle modes
Each condition can choose one of two presentation styles:

- `continuous`: image remains on screen for the full 6 Hz cycle
- `blank_50`: image remains on screen for half of the cycle, followed by an equal blank interval

### Sequence repeat default
The default sequence repeats **146 oddball cycles per sequence**.

Because oddballs occur every 5th image:
- `oddball_cycle_repeats_per_sequence = 146`
- `base_cycles_per_sequence = 146 * 5 = 730`
- `oddball_presentations_per_sequence = 146`

The actual duration is derived from frame-locked timing, not stored as a magical free-floating constant.

### Fixation task
The only behavioral task in v1 is a fixation-cross color-change task with project-level settings such as:
- enabled
- changes per sequence
- base color
- target color
- target duration
- min/max spacing
- response keys
- cross size / line width

### Preprocessing
v1 preprocessing includes:
- importing/copying source images into the project
- grayscale conversion
- control generators:
  - `rot180` = 180-degree orientation inversion
  - `phase_scrambled` = deterministic Fourier phase scrambling

### Supported source image formats
Only these source formats are allowed:
- `.jpg`
- `.jpeg`
- `.png`

Matching should be case-insensitive.

### Resolution rules
- all images inside a stimulus set must have the same resolution
- base and oddball stimulus sets used together in one condition must also match in resolution
- do **not** auto-resize images to make a project pass

### Trigger settings
Expose trigger settings in project settings, including:
- backend
- enabled
- serial port string
- baudrate and pulse/reset settings if helpful

The actual lab-specific serial trigger implementation may remain a placeholder/stub in this pass. Create the interface and data model boundary now.

## Goal of this Codex pass

Create the initial repository structure and the model/validation layer that will support future implementation.

The end result of this pass should include:

1. a sensible repo scaffold
2. packaging/config files
3. engine-neutral persisted schemas
4. JSON serialization/round-trip support
5. validation rules
6. project-folder scaffolding helpers
7. a template library
8. a minimal compile path from editable project state to a neutral `RunSpec`
9. preprocessing manifest and image inspection utilities
10. engine/runtime/trigger interfaces and stubs
11. tests

## Strong implementation preferences

Use these unless there is a compelling reason not to:

- **src layout**
- **Pydantic v2** for persisted schemas and validation
- `pathlib.Path` for filesystem operations
- `pytest`
- `ruff`
- `mypy`
- public APIs typed and documented
- engine-neutral JSON models with `schema_version`
- persisted paths stored as **project-relative POSIX strings**

## Recommended repository layout

Use this layout unless you have a strong reason to adjust it:

```text
<repo>/
  AGENTS.md
  README.md
  LICENSE
  pyproject.toml
  .gitignore
  docs/
    FPVS_Studio_v1_Architecture_Spec.md
    REPO_SCAFFOLD_PLAN.md
    CODEX_INITIAL_PROMPT.md
  src/
    fpvs_studio/
      __init__.py
      app/
        __init__.py
        main.py
      gui/
        __init__.py
      core/
        __init__.py
        enums.py
        models.py
        template_library.py
        validation.py
        serialization.py
        project_service.py
        compiler.py
        migrations.py
        paths.py
      preprocessing/
        __init__.py
        models.py
        inspection.py
        manifest.py
        importer.py
        grayscale.py
        controls.py
      engines/
        __init__.py
        base.py
        registry.py
        psychopy_engine.py
      runtime/
        __init__.py
        launcher.py
        worker.py
        session_export.py
      triggers/
        __init__.py
        base.py
        null_backend.py
        serial_backend.py
  tests/
    unit/
    fixtures/
```

## What to implement now

### 1. Packaging and repo basics
Create:
- `pyproject.toml`
- package metadata
- dependency groups
- dev-tool configuration
- `README.md`
- `.gitignore`
- a basic `LICENSE` file or placeholder aligned with GPL-3.0

If you need to choose a Python version for the scaffold, use a conservative version compatible with PySide6 and PsychoPy for current desktop development. If uncertain, prefer a narrow, editable constraint rather than a very broad one.

### 2. Core enums and models
Implement engine-neutral Pydantic models for at least:

- `SchemaVersion`
- `DutyCycleMode`
- `StimulusVariant`
- `TriggerBackendKind`
- `RunMode`
- `EngineName`

And persisted/domain models for at least:

- `ProjectMeta`
- `DisplaySettings`
- `FixationTaskSettings`
- `TriggerSettings`
- `ProjectSettings`
- `StimulusSet`
- `Condition`
- `ProjectFile`
- `TemplateSpec`
- `RunParticipant`
- `CompiledDisplaySpec`
- `CompiledProtocolSpec`
- `CompiledFixationSpec`
- `CompiledTriggerSpec`
- `CompiledConditionSpec`
- `RunSpec`
- `SessionSummary`
- `DisplayValidationReport`
- preprocessing-manifest models

Use `extra="forbid"` on persisted schemas unless there is a strong reason not to.

### 3. Template library
Create a template library module that exposes the one built-in template:
- `fpvs_6hz_every5_v1`

That template should make the fixed protocol constants explicit:
- `base_hz = 6.0`
- `oddball_every_n = 5`
- `oddball_hz = 1.2`

### 4. Project service and folder scaffolding
Create a small project service that can:
- create a new project directory tree
- initialize `project.json`
- initialize `stimuli/`, `runs/`, `cache/`, and `logs/`
- embed the template id into the starter project
- generate a slug/id
- set reasonable starter defaults

Defaults should include:
- `oddball_cycle_repeats_per_sequence = 146`
- supported variants prepared for future use
- a blank or minimal initial condition model if appropriate

Do not make up unnecessary defaults beyond what is already decided. Keep `sequence_count` explicit and conservative.

### 5. Validation
Implement validation rules for at least:

#### Protocol/display
- `refresh_hz / 6.0` must resolve to an integer frame count within tolerance
- `blank_50` also requires an even `frames_per_cycle`

#### Conditions
- non-empty name
- valid stimulus-set references
- valid duty-cycle enum
- integer trigger code
- positive or non-negative count fields as appropriate

#### Fixation task
- valid color strings or structured color type
- target duration > 0 when enabled
- `min_gap_ms <= max_gap_ms`
- `changes_per_sequence >= 0`

#### Images
- only `.jpg`, `.jpeg`, `.png`
- no empty image sets
- all images in a set same resolution
- base/oddball sets must match in resolution for a condition

Give validation results user-friendly messages. Avoid silent coercion or mysterious errors.

### 6. Preprocessing-manifest and image inspection layer
Implement a preprocessing/data layer that can:

- inspect a directory of source images
- filter supported files
- read image dimensions
- detect mixed resolutions
- compute hashes for manifest purposes
- produce a stimulus-set summary
- define manifest records for source and derivative variants

You do **not** need to finish all derivative-generation algorithms in this pass, but the data model should support:
- `original`
- `grayscale`
- `rot180`
- `phase_scrambled`

If you implement placeholders for preprocessing functions, keep the interfaces realistic and deterministic.

Important:
- `rot180` means orientation inversion, not pixel/color inversion
- `phase_scrambled` should be modeled as deterministic and seed-driven

### 7. Minimal compiler to RunSpec
Implement a minimal, pure-Python compiler that takes validated project state plus a selected display refresh rate and produces a neutral `RunSpec`.

At minimum the compiler should derive:
- frames per cycle
- image-on frames
- blank frames
- base cycles per sequence
- oddball presentations per sequence
- approximate per-sequence duration in seconds
- fixation timing converted from ms to frames
- compiled trigger settings

If detailed image-order schedule generation feels premature, leave a clean seam for it. Do not invent a brittle or overcomplicated scheduler just to fill space.

### 8. Engine/runtime/trigger stubs
Create:

- a base presentation-engine protocol or ABC
- an engine registry
- a stub `PsychoPyEngine`
- runtime launcher/worker placeholders
- trigger backend interface plus `NullBackend` and `SerialBackend` scaffolds

Key rule:
- only `src/fpvs_studio/engines/` may import PsychoPy

It is acceptable for the engine implementation in this pass to be skeletal or to raise `NotImplementedError` for intentionally deferred runtime behavior.

### 9. Tests
Add tests that cover at least:

- project model round-trip
- default template retrieval
- project scaffolding creates expected directories/files
- refresh/duty-cycle validation
- image inspection rejects unsupported extensions
- image inspection rejects mixed-resolution sets
- compiler derives correct frame counts for a supported refresh rate
- compiler rejects unsupported refresh rates
- import graph does not require PsychoPy for core-model tests

Use small fixture data. Do not overcomplicate the test suite.

## Important architecture constraints

These must hold after your changes:

- Core models remain importable without PsychoPy or PySide6.
- GUI does not directly depend on PsychoPy.
- Engine/runtime boundaries are explicit.
- The project JSON schema remains engine-neutral.
- The data layer is designed so a future switch from PsychoPy to `pyglet` or `GLFW` is realistic.
- No runtime image preprocessing is implied.
- Derived stimuli are intended to be materialized into the project folder and reused from disk.

## What to defer

Do not spend this pass on:
- full PySide6 windows/widgets
- the full PsychoPy fullscreen presentation loop
- serial trigger hardware specifics
- photodiode support
- advanced balancing/randomization rules
- advanced preprocessing beyond the manifest/inspection/data contracts
- packaging polish beyond a reasonable initial scaffold

## Working style

1. Make a short implementation plan first.
2. Then create the scaffold and models.
3. Keep changes coherent and well-typed.
4. Prefer a smaller, solid first pass to a large unstable one.
5. Leave clear TODOs only where genuinely appropriate.

## Acceptance bar

The first pass is successful if:
- the repository structure is clean
- the project/data models are strong and versioned
- validation is concrete and tested
- the compiler produces a useful neutral `RunSpec`
- engine/runtime/trigger boundaries are in place
- the codebase clearly supports future GUI/runtime development without schema churn

