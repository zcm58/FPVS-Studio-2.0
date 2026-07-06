# FPVS Project Bundle Import/Export

Status: Active

## User Workflow

Users can export one portable `.fpvsbundle` file from a complete project, share that
single file, and import it on another machine through FPVS Studio. Import creates a new
project under the receiving user's configured FPVS Studio root, restores project settings
and stimulus assets, asks the receiver to confirm local display geometry/refresh before
opening, opens the new project, and removes temporary staging files.

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

## Verification

- Unit tests for export validation, archive contents, checksums, import staging cleanup,
  project-id collisions, and path traversal rejection.
- GUI smoke tests for save/open dialogs, Cancel behavior, export action, and import
  action opening the imported project.
- Focused pytest commands for the bundle unit tests and GUI import/export smoke tests.
