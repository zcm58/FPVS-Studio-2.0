# AGENTS.md

## Scope of this directory

`src/fpvs_studio/tools/` holds imported/reference utility code that may become
Studio-native tools after an execution plan moves to active implementation.

Current files from FPVS Toolbox are planning ground truth for the future image
preparation tool. They are not final production architecture.

## Requirements

- Start image-preparation work from
  `docs/exec-plans/planned/fpvs-toolbox-image-prep-tool.md` until that plan is
  moved to `docs/exec-plans/active/`.
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
