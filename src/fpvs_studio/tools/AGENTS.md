# AGENTS.md

## Scope of this directory

`src/fpvs_studio/tools/` is reserved for future Studio-native utility modules.

The current user-facing `Tools > Image Resizer` page is Studio-native code in
`src/fpvs_studio/gui/image_resizer_page.py` backed by preprocessing normalization
services. The imported FPVS Toolbox reference files were archived under
`docs/references/archive/fpvs-toolbox-image-resizer/`.

## Requirements

- Use `docs/GUI_WORKFLOW.md`, `docs/FRONTEND.md`, and
  `tests/gui/test_image_resizer_page.py` for the landed Image Resizer workflow,
  GUI expectations, and smoke coverage.
- Adapt behavior into FPVS Studio boundaries before exposing it to users.
- Use `fpvs_studio.preprocessing` for resize, conversion, inspection, derived
  variants, manifests, and deterministic transform metadata.
- Use `fpvs_studio.gui.components` for any Studio GUI surface.
- Run long image work through Qt worker patterns; do not block the UI thread.
- Return structured processing results from backend code instead of GUI log
  strings.

## Restrictions

- Do not import `Main_App.gui.*` in final Studio-integrated code.
- Do not move image preparation into runtime, compiler, `RunSpec`,
  `SessionPlan`, exporters, or PsychoPy engine code.
- Do not silently resize images as a validation fallback.
- Do not mutate conditions, project schema, or persisted project paths unless
  the active implementation plan explicitly scopes that change.
- Do not add hard-coded user paths or drive assumptions.
