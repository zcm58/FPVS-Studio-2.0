# Frontend

FPVS Studio's frontend is the Windows-focused PySide6 GUI. There is no web frontend in
the active app.

## Public GUI Surface

- Start GUI work from `../src/fpvs_studio/gui/AGENTS.md`.
- Use `../src/fpvs_studio/gui/components.py` for shared widgets, button roles, labels,
  status badges, and theme helpers.
- Use `../src/fpvs_studio/gui/design_system.py` for tokens and tiny text helpers.
- Keep detailed behavior and test guidance in `GUI_WORKFLOW.md`.

## GUI Architecture

- First-run startup shows a concise FPVS Studio Root Folder setup guide before the
  native folder picker when no valid root is configured.
- Home is the daily launch surface for ready projects, centered around one launch
  card with project actions, readiness, summary metrics, and the primary launch
  action.
- Welcome and Home share the same launch-surface frame/styling so opening a ready
  project keeps a stable outer window and card treatment.
- Setup Wizard is the guided setup/editing surface. Setup uses the compact
  Welcome/Home-sized default window, with Image Resizer retaining the larger
  workspace sizing.
- Conditions and Images are split guided setup areas: Conditions handles condition
  list/actions, names, triggers, and instructions; Images handles base/oddball
  folder assignment and image normalization. Raw folder selection is permissive;
  inconsistent image sizes are handled by the guided normalization flow.
- Fixation and Response are split guided setup areas: Fixation handles color-change
  schedule/timing, while Response handles accuracy tracking, response key/window,
  appearance, and preview.
- Open Projects is the welcome entry point for the Manage Projects surface, which
  opens known projects or moves project folders to the Windows Recycle Bin with
  confirmation. The File menu still exposes the same management surface.
- The current Setup Wizard does not expose Advanced buttons; dense/internal support
  pages should remain behind guided workflows unless a future plan explicitly
  reintroduces them.
- GUI code may coordinate document services and runtime launches, but core validation,
  compilation, session planning, and runtime flow remain outside widgets.
- Current runtime launch controls intentionally do not expose serial trigger settings,
  display selection, or fullscreen toggles; those remain backend/runtime contract values.

## Verification

- Focused GUI changes need pytest-qt coverage or documented manual smoke steps.
- Run `.\scripts\check_gui.ps1` for GUI workflow changes.
- Run `.\scripts\check_quality.ps1` when GUI changes touch multiple layers.
