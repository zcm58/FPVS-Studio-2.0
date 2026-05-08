# AGENTS.md

## Scope of this directory

`src/fpvs_studio/tools/` holds imported/reference image-resizing utility code.

The current user-facing `Tools > Image Resizer` page is Studio-native code in
`src/fpvs_studio/gui/image_resizer_page.py` backed by preprocessing normalization
services. Files in this package remain reference/comparison material unless a future
plan explicitly scopes their extraction.

## Requirements

- Use `docs/exec-plans/completed/fpvs-toolbox-image-prep-tool.md` for the landed
  Image Resizer workflow and boundaries.
- Adapt behavior into FPVS Studio boundaries before exposing it to users.
- Use `fpvs_studio.preprocessing` for resize, conversion, inspection, derived
  variants, manifests, and deterministic transform metadata.
- Use `fpvs_studio.gui.components` for any Studio GUI surface.
- Run long image work through Qt worker patterns; do not block the UI thread.
- Return structured processing results from backend code instead of GUI log
  strings.
- Do not import `pyside_resizer.py` from Studio code; it is reference-only and its
  PySide6 imports are tracked boundary debt until the file is removed, relocated, or
  explicitly archived.

## Restrictions

- Do not import `Main_App.gui.*` in final Studio-integrated code.
- Do not move image preparation into runtime, compiler, `RunSpec`,
  `SessionPlan`, exporters, or PsychoPy engine code.
- Do not silently resize images as a validation fallback.
- Do not mutate conditions, project schema, or persisted project paths unless
  the active implementation plan explicitly scopes that change.
- Do not add hard-coded user paths or drive assumptions.
