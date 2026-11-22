# Agent Task Index

Choose the row for the change, then read its guide and relevant contract section.

## Verification Scopes

Paths are repository-relative. [Task recipes](task-recipes.md) locate less obvious
owners and targeted tests.

| Scope | Use for | Governing guide | One focused contract |
| --- | --- | --- | --- |
| `repo` | Harness, shared configuration, Windows source bootstrap and PyCharm setup, cross-layer ownership | `AGENTS.md` | `ARCHITECTURE.md` or [Windows setup](../ENVIRONMENT.md#windows-source-setup) |
| `macos` | Source bootstrap, environment/PyCharm repair, automatic completion reports, display/input recovery, resolution confirmation, native adapters and bundle handoff | `AGENTS.md` plus owning package guide | `docs/MACOS_SUPPORT.md` |
| `docs` | Guidance, contracts and plans | `AGENTS.md` | Edited document; `docs/exec-plans/README.md` for plan work |
| `gui` | PySide6 authoring, Settings, Tools, controllers and workers | `src/fpvs_studio/gui/AGENTS.md` | `docs/GUI_WORKFLOW.md` for behavior, `docs/FRONTEND.md` for design, [mid-study edit safeguard](../product-specs/studio.md#safeguard-for-changes-during-collection) |
| `core` | Models, validation and neutral domain logic | `src/fpvs_studio/core/AGENTS.md` | Relevant model contract from `ARCHITECTURE.md` |
| `compiler` | Compiled runs, sessions, participant reuse policies, scheduling and fixation | `src/fpvs_studio/core/AGENTS.md` | `docs/RUNSPEC.md` for runs or `docs/SESSION_PLAN.md` for sessions |
| `project-io` | Persistence, Studio → Toolbox handoff, runnable bundles, templates and paths | `src/fpvs_studio/core/AGENTS.md` | [Current exports](../PROJECT_CONFIG.md#user-workflow-and-limits), [whole-study handoff](../PROJECT_CONFIG.md#whole-study-handoff), [project open/save](../GUI_WORKFLOW.md#project-opening-and-saving) |
| `preprocessing` | Image intake, inspection, variants, manifests and standalone equalization | `src/fpvs_studio/preprocessing/AGENTS.md` | Relevant asset/manifest test or [Image Equalizer](../product-specs/image-equalizer.md) |
| `runtime` | Launch, preflight, session flow, scoring and participant results/exports | `src/fpvs_studio/runtime/AGENTS.md` | Relevant `docs/RUNTIME_EXECUTION.md` section; [exports](../RUNTIME_EXECUTION.md#exports) |
| `engine` | Rendering, task-screen fitting, response pointers, graphics lifetime and frame playback | `src/fpvs_studio/engines/AGENTS.md` | Relevant `docs/ENGINE_INTERFACE.md` section |
| `triggers` | Hardware adapters, local UDP markers, port discovery, recovery, Windows write completion and offline Unicorn timing | `src/fpvs_studio/triggers/AGENTS.md` or `src/fpvs_studio/tools/AGENTS.md` for offline timing | [Recording](../RUNTIME_EXECUTION.md#trigger-behavior), [Trigger Tester](../GUI_WORKFLOW.md#trigger-tester) or [Unicorn timing report](../RUNTIME_EXECUTION.md#unicorn-recorder-timing-report) |
| `updates` | Source/platform routing, updater protocol, cache, downloads and install handoff | `src/fpvs_studio/updates/AGENTS.md` | `docs/PACKAGING.md#in-app-update-flow` |
| `library` | Public and lab catalog, enrollment, verified downloads, submissions and project updates | `src/fpvs_studio/library/AGENTS.md` | Relevant `docs/EXPERIMENT_LIBRARY.md` section |
| `data-sharing` | Consent, outbox, delivery and comparisons | `src/fpvs_studio/data_sharing/AGENTS.md` | Relevant `docs/DATA_SHARING.md` section |
| `packaging` | Versions, builds, DLL origins, installers, patches and smoke | `packaging/AGENTS.md` | Relevant `docs/PACKAGING.md` section |

Publishing also requires `src/fpvs_studio/developer/AGENTS.md`. For backend changes,
follow the owning sibling repository's guidance instead of loading desktop contracts.
For Settings > Account, use `gui`; for Studio connection and upload linking, also use `library`.
The [account portal plan](../exec-plans/active/fpvs-account-portal.md) links the website
workflow to its separate owner.

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

## Performance and output parity

- Use the affected entry point with the same project, assets, resolved seeds,
  settings, refresh rate and cache state on both builds. Check deterministic
  results bit for bit, including affected stimulus derivatives, compiled frame
  schedules, fixation events and trigger sequences. For runtime scoring and
  exports, replay the same recorded inputs and preserve the observed timing data.
- Count costly operations where they happen. For example, compiling repeated
  entries that share task images should hash each unique image once per compile.
  Exercise a subsequent compile after changing an image to verify fresh validation.
  Preserve independent per-entry schedules and launch preflight checks.
  [Compilation input preparation](../SESSION_PLAN.md#compilation-input-preparation)
- Measure the affected user action end to end, including GUI stalls and any
  work moved into launch or playback. Compare relevant first and repeated uses
  and repeat noisy timings. Physical display and EEG timing claims require
  hardware evidence. For a less efficient design, quantify its cost against
  the alternative and explain the architectural, integrity or resource benefit.
  A measured slowdown requires the user's explicit approval even when another
  workflow improves.

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

Windows and Mac experiment monitor selection follows the `gui` route and the
[launch workflow](../GUI_WORKFLOW.md#launch); native mode validation and engine screen
mapping also use the `runtime` and `engine` focused checks. Mac enumeration, selected
monitor rendering, Retina backing and bounded-probe coverage use the `macos` route.
