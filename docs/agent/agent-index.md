# Agent Task Index

Use this page after `AGENTS.md` to choose the smallest useful context and verification
route. Pick one primary scope, read only its initial context, and expand when failures or
cross-layer behavior require it.

## Fast Route

1. Run `git status --short --branch`.
2. Match the task to one scope below.
3. Read the listed package guide and focused contract document.
4. Run the scope's focused verification before broad source inspection.
5. Inspect only relevant failures, symbols, and tests.
6. Run the repo precommit tier when shared behavior or multiple layers changed.

## Verification Scopes

| Scope | Use for | Initial context |
| --- | --- | --- |
| `repo` | Harness, shared configuration, cross-layer changes, or uncertain ownership | `ARCHITECTURE.md`, this index, and the changed paths |
| `docs` | Agent guidance, contracts, plans, or docs hygiene | `docs/index.md`, the document being edited, and `docs/exec-plans/README.md` for plan work |
| `gui` | PySide6 windows, dialogs, controllers, components, workers, or GUI behavior | `src/fpvs_studio/gui/AGENTS.md`, `docs/FRONTEND.md`, `docs/GUI_WORKFLOW.md`, and the focused GUI test file |
| `core` | Models, validation, neutral contracts, compilation helpers, or domain logic | `src/fpvs_studio/core/AGENTS.md` and the relevant contract document |
| `compiler` | `RunSpec`/`SessionPlan` compilation, scheduling, fixation realization, or assets in compiled contracts | `src/fpvs_studio/core/AGENTS.md`, `docs/RUNSPEC.md`, and `docs/SESSION_PLAN.md` |
| `project-io` | Project persistence, `.fpvsconfig`, `.fpvsbundle`, templates, paths, import, or export | `src/fpvs_studio/core/AGENTS.md`, `docs/GUI_WORKFLOW.md`, and the active plan when bundle work is in scope |
| `preprocessing` | Image intake, inspection, normalization, variants, or manifests | `src/fpvs_studio/preprocessing/AGENTS.md` and the relevant asset/manifest tests |
| `runtime` | Launch, preflight, session flow, participant history, scoring, or exports | `src/fpvs_studio/runtime/AGENTS.md` and `docs/RUNTIME_EXECUTION.md` |
| `engine` | Presentation interface, PsychoPy rendering, frame timing, or display screens | `src/fpvs_studio/engines/AGENTS.md`, `docs/ENGINE_INTERFACE.md`, and `docs/RUNSPEC.md` |
| `triggers` | Trigger contracts, serial hardware adapters, marker writes, or trigger logs | `src/fpvs_studio/triggers/AGENTS.md` and the trigger sections of `docs/RUNTIME_EXECUTION.md` |
| `updates` | Release checks, installer downloads, updater backend, or update GUI coordination | `src/fpvs_studio/updates/AGENTS.md` and `docs/PACKAGING.md` |
| `packaging` | Versioning, PyInstaller, Inno Setup, branding, executable builds, or packaged smoke | `packaging/AGENTS.md`, `docs/PACKAGING.md`, and `pyproject.toml` |

Run a route with:

```powershell
./scripts/verify.ps1 -Scope <scope> -Tier focused
```

Add `-List` to a scoped command to inspect the configured steps. Use
`./scripts/verify.ps1 -CheckConfig` after editing `.agents/verification.toml`, the
PowerShell wrapper, or the Python driver.

## Verification Tiers

- `focused`: selected scope checks plus changed-file Ruff and Python compilation.
- `precommit`: repo audits, mypy, changed-file checks, and the safe non-Qt pytest suite.
- `full-ci`: full Ruff, mypy, and pytest with registered Qt tests explicitly enabled.

Use the broader local gate after cross-layer or shared-contract changes:

```powershell
./scripts/verify.ps1 -Scope repo -Tier precommit
```

Do not run `full-ci` locally by default. Qt tests are excluded before import during
ordinary local verification. CI owns explicit Qt opt-in and offscreen configuration;
local Qt execution requires user approval and a safe visible environment.

## Skill Routing

| Task | Repo-local skill |
| --- | --- |
| PySide6 layout, components, workers, status/error UX | `.agents/skills/pyside6-gui-cleanup/SKILL.md` |
| Add or maintain registered pytest-qt coverage | `.agents/skills/pytest-qt-smoke/SKILL.md` |
| Project roots, dialogs, persistence, export/import paths | `.agents/skills/project-path-audit/SKILL.md` |
| Protected retired paths or historical behavior boundaries | `.agents/skills/legacy-boundary-review/SKILL.md` |
| PsychoPy migration across compile/runtime/engine seams | `.agents/skills/fpvs-psychopy-migration/SKILL.md` |

Read a selected skill completely before acting. A passing skill audit is sufficient
evidence for its invariant unless the task changes that audit or boundary.

## Planning Route

- Planning map: `docs/PLANS.md`
- Plan rules: `docs/exec-plans/README.md`
- Current implementation: `docs/exec-plans/active/`
- Concrete future work: `docs/exec-plans/planned/`
- Historical implementation notes: `docs/exec-plans/completed/`
- Measured debt: `docs/exec-plans/tech-debt-tracker.md`

Read completed plans only when historical rationale is necessary. Never use them in
place of current architecture and workflow documents.
