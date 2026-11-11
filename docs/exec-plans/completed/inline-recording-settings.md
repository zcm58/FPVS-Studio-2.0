# Inline Recording settings

Status: Completed

## Requested outcome

On 2026-11-11 the user requested the recording hardware editor directly on
Settings > Recording, with Save Default Settings on the same page, eliminating
the nested project/default editor dialogs from this Settings workflow.

## Workflow and boundaries

- The existing Home recording link opens Recording with the editable hardware,
  endpoint and timing fields immediately available.
- Apply to Project saves the current project override; Save Default Settings
  saves the displayed configuration as this computer's default. An inheriting
  project follows a changed default, while an explicit project override remains
  independent. BioSemi serial ports stay project-owned.
- Use Computer Default clears a project override and reloads the displayed form.
  Changing categories preserves pending edits; closing Settings discards edits
  that have not been applied. Failed saves retain the draft and accepted state.
- Without a project, the same form edits the computer default and hides project
  actions and the project-only BioSemi port.
- Extract one reusable QWidget editor from the existing Recording Setup dialog.
  Keep the standalone dialog wrapper for required pre-launch review and preserve
  its validation and worker lifecycle. No persisted or compiled format changes.

## UI brief and acceptance

Researchers choose their hardware and save without opening another editor.
Use the existing Settings sidebar, scroll area, field styling and recording
guidance. Keep the main Apply action distinct from Save Default Settings and
show inheritance/default context without repeating the form's labels.

Settings retains its 860x560 minimum and 1000x680 default. Recording fields and
actions must remain accessible with vertical scrolling, never horizontal clipping.
Cover all hardware types, longest port/device labels, missing/invalid values,
busy checks, failed saves, inherited/overridden projects and no-project mode in
both themes. Metadata/access checks stay in workers and send no markers.

## Verification

- [x] Baseline GUI focused route: 180 passed.
- [x] Shared editor and inline Settings workflow implemented.
- [x] Registered GUI tests cover direct editing, save scopes, rollback, draft
  retention, worker cleanup and minimum/default layout budgets.
- [x] GUI/docs focused routes and repository precommit pass.
- [x] Workflow/ownership documentation updated and plan archived.

Verification on 2026-11-11:

- `./scripts/verify.ps1 -Scope gui -Tier focused`: 180 passed, changed-file Ruff
  and compilation passed.
- `./scripts/verify.ps1 -Scope docs -Tier focused`: 13 passed and documentation
  hygiene passed.
- `./scripts/verify.ps1 -Scope repo -Tier precommit -Workers 4`: 5931 passed,
  33 skipped; Windows/macOS mypy and repository audits passed. Skips concern
  native POSIX/macOS behavior, unavailable Windows symlink privileges, and the
  targeted PsychoPy reproduction version.
- Independent source review found no remaining actionable issues. Saved TriggerBox
  selections are protected from delayed discovery, and hidden/replaced editors
  detach their discovery jobs.

Visible Qt execution requires an approved safe environment and is not authorized
in this task. Manual smoke: click the Home recording link, edit each hardware
type inline, Apply/Save Default/Use Computer Default, switch categories and close,
then reopen and check persistence at both sizes/themes. Stub hardware checks or
use a separately qualified lab environment; this work does not qualify hardware.

The registered tests replace persistence callbacks, error dialogs, and hardware
discovery/access jobs with controlled fakes. They cover all five hardware choices
at both sizes and themes, failed-save retries, no-project default editing, BioSemi
port ownership, and late TriggerBox discovery after a successful save. The layout
helpers permit only intentional vertical scroll-content overflow; horizontal
overflow and child/text clipping checks remain active. No Qt or hardware checks
were executed during this task.

## Changed files

- `src/fpvs_studio/gui/settings_dialog.py`
- `src/fpvs_studio/gui/recording_dialog.py`
- `src/fpvs_studio/gui/packaged_smoke.py`
- `tests/gui/helpers.py`
- `tests/gui/test_settings_dialog.py`
- `tests/gui/test_recording_setup.py`
- `tests/gui/test_biosemi_recording_persistence.py`
- `tests/gui/test_default_recording_setup.py`
- `tests/gui/test_home_launch_surface.py`
- `src/fpvs_studio/gui/AGENTS.md`
- `ARCHITECTURE.md`
- `docs/agent/agent-index.md`
- `docs/FRONTEND.md`
- `docs/GUI_WORKFLOW.md`
- `docs/PLANS.md`
- This execution plan.

The previously implemented Home recording link is retained. Required pre-launch
recording review still uses the standalone wrapper around the shared editor.
