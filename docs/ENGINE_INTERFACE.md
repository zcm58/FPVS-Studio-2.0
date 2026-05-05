# Engine Interface

The engine layer is the only place that may talk to presentation backends such
as PsychoPy. Runtime owns flow and calls engines through
`src/fpvs_studio/engines/base.py`.

## Boundary Rules

- Runtime passes compiled `RunSpec` objects and project roots into engines.
- Engines render transition, instruction, break, feedback, completion, and
  condition playback screens.
- Engines may receive runtime options, but runtime-only options must not be
  persisted into `RunSpec`.
- PsychoPy imports must remain lazy and local to engine implementations.
- Engines return core-owned execution summaries; exporters stay outside engine
  code.

## First Files

- Interface: `src/fpvs_studio/engines/base.py`
- Registry: `src/fpvs_studio/engines/registry.py`
- PsychoPy implementation facade: `src/fpvs_studio/engines/psychopy_engine.py`
- PsychoPy helpers:
  - `src/fpvs_studio/engines/psychopy_loader.py`
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
