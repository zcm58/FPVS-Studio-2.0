# UI action discovery and condition navigation

Status: Completed

## Workflow and evidence

User-authorized research and implementation on `feature/ui-action-discovery`.
Compare PsychoPy Builder's overview/detail organization and OpenSesame's command
palette and experiment overview with Studio's existing Home/eight-step Setup model.
Implement original PySide6 controls; do not copy third-party code or assets.

Primary references:

- https://psychopy.org/builder/concepts.html
- https://github.com/psychopy/psychopy-app
- https://osdoc.cogsci.nl/4.0/manual/interface/
- https://github.com/open-cogsci/OpenSesame
- https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/command-bar
- https://www.nngroup.com/articles/ten-usability-heuristics/
- https://www.nngroup.com/articles/progressive-disclosure/

## Design decisions

| Reference | Useful interface pattern | Adaptation in Studio |
| --- | --- | --- |
| OpenSesame interface and public Qt repository | Command palette (`Ctrl+Shift+P`), overview beside the editor | Find Action backed by existing QActions; filter the existing condition navigator |
| PsychoPy Builder and public native App repository | Routine/detail and Flow/overview separation | Keep the condition list next to its editor and preserve selected context during filtering |
| Microsoft command-bar guidance | Visible labels, clear command hierarchy and secondary commands on demand | File > Find Action and its keyboard shortcut; retain Launch and wizard Next as primary actions |
| NN/g usability heuristics | Recognition, keyboard efficiency, visible status and error recovery | Search aliases, menu-location/shortcut columns, unavailable counts, empty-result recovery and full-value tooltips |
| NN/g progressive disclosure | Keep occasional controls out of the primary task | Search existing tools without adding setup tabs, Advanced buttons or explanatory paragraphs |

Repository references are inspected as design precedents, not dependencies.
OpenSesame and PsychoPy App identify GPL-3.0 licenses; all implementation here is
original and uses existing PySide6 dependencies and Studio theme tokens. No external
source, artwork, icons or screenshots were copied. PsychoPy's separate modern
[Studio repository](https://github.com/psychopy/psychopy-studio) is another interface
reference, but its web stack is outside this native application's architecture.

A full session-flow visualization is a possible later improvement, subject to its own
design and authoritative SessionPlan mapping. It is not part of this implementation.

## Scope and boundaries

- Find Action: File menu entry and Ctrl+F in Home/Setup, searchable
  existing commands with category/shortcut context, keyboard navigation, explicit
  unavailable/no-result states, and existing QAction dispatch/permissions.
- Conditions: searchable existing navigator, full-name access, matching feedback,
  and stable condition identity/order and pending-edit behavior.
- Reuse `gui.components` theme helpers and existing document/controller services.
  Keep the eight-step workflow, readiness, project formats, runtime and timing intact.
- Palette minimum 600x400, default 680x460; menu chrome fits Home's 760x520 minimum.
  Conditions still fits the full 1120x820 wizard, including native AB and word states.
  These are acceptance targets, with registered geometry tests; visible validation
  remains pending. The menu corner retains the existing save badge.

## Verification and acceptance

- Baseline `./scripts/verify.ps1 -Scope gui -Tier focused`: 17 passed.
- Register focused Qt tests for search, keyboard activation/dismissal, disabled
  actions, busy guards, selection preservation, long names and geometry.
- Run GUI/docs focused checks and repo precommit after implementation.
- Do not launch Qt locally without explicit approval for a safe visible session.
  Document manual light/dark theme, long-content, keyboard and sizing acceptance.

## Progress

- [x] Clean working tree checked; feature branch created; GUI baseline passed.
- [x] Comparator research and repository constraints inspected.
- [x] Implement and review command palette and condition navigation.
- [x] Verify safe checks and document research, behavior and remaining visible checks.

Source review corrected palette Home routing to use the wizard's existing return
handler, retaining design-discard, Review and incomplete-setup confirmations.
Selected nonmatching conditions stay visible with explicit feedback; filtering itself
does not flush drafts. Existing focus-loss/debounce behavior remains active.

User review moved Find Action into the File menu, beside Settings, and removed the
main-window button and duplicate View entry. A subsequent user request selected
Ctrl+F as Studio's Find Action shortcut. The unused button styling and corner
container were removed; the save badge uses its
original corner-widget layout. Registered tests and the visible smoke path cover
the revised placement.

User-requested follow-up researched GPT-6 Astra prompting and professional native UI
guidance. Root, source, GUI, assets and packaging AGENTS.md now contain scoped design
rules, with a cited synthesis in `docs/design-docs/agent-ui-design.md`. Root guidance
applies to all other package scopes without repeating the same prompt in backend
files. This documentation follow-up preserves the existing Qt approval boundary and
does not change the configured model or application behavior.

## Changed files and verification record

- `src/fpvs_studio/gui/action_palette.py`: native command search and keyboard dispatch.
- `src/fpvs_studio/gui/main_window.py`: catalog, menu entry, navigation and busy guards.
- `src/fpvs_studio/gui/components.py`: shared palette theme.
- `src/fpvs_studio/gui/condition_setup_step.py`: condition filter and selection feedback.
- `tests/gui/test_action_palette.py`: command, navigation, keyboard and geometry coverage.
- `tests/gui/test_condition_search.py`: filter, draft, selection and geometry coverage.
- `tests/gui/test_setup_conditions.py`: navigator/editor top alignment.
- `tests/qt_test_files.txt`: registration of both new Qt test modules.
- `ARCHITECTURE.md`, `docs/FRONTEND.md`, `docs/GUI_WORKFLOW.md`,
  `docs/agent/agent-index.md`, `docs/PLANS.md`, and this plan: current contracts,
  routing, design evidence and manual acceptance.

Verification on the feature branch:

- GUI focused: Ruff and compilation pass; 17 safe tests pass.
- Docs focused: hygiene pass; 10 tests pass.
- Agent-design guidance follow-up: docs hygiene and all 10 focused tests pass;
  local Markdown links resolve across the 11 changed guidance/routing files.
  This follow-up changes documentation only; no GUI execution was needed.
- File-menu placement follow-up: GUI focused passes again (Ruff, compilation and
  17 tests); docs focused passes again (hygiene and 10 tests). The registered menu,
  shortcut and save-badge layout coverage is updated but was not run locally.
- Source type checking: all 235 source files pass as part of precommit.
- Initial repo precommit: lint, compilation, mypy and audits pass. The non-Qt suite reports
  2,959 passed, 11 skipped and one failure in the unchanged
  `test_import_project_bundle_never_overwrites_existing_project_folder`: Windows
  denied the staging-folder rename with `WinError 5`.
- Targeted follow-up:
  `.venv3.10/Scripts/python.exe -m pytest --disable-plugin-autoload -p pytest_timeout -q tests/unit/test_project_bundle.py`
  passes all 65 tests, including the failed case. The access failure did not reproduce;
  no bundle-I/O code was changed. That initial full precommit run was not green.
- Pre-merge feature verification: repo precommit passes with 2,960 tests passed
  and 11 skipped. The skips are Windows symlink privilege limitations; the earlier
  bundle staging-folder failure did not recur.
- Integrated master verification: repo precommit passes with 3,043 tests passed
  and 11 skipped; Ruff, compilation, mypy across 236 source files, repository
  audits and documentation hygiene pass. The skips remain Windows symlink cases.
- Registered Qt tests and the full visible acceptance matrix: not run.
  The subsequent user request for screenshots authorized a visible local preview.
  Actual Windows captures of Home, Find Action, filtered Conditions and native AB
  Design were taken with a temporary demo project in the dark theme, using Home's
  1120x720 size, the 680x460 palette and the 1120x820 wizard. These inspected states
  showed their controls within the window; this is not the full minimum-size,
  light-theme, scaling or automated Qt acceptance matrix.
  These captures precede the requested move to File > Find Action.
  The exact acceptance path is in `docs/GUI_WORKFLOW.md` under Action Discovery And
  Condition Search, including the 600x400/680x460 palette and 1120x820 wizard.

The user authorized committing, pushing and merging the implementation into the
previous branch, `master`. Feature commit `11962ab` was pushed on
`feature/ui-action-discovery`. The landing includes the newer upstream master work;
the plan-index conflict was resolved by retaining the current upstream entries and
listing this implementation as completed. Automated Qt and the full visible matrix
remain unverified as described above and in `docs/GUI_WORKFLOW.md`.
