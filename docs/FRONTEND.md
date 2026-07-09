# Frontend

FPVS Studio's frontend is the Windows-focused PySide6 GUI. There is no web frontend in
the active app.

## Public GUI Surface

- Start GUI work from `../src/fpvs_studio/gui/AGENTS.md`.
- Use `../src/fpvs_studio/gui/components.py` for shared widgets, button roles, labels,
  status badges, and theme helpers.
- Use `../src/fpvs_studio/gui/design_system.py` for tokens and tiny text helpers.
- Keep detailed behavior and test guidance in `GUI_WORKFLOW.md`.

## Skill Routing for GUI Work

FPVS Studio's frontend remains PySide6. Global UI skills may help agents reason about
the product experience, but implementation must keep using PySide6 widgets, the shared
component layer, Qt worker patterns, and pytest-qt verification.

- Use `.agents/skills/pyside6-gui-cleanup` for widget refactors, dialog polish, shared
  component usage, status/error UX, worker/threading checks, and QAction import cleanup.
- Use `.agents/skills/pytest-qt-smoke` when GUI behavior changes need focused smoke
  coverage.
- Use `diagnose` before editing when a GUI test hangs, a modal blocks, a worker thread
  does not finish, or a layout/runtime regression is reported. Start from a single
  pytest node or focused script with an explicit timeout.
- Use `impeccable` / `delight`, `frontend-design`, or `ui-ux-pro-max` only for concrete
  PySide6 product-design questions such as Setup Wizard density, Home launch hierarchy,
  button role clarity, empty/error state wording, or visual consistency with
  `gui.components`.
- If those global UI skills suggest web, React, Tailwind, browser animation, mobile, or
  deployment patterns, translate only the relevant design intent into existing PySide6
  components and discard the stack-specific advice.
- Use `web-design-guidelines` only for `../docs-site/` or MkDocs web documentation UI,
  not for the desktop authoring app.

GUI verification still follows this repo's gates: focused pytest-qt coverage for changed
behavior, `.\scripts\check_gui.ps1` for GUI workflow changes, and
`.\scripts\check_quality.ps1` when GUI work touches multiple layers.

## GUI Architecture

- First-run startup shows a concise FPVS Studio Root Folder setup guide before the
  native folder picker when no valid root is configured.
- Home is the daily launch surface for ready projects, centered around one launch
  card with create, import, open, setup, readiness, summary metrics, and the primary
  launch action.
- Welcome and Home share the same launch-surface frame/styling so opening a ready
  project keeps a stable outer window and card treatment.
- Setup Wizard is the guided setup/editing surface. Setup uses the compact
  Welcome/Home-sized `1120x720` default window, with Image Resizer using the
  same focused utility footprint instead of the larger workspace sizing. Wizard
  pages share the same setup step surface so content
  width, margins, and vertical alignment stay consistent across steps. The shared
  setup frame, top progress stepper, bottom navigation, and visible child widgets
  must fit at `1120x720` without bottom clipping or required vertical scrolling.
- Conditions is a combined guided setup area for condition list/actions, names,
  triggers, instructions, modality selection, image-folder assignment, typed word-list
  authoring, control-condition creation, and image normalization. It uses compact list
  rows and source cards without extra section headers. Raw image-folder selection is
  permissive; inconsistent image sizes are handled by the guided normalization flow
  before leaving Conditions. Control-condition creation and normalization stay
  image-only paths.
- Fixation and Response are split guided setup areas: Fixation handles color-change
  schedule/timing, while Response handles accuracy tracking, response key/window,
  appearance, and preview.
- Open Existing Project is the welcome entry point for the Manage Projects surface,
  which opens known projects or moves project folders to the Windows Recycle Bin with
  confirmation. Import New Project uses the same `.fpvsbundle` import workflow exposed
  in the File menu, and Welcome accepts dropped local `.fpvsbundle` files.
- Settings exposes app-level preferences for the FPVS Studio Root Folder, condition
  templates, run export mode, and Sophia Mode. These preferences are persisted with
  `QSettings` and remain outside project files.
- The current Setup Wizard does not expose Advanced buttons; dense/internal support
  pages should remain behind guided workflows unless a future plan explicitly
  reintroduces them.
- GUI code may coordinate document services and runtime launches, but core validation,
  compilation, session planning, and runtime flow remain outside widgets.
- Current runtime launch controls intentionally do not expose serial trigger settings,
  display selection, or fullscreen toggles; those remain backend/runtime contract values.

## Verification

- Focused GUI changes need pytest-qt coverage or documented manual smoke steps.
- Setup Wizard layout changes must run or update the focused compact no-clipping
  coverage in `tests/gui/test_setup_wizard_shell.py` and should smoke all six
  steps at `1120x720`.
- Run `.\scripts\check_gui.ps1` for GUI workflow changes.
- Run `.\scripts\check_quality.ps1` when GUI changes touch multiple layers.
