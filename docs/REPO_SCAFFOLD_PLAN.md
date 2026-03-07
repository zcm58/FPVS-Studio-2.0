# FPVS Studio Repository Scaffold Plan

## Goal of this pass

Create the initial repository structure and the engine-neutral project/data model layer for FPVS Studio.

The implementation should be conservative and futureproof. It should make later GUI work, PsychoPy runtime work, and possible future engine replacement significantly easier.

## Recommended repository layout

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
        AGENTS.md
        __init__.py
      core/
        AGENTS.md
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
        AGENTS.md
        __init__.py
        models.py
        inspection.py
        manifest.py
        importer.py
        grayscale.py
        controls.py
      engines/
        AGENTS.md
        __init__.py
        base.py
        registry.py
        psychopy_engine.py
      runtime/
        AGENTS.md
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
      test_models.py
      test_validation.py
      test_template_library.py
      test_project_service.py
      test_compiler.py
      test_preprocessing_inspection.py
    fixtures/
      sample_project/
      sample_images/
```

## Strong recommendations

- Use `pydantic v2` for persisted models.
- Use `pathlib.Path` for filesystem operations.
- Use `pytest`, `ruff`, and `mypy`.
- Keep GUI placeholders minimal in this pass.
- Keep PsychoPy imports isolated.

## Data-model expectations

### Project file

The canonical editable project file should include:

- schema version
- project metadata
- project settings
- stimulus sets
- conditions

### Project settings

Should cover:

- display preferences
- fixation task settings
- trigger settings

### Stimulus-set model

Should include enough metadata to know:

- set id and user-facing name
- source directory relative path
- resolution
- image count
- supported/available variants
- manifest links as needed

### Condition model

Should include at least:

- id
- name
- instructions text
- base set id
- oddball set id
- selected variant
- sequence count
- oddball cycle repeats per sequence (default 146)
- trigger code
- duty-cycle mode
- order index

Note: in v1 the protocol constants are fixed by template, but conditions still need the per-sequence repeat count and sequence-count fields.

### RunSpec

Should include:

- run mode
- engine name
- project id
- session id
- participant/session metadata
- compiled display spec
- compiled protocol spec
- compiled fixation settings
- compiled trigger settings
- compiled condition specs

## Validation rules that should exist in this pass

- supported image extensions only
- no empty stimulus sets
- equal image resolution within set
- equal resolution across base/oddball sets in a condition
- non-empty condition names
- valid trigger code types/ranges
- display compatibility with 6 Hz
- even frame count for `blank_50`
- fixation target timing consistency

## Behavior of unsupported or unimplemented areas

Use explicit placeholders and `NotImplementedError` where appropriate. Prefer clear seams over fake implementations.

## Acceptance criteria for this pass

1. The package installs locally.
2. The models round-trip to/from JSON cleanly.
3. Project scaffolding can create a valid starter project on disk.
4. Image inspection can detect unsupported extensions and mixed resolutions.
5. Display/timing validation can distinguish supported vs unsupported refresh-rate cases.
6. The engine/runtime interfaces exist and are importable without dragging PsychoPy into unrelated modules.
7. Tests cover the above.

