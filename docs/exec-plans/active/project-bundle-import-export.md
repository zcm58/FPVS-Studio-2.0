# FPVS Project Bundle Import/Export

Status: Active

## User Workflow

Users can export one portable `.fpvsbundle` file from a complete project, share that
single file, and import it on another machine through FPVS Studio. Import creates a new
project under the receiving user's configured FPVS Studio root, restores project settings
and stimulus assets, asks the receiver to confirm local display geometry/refresh before
opening, opens the new project, and removes temporary staging files.

The GUI presents a review step before import, keeps processing status visible whether
the workflow starts from Welcome or an open project, makes imported-versus-local display
settings an explicit comparison, and keeps a persistent export result surface available
until the user dismisses it.

Before choosing the bundle filename, export also lets the user set the project name
embedded in the portable copy. The exported copy receives the matching project id and
stimulus-manifest identity without renaming or mutating the open source project. This
makes same-machine export/import testing produce an intentionally distinct project.

## Boundaries

- Keep the editable `project.json` and `stimuli/manifest.json` as the source of truth.
- Store bundle metadata in a separate versioned `fpvs_bundle.json` member inside the
  archive.
- Include project stimuli needed for authoring and launch; exclude `cache/`, `logs/`,
  and `runs/` from the first bundle workflow.
- Keep archive validation and path checks in core, without PySide6 or PsychoPy imports.
- Use GUI actions only as orchestration around the core bundle service.
- Stage imports under the FPVS Studio root and delete staging paths after success or
  failure.
- Use Qt primary-screen metadata for quick display detection in the import confirmation
  dialog; keep PsychoPy imports behind the engine boundary.
- Keep file selection and destination paths user-visible without persisting new absolute
  paths into project data.
- Keep the existing stage-only progress callbacks for this polish pass; determinate file
  counts and ETA remain future contract work rather than GUI-invented progress.
- Reuse shared PySide6 components, theme tokens, and button roles for bundle dialogs and
  result pages.
- Resolve the configured FPVS Studio root as an absolute path. Never derive an import
  destination from the application working directory; reject legacy relative root
  settings so the user can choose the intended root again.
- Apply an export-name override only to the archived `project.json`, archived
  `stimuli/manifest.json`, and bundle metadata, with payload hashes computed from those
  rewritten archive bytes. Do not mutate files in the active project root.

## Verification

- Unit tests for export validation, archive contents, checksums, import staging cleanup,
  project-id collisions, and path traversal rejection.
- GUI smoke tests for save/open dialogs, Cancel behavior, export action, and import
  action opening the imported project.
- GUI smoke tests for import review choices, Welcome progress visibility, explicit
  display-setting actions, persistent export completion, and copy/open-folder actions.
- Unit and GUI tests for export-name overrides, unchanged source project identity, and
  imported project placement beneath the configured absolute Studio root.
- Focused pytest commands for the bundle unit tests and GUI import/export smoke tests.
