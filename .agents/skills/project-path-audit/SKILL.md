---
name: project-path-audit
description: Use when reviewing or changing file I/O, project manifests, import/export paths, Windows path handling, QFileDialog behavior, generated files, project-root-relative joins, or hard-coded path cleanup.
---

# Project Path Audit

## Workflow

1. Read `AGENTS.md`, `ARCHITECTURE.md`, and the path-related parts of
   `docs/FPVS_Studio_v1_Architecture_Spec.md`.
2. Locate the active project-root source of truth for the workflow.
3. Search changed code for hard-coded absolute paths, home-directory assumptions, and
   joins that can escape the project root.
4. Keep persisted paths and output formats compatible with existing project data.
5. Ensure file dialogs handle Cancel without side effects.
6. Handle missing, invalid, permission-denied, and repeated-operation cases explicitly
   where those cases are reachable.
7. Use `pathlib.Path` or existing path helpers instead of ad hoc string path assembly.
8. Add or update tests with `tmp_path` for path behavior; avoid real user directories.

## Audit Targets

- `QFileDialog` open/save flows.
- Project creation, open, save, import, export, and manifest paths.
- Generated assets under project `stimuli/`, `runs/`, `cache/`, and `logs/`.
- Windows path separators, drive roots, and relative-path serialization.

## Output Checklist

- List path entry points reviewed.
- State the active project-root invariant.
- Name any Cancel, missing-file, or permission behavior covered.
- Report verification commands and results.
