# AGENTS.md

## Project identity

FPVS Studio is an open-source, GPL-3.0-compatible desktop application for
building and running fast periodic visual stimulation (FPVS) experiments
without requiring users to write code. Version 1 is intentionally narrow and
mirrors the current lab workflow:

- fixed base rate: **6.0 Hz**
- oddball every **5th** image
- oddball frequency: **1.2 Hz**
- duty-cycle choices: **continuous** or **50% blank**
- project-based GUI workflow
- PySide6 GUI shell
- PsychoPy hidden behind a presentation-engine adapter
- rich session export
- all derived stimuli materialized into the project folder before any run

## Current phase

The current implementation phase is **runtime execution vertical slice**.

This pass should keep the compile layers stable while making execution real:

- `project.json` -> core project models
- core compiler -> single-condition `RunSpec`
- core compiler -> multi-condition `SessionPlan`
- preprocessing -> manifest-backed original/derived assets
- runtime -> session preflight -> session flow -> export writers
- engine -> transition screens + frame-accurate `RunSpec` playback
- core execution results -> neutral run/session artifacts

Do not collapse the planning layers into runtime or move PsychoPy into core or
preprocessing.

## Non-negotiable product decisions for v1

1. The only built-in protocol template is `fpvs_6hz_every5_v1`.
2. The user does not edit base/oddball frequency in v1.
3. Users choose between:
   - `continuous` = image visible for the full 6 Hz cycle
   - `blank_50` = image visible for half the cycle, blank for the other half
4. The default sequence repeats **146 oddball cycles per sequence**.
   - Because oddball occurs every 5 base cycles, this means:
     - `base_cycles_per_sequence = 146 * 5 = 730`
     - `oddball_presentations_per_sequence = 146`
   - Duration is derived from cycle count and refresh-compatible frame timing.
5. Supported source image formats are only:
   - `.jpg`
   - `.jpeg`
   - `.png`
6. All images inside a stimulus set must have the same resolution.
7. A condition's base and oddball stimulus sets must also match in resolution.
8. Control conditions in v1 are:
   - `rot180` = 180-degree orientation inversion
   - `phase_scrambled` = deterministic Fourier phase scrambling
9. The fixation task is the only behavioral task in v1.
10. Trigger settings must include a user-configurable serial port field in
    project settings, but the actual lab-specific serial trigger implementation
    can remain a scaffold/stub in this pass.

## Architecture guardrails

- Use a **src layout**.
- Keep all persistent schemas **engine-neutral**.
- Keep project models, `RunSpec`, `SessionPlan`, and execution-result contracts
  as separate layers.
- Keep all GUI code **separate** from core models and validation.
- Only code under `src/fpvs_studio/engines/` may import PsychoPy.
- Keep PsychoPy imports lazy inside the PsychoPy engine implementation.
- Do not use Qt repaint/update loops as a substitute for the presentation
  engine timing loop.
- Do not perform grayscale conversion, inversion, or scrambling during runtime
  presentation.
- Derived assets belong in the project folder under `stimuli/derived/...`.
- Persist project-facing file paths as project-relative POSIX-style strings in
  JSON. Convert to `pathlib.Path` at the edges.
- Prefer deterministic behavior with explicit seeds.
- Prefer friendly validation errors over silent coercion.
- Never resize images automatically to make a project pass validation.

## Technical preferences

- Prefer **Pydantic v2** for persistent schemas and validation.
- Use `pathlib`, `enum`, and strong typing throughout.
- Use `pytest` for tests.
- Configure `ruff` and `mypy`.
- Add docstrings to public models/functions.
- Include small, representative test fixtures.
- Keep the runtime and GUI shallow where possible, but keep the contracts solid.

## What this phase should deliver

1. A clean repository scaffold.
2. `pyproject.toml` with runtime and dev dependencies.
3. Engine-neutral core models for:
   - project file
   - project settings
   - stimulus set and manifest metadata
   - condition definitions
   - template metadata
   - a dedicated `RunSpec`
   - a dedicated `SessionPlan`
   - execution-result/export contracts
   - display validation reports
4. JSON serialization and round-trip tests.
5. Validation rules for:
   - supported file extensions
   - equal-resolution image sets
   - matching base/oddball set resolutions
   - duty-cycle/frame-compatibility checks
   - fixation settings consistency
6. A template library exposing the one v1 template.
7. A project-creation service that initializes the project folder structure and
   starter `project.json`.
8. A preprocessing-manifest model and basic image inspection utilities.
9. Engine/runtime/trigger interfaces that consume `RunSpec`, with a real but
   still narrow PsychoPy execution path.
10. A `SessionPlan` contract plus runtime session flow that iterates ordered
    `RunSpec` entries above the engine layer.
11. Core-owned execution-result/export contracts and unit tests that keep the
    runtime path trustworthy without requiring PsychoPy in the default suite.

## What this phase should not overbuild

- No GUI editor completion yet.
- No complete GUI yet.
- No real lab-specific serial-port trigger code yet.
- No advanced image normalization beyond the data contracts needed to support
  it later.
- No attempt to make unsupported monitor refresh rates work anyway.

## Change discipline

If something is ambiguous, preserve the architecture's intent, add a short
TODO, and avoid inventing user-facing behavior that has not been discussed.
Latest explicit user decisions override earlier defaults.
