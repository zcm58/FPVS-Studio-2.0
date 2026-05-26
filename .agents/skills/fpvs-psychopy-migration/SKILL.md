---
name: fpvs-psychopy-migration
description: Use when migrating an existing PsychoPy-based FPVS experiment folder, .psyexp file, shortcut-linked PsychoPy experiment, Excel/CSV stimulus list, image folder, or word-list paradigm into an FPVS Studio-compatible project under an FPVS Studio Root Folder, including copying source stimuli, creating image or word conditions, preserving provenance, normalizing active image assets, and verifying project.json/manifest readiness.
---

# FPVS PsychoPy Migration

## Goal

Create a new FPVS Studio project from a legacy PsychoPy experiment folder without
moving or deleting source files. Preserve exact source stimulus identity, copy inputs
into the Studio project, normalize only the active image copies when Studio requires it,
and leave a provenance trail that explains every source list, copied file, skipped row,
condition name, and trigger code.

For schema details and copy/layout patterns, read
`references/migration-guide.md` after the source folder and target root are known.

## Workflow

1. Read repo guardrails first: `AGENTS.md`, `ARCHITECTURE.md`, and the path-related
   parts of `docs/FPVS_Studio_v1_Architecture_Spec.md`, `docs/RUNSPEC.md`, and
   `docs/GUI_WORKFLOW.md`.
2. Locate the FPVS Studio Root Folder from user input, app settings, or current
   project context. Never assume a root when more than one plausible root exists.
3. Inventory the legacy folder read-only:
   - top-level `.psyexp`, `.py`, `.lnk`, `.xlsx`, `.xls`, `.csv`, `.tsv`, `.txt`
   - shortcut targets via `WScript.Shell`
   - stimulus-list references in `.psyexp` and generated `*_lastrun.py`
   - existing image files and word-list workbooks
4. Extract condition facts:
   - condition names and trigger codes from readme files, PsychoPy code, or user notes
   - source list files and their stimulus columns
   - source roots used to resolve relative paths in each list
   - modality per condition: `image` or `word`
5. Copy source materials into a new Studio project:
   - copy images into `stimuli/original-images/<set_id>/`
   - copy word source files into `stimuli/original-word-lists/<set_id>/` for provenance
   - store word stimuli directly in `project.json` as `StimulusSet.modality="word"`
   - write `migration/` CSV/JSON reports for mapping, skipped rows, source lists, and
     linked PsychoPy experiments
6. Normalize active image conditions when required:
   - keep originals unchanged in `stimuli/original-images/`
   - create square PNG active copies under `stimuli/normalized-images/<set_id>/`
   - point image stimulus sets at normalized folders if validation requires square
     assets
7. Verify before finalizing:
   - copied-file hashes match source files
   - `project.json` loads with `load_project_file`
   - `validate_project(..., refresh_hz=60.0)` has no errors
   - `compile_session_plan` succeeds for mixed image/word sessions
   - `preflight_session_plan` succeeds with a simple validation engine when practical
   - report any remaining non-blocking repeat-balance warnings

## Rules

- Copy, never move, legacy source files unless the user explicitly asks to move them.
- Do not copy protected participant/IRB workbooks unless the user explicitly names them.
- Use project-relative POSIX paths in `project.json`, manifests, and reports.
- Use `pathlib.Path`, structured Excel/CSV readers, and image libraries instead of
  ad hoc string parsing.
- Keep the migration script temporary, usually under `.codex-tmp/`; do not commit
  user-specific absolute paths or generated project data to the repo.
- If a source list row is not a supported image for an image condition, skip it only
  with an explicit row-level report.
- Do not render word stimuli into images. Word conditions persist authored text in
  `project.json`.
- Keep the project-wide `oddball_onset` trigger code locked to `55`. Only set a
  nonstandard oddball marker when the user explicitly asks for it, and then record
  `allow_nonstandard_oddball_trigger_code=true` in the project/config audit trail.
- Keep source workbook/CSV copies in the project for auditability, but do not make
  Studio runtime depend on those copied lists after migration.

## Final Response

Summarize the target project path, conditions created, copied counts, skipped rows,
normalization results, validation status, and whether the originals were copied or
moved. Mention any warnings that are expected Studio guidance rather than blockers.
