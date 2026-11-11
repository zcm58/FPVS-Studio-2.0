# Settings sidebar navigation

Status: Completed

## Requested outcome

Authorized on 2026-11-10. Reorganize FPVS Studio Settings to match the supplied
reference's left category column and right settings page, then commit and push.
Operators select General, Recording, Appearance, Workspace, Advanced or Diagnostics
and change preferences through the existing controls and save actions.

## Design and ownership

- `gui/settings_dialog.py` owns native list navigation, the selected page heading
  and stacked, vertically scrollable settings pages.
- General retains participant-run and eligible Test/Pilot controls. Appearance owns
  theme selection, and Workspace owns root-folder, templates and Library actions.
  Recording, Advanced and Diagnostics retain their existing controls.
- Reuse shared components and theme tokens. The sidebar and Close stay reachable,
  and the current category supplies the page title. Preserve callback behavior,
  control identities, error recovery and entered values across category changes.
- Use one `860x560` minimum and `1000x680` default size across Welcome, open-project,
  Library, Test Mode and AB Pilot Mode contexts. Long content wraps or scrolls within
  the content area, and full paths remain available through existing tooltips.
- The controller continues to own computer preferences and project recording saves.
  This layout change keeps the existing persistence contracts.

## Acceptance and verification

- [x] Implement the six category selections and matching right-side page headings.
- [x] Preserve every existing action, callback, eligibility state and save behavior.
- [x] Update registered Qt coverage for mouse and keyboard navigation, page-state
  preservation, minimum/default geometry, long content and error states in both themes.
- [x] Run `./scripts/verify.ps1 -Scope gui -Tier focused`.
- [x] Run the applicable repo precommit verification.
- [x] Record visible acceptance in the approved environment, including every category,
  keyboard focus, eligible Test/Pilot and Library controls, and developer-password state.
- [x] Update current GUI contracts and archive this plan after verification.

## Verification evidence

- GUI focused verification passed with 178 safe tests, changed-file Ruff and compilation.
- Repo precommit passed with 5,872 tests and 33 platform/permission skips, Windows and
  Darwin mypy, and repository/documentation audits.
- The targeted visible suite passed 99 cases across Settings, native theme preferences,
  recording Apply/Cancel/errors, Diagnostics, Workspace and Welcome bindings.
- Both verification routes passed again on a clean checkout after integrating the
  newer upstream Studio 2.8.2 changes before the push.
- All six categories were captured at `860x560` and `1000x680` in native Windows Light
  and Dark themes on a `1920x1080` display at 100% scaling. Labels and controls fit.
- The overflow regression forces a long Diagnostics page, sends real mouse-wheel
  events, reaches the last content and verifies fixed navigation, title and Close.
  Switching categories preserves that page's scroll position.
- Existing recording error tests now check the preserved original summary and modal
  error contract. The production recording save behavior carries through this redesign.
- Other native platforms and Windows scale factors were not executed for this change.

The user requested commit and push after verification.

Current layout and interaction requirements live in
[GUI workflow](../../GUI_WORKFLOW.md#settings-appearance-and-layout) and
[Frontend](../../FRONTEND.md).
