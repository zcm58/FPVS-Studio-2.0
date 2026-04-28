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
- PsychoPy implementation: `src/fpvs_studio/engines/psychopy_engine.py`
- Runtime caller: `src/fpvs_studio/runtime/launcher.py`
- Boundary test: `tests/unit/test_import_boundaries.py`
