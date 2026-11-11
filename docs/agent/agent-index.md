# Agent Task Index

After root `AGENTS.md`, choose one primary scope below. Read its governing guide
and one relevant contract section, not every linked document. Run focused verification,
then inspect implicated symbols/tests. Expand only for failures or cross-layer work.
Read the relevant active plan through [Plans](../PLANS.md) when its scope applies.

## Verification Scopes

Paths below are relative to the repository root. Read the listed guide before editing;
use document headings or `rg -n '^#{1,3} ' <document>` to choose the contract section.
[Optional task recipes](task-recipes.md) locate less obvious owners and targeted tests.

| Scope | Use for | Governing guide | One focused contract |
| --- | --- | --- | --- |
| `repo` | Harness, shared configuration, cross-layer ownership | `AGENTS.md` | `ARCHITECTURE.md` |
| `macos` | Source bootstrap, environment/PyCharm repair and diagnostic reporting, display/input recovery, resolution confirmation, native adapters and bundle handoff | `AGENTS.md` plus owning package guide | `docs/MACOS_SUPPORT.md` |
| `docs` | Guidance, contracts and plans | `AGENTS.md` | Edited document; `docs/exec-plans/README.md` for plan work |
| `gui` | PySide6 widgets, controllers, workers, inline project/default recording setup, Tools, Settings navigation/preferences and nine-step authoring | `src/fpvs_studio/gui/AGENTS.md` | Relevant `docs/GUI_WORKFLOW.md` section; `docs/FRONTEND.md` for design |
| `core` | Models, validation and neutral domain logic | `src/fpvs_studio/core/AGENTS.md` | Relevant model contract from `ARCHITECTURE.md` |
| `compiler` | Compiled runs, sessions, participant reuse policies, scheduling and fixation | `src/fpvs_studio/core/AGENTS.md` | `docs/RUNSPEC.md` for runs or `docs/SESSION_PLAN.md` for sessions |
| `project-io` | Persistence, configs, bundles, templates and paths | `src/fpvs_studio/core/AGENTS.md` | Configs: [exchange format](../PROJECT_CONFIG.md); other persistence/imports: `docs/GUI_WORKFLOW.md` |
| `preprocessing` | Image intake, inspection, variants and manifests | `src/fpvs_studio/preprocessing/AGENTS.md` | Relevant asset/manifest test |
| `runtime` | Launch, preflight, session flow, scoring and participant results/exports | `src/fpvs_studio/runtime/AGENTS.md` | Relevant `docs/RUNTIME_EXECUTION.md` section; [exports](../RUNTIME_EXECUTION.md#exports) |
| `engine` | Rendering, task-screen fitting, response pointers, graphics lifetime and frame playback | `src/fpvs_studio/engines/AGENTS.md` | Relevant `docs/ENGINE_INTERFACE.md` section |
| `triggers` | Hardware adapters, discovery, shared serial failure classification, vendor recovery, Windows write completion and transport evidence | `src/fpvs_studio/triggers/AGENTS.md` | `docs/RUNTIME_EXECUTION.md#trigger-behavior` |
| `updates` | Source/platform routing, updater protocol, cache, downloads and install handoff | `src/fpvs_studio/updates/AGENTS.md` | `docs/PACKAGING.md#in-app-update-flow` |
| `library` | Catalog, enrollment, submissions and project updates | `src/fpvs_studio/library/AGENTS.md` | Relevant `docs/EXPERIMENT_LIBRARY.md` section |
| `data-sharing` | Consent, outbox, delivery and comparisons | `src/fpvs_studio/data_sharing/AGENTS.md` | Relevant `docs/DATA_SHARING.md` section |
| `packaging` | Versions, builds, DLL origins, installers, patches and smoke | `packaging/AGENTS.md` | Relevant `docs/PACKAGING.md` section |

Publishing also requires `src/fpvs_studio/developer/AGENTS.md`. For backend changes,
follow the owning sibling repository's guidance instead of loading desktop contracts.

## Verification Tiers

```powershell
./scripts/verify.ps1 -Scope <scope> -Tier focused
./scripts/verify.ps1 -Scope repo -Tier precommit
```

- `focused`: scope checks plus changed-file Ruff/compilation.
- `precommit`: repo audits, mypy, changed-file checks and the safe non-Qt suite.
  Use it after shared behavior or cross-layer changes. All-source mypy targets
  primary Windows; a separate Darwin pass checks secondary Mac adapter owners.
- `full`: optional complete Ruff/mypy/pytest including registered Qt tests. It requires
  `FPVS_ALLOW_QT_TESTS=1` and user approval for a safe visible environment. Never set
  `QT_QPA_PLATFORM=offscreen` locally. Default collection excludes Qt modules before
  import, including registered `ProjectDocument` tests beneath `tests/unit/`.

The driver selects `.venv3.10`, `.venv`, then compatible current Python,
using each host's native `Scripts/python.exe` or `bin/python` layout. Existing audits
require PowerShell (`pwsh` on macOS).
Use `-List` to inspect steps and `-CheckConfig` after harness edits. Non-Qt tiers support
`-Workers 4` (default one); Qt stays serial. See
[test performance](../ENVIRONMENT.md#test-performance) for isolation and `-Durations`.
GitHub runs documentation publishing and primary Windows precommit before the
secondary macOS source/bundle lane. It does not replace local precommit,
visible GUI acceptance or physical display qualification.

## Skill Routing

| Task | Read this repo-local skill |
| --- | --- |
| PySide6 layout, components, workers or status/error UX | `.agents/skills/pyside6-gui-cleanup/SKILL.md` |
| Registered Qt smoke coverage | `.agents/skills/pytest-qt-smoke/SKILL.md` |
| Roots, dialogs, persistence or import/export paths | `.agents/skills/project-path-audit/SKILL.md` |
| Protected legacy boundaries | `.agents/skills/legacy-boundary-review/SKILL.md` |
| Existing PsychoPy experiment migration | `.agents/skills/fpvs-psychopy-migration/SKILL.md` |

Read the selected skill completely. A passing invariant audit is sufficient evidence
for that invariant; it does not replace focused or precommit checks. Keep detailed
behavior in its canonical contract; add topic entry points to the optional recipes
rather than expanding this front door.
