# Agent Task Index

After root `AGENTS.md`, choose one scope, its guide and one contract section.
Run focused verification, then inspect implicated symbols or tests. Read the
matching [active plan](../PLANS.md) for feature-sized or cross-layer work.

## Verification Scopes

Paths are repository-relative. [Task recipes](task-recipes.md) locate less obvious
owners and targeted tests.

| Scope | Use for | Governing guide | One focused contract |
| --- | --- | --- | --- |
| `repo` | Harness, shared configuration, Windows source bootstrap and PyCharm setup, cross-layer ownership | `AGENTS.md` | `ARCHITECTURE.md` or [Windows setup](../ENVIRONMENT.md#windows-source-setup) |
| `macos` | Source bootstrap, environment/PyCharm repair and diagnostic reporting, display/input recovery, resolution confirmation, native adapters and bundle handoff | `AGENTS.md` plus owning package guide | `docs/MACOS_SUPPORT.md` |
| `docs` | Guidance, contracts and plans | `AGENTS.md` | Edited document; `docs/exec-plans/README.md` for plan work |
| `gui` | PySide6 authoring, Settings, Tools, controllers and workers | `src/fpvs_studio/gui/AGENTS.md` | `docs/GUI_WORKFLOW.md` for behavior or `docs/FRONTEND.md` for design |
| `core` | Models, validation and neutral domain logic | `src/fpvs_studio/core/AGENTS.md` | Relevant model contract from `ARCHITECTURE.md` |
| `compiler` | Compiled runs, sessions, participant reuse policies, scheduling and fixation | `src/fpvs_studio/core/AGENTS.md` | `docs/RUNSPEC.md` for runs or `docs/SESSION_PLAN.md` for sessions |
| `project-io` | Persistence, configs, bundles, templates and paths | `src/fpvs_studio/core/AGENTS.md` | Configs: [exchange format](../PROJECT_CONFIG.md); other persistence/imports: `docs/GUI_WORKFLOW.md` |
| `preprocessing` | Image intake, inspection, variants and manifests | `src/fpvs_studio/preprocessing/AGENTS.md` | Relevant asset/manifest test |
| `runtime` | Launch, preflight, session flow, scoring and participant results/exports | `src/fpvs_studio/runtime/AGENTS.md` | Relevant `docs/RUNTIME_EXECUTION.md` section; [exports](../RUNTIME_EXECUTION.md#exports) |
| `engine` | Rendering, task-screen fitting, response pointers, graphics lifetime and frame playback | `src/fpvs_studio/engines/AGENTS.md` | Relevant `docs/ENGINE_INTERFACE.md` section |
| `triggers` | Hardware adapters, port discovery, recovery and Windows write completion | `src/fpvs_studio/triggers/AGENTS.md` | [Recording](../RUNTIME_EXECUTION.md#trigger-behavior) or [Trigger Tester](../GUI_WORKFLOW.md#trigger-tester) |
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

Audits require PowerShell (`pwsh` on macOS). Non-Qt tiers support `-Workers 4`
(default one). See [test performance](../ENVIRONMENT.md#test-performance) for
isolation, Windows test paths and `-Durations`.

## Skill Routing

| Task | Read this repo-local skill |
| --- | --- |
| PySide6 layout, components, workers or status/error UX | `.agents/skills/pyside6-gui-cleanup/SKILL.md` |
| Registered Qt smoke coverage | `.agents/skills/pytest-qt-smoke/SKILL.md` |
| Roots, dialogs, persistence or import/export paths | `.agents/skills/project-path-audit/SKILL.md` |
| Protected legacy boundaries | `.agents/skills/legacy-boundary-review/SKILL.md` |
| Existing PsychoPy experiment migration | `.agents/skills/fpvs-psychopy-migration/SKILL.md` |

Read the selected skill completely. Keep behavior in its canonical contract and
add topic entry points to the optional recipes.
