# Settings hierarchy and theme preference

Status: Completed

## Requested outcome

Authorized on 2026-11-02: simplify Settings into a clear header/section/control
hierarchy without nested cards, and offer an exclusive `Light` / `Dark` / `Auto`
button toggle. Changes apply immediately and remain preferences for this computer.
`Auto` follows the operating system's color scheme, including changes while Studio
is open. The user requested commit/push after implementation and verification.

The primary task is to change a preference without navigating decorative containers.
Keep the existing General, Advanced, Recording and Diagnostics routes, useful status
and error information, callbacks and immediate-save behavior. Existing reminder,
test/pilot, recording, Library, developer and diagnostics eligibility stays unchanged.

## Scope and owners

- Settings UI uses existing PySide6/shared components and clear section titles;
  remove nested card framing instead of adding explanatory paragraphs.
- Theme infrastructure owns the effective application palette and OS-follow behavior;
  the controller owns persisted per-computer preference composition. Reuse existing
  palette observation so open windows/dialogs refresh consistently.
- Preference values stay in the existing app-preference service; no project, config,
  bundle or compiled-contract schema changes. UI theme selection must not edit the
  experiment's authored display/background settings or saved scientific parameters.
- Add focused registered GUI coverage. Do not introduce another GUI framework,
  hardware activity, network/service changes or a separate Mac/Windows UI.
- Canonical interaction/sizing guidance stays in [GUI workflow](../../GUI_WORKFLOW.md)
  and [Frontend](../../FRONTEND.md); update them to the final implementation.

## Implementation and verification

- [x] Implement flat Settings sections, aligned tab insets and headings without nested
  cards or outer tab-pane border, preserving existing control identities/actions.
- [x] Implement mutually exclusive `Light`, `Dark`, `Auto` buttons, selected state,
  inline callback-failure feedback and selector rollback.
- [x] Verify immediate application and `appearance/theme_mode` persistence across
  close/reopen and controller/app restart without modifying project files.
- [x] Implement native Auto/Unknown delegation and notification-event coverage for
  OS-follow behavior. Explicit Light/Dark retain their selection; returning to Auto
  uses the current native choice. No host-global OS setting was changed for testing.
- [x] Refresh already-open Settings, Home/Setup and representative dialogs through the
  shared theme mechanism, with legible headings, values, validation, selection and focus.
- [x] Update canonical GUI/Frontend layout and appearance contracts.
- [x] Pass registered Settings layout/state coverage and visible sizing/contrast review
  at the recorded sizes below; report palette tests and actual captures separately.
- [x] Finish theme persistence/native tests, final focused checks and repo precommit.
  Report OS-follow delegation separately from changing a host OS setting.

## Observable acceptance

Inspect every Settings tab in Light, Dark and Auto at the documented minimum/default
sizes, with ordinary and longest realistic labels/paths, unavailable actions and
relevant errors. No required control or text clips or needs window enlargement.
Current size budgets are `700x560` normally, `700x650` with Test Mode and `700x720`
with AB Pilot Mode; Library access adds 44 px (`700x604`, `700x694`, `700x764`). Keep
these budgets unless a justified implementation change is documented and tested.

Confirm a flat, readable hierarchy, no nested cards, keyboard-accessible theme
selection and correct selected state. Change all three modes from Welcome and an
open project, reopen Settings/restart the controller, then verify the saved choice.
Simulate OS changes for deterministic Auto coverage; physical/native acceptance must
state the actual OS/theme observation rather than treating a mocked signal as proof.
Check project bytes/settings remain unchanged when only the app theme changes.

Visible Qt checks require the existing approved visible environment, synthetic data
and fake native/service dependencies; never use local offscreen Qt or launch an
experiment. Root owns that review and commit/push. Implementation, applicable
verification and canonical documentation are complete with the limits recorded below.

## Evidence

Settings UI structure and canonical docs are implemented. General starts with an
inline Appearance selector; other tabs use explicit section headings, with shared
insets/gaps and retained size budgets. The computer preference is
`appearance/theme_mode`, with missing/invalid values resolving to Auto. Error feedback
rolls back the selector instead of presenting the failed choice as saved.

Auto delegates the native scheme to `QStyleHints` using the `Unknown` override;
existing palette observers refresh open widgets. Validation simulates theme
notifications without changing the host's global OS setting.

Recorded on 2026-11-02:

- 26 registered Settings tests passed: all four tabs at `700x560`, `700x650` and
  `700x764`, in both palettes, including failure/keyboard/retry states. These dialog
  cases use equal minimum/default sizes.
- Parent inspected all 10 real Qt captures: all four tabs in Light/Dark at `700x694`,
  plus General at `700x560`, DPR 1.0 (100%). No nested cards, clipping or poor contrast
  were observed. Native scheme/application palette switching produced Light `#f3f3f3`
  and Dark `#1e1e1e`; this was not a change to the host's global OS setting.
- Captures are retained in the task-owned temporary directory
  `C:/Users/zcm58/AppData/Local/Temp/fpvs-settings-captures-7f1eb18a959642bdae7e4f95f424dc50/`.
- Documentation hygiene and all 13 focused docs tests passed with the native
  delegation and visual-evidence updates.

Final verification:

- Repo precommit passed: 4,979 tests, with 14 Windows symlink checks skipped.
- Full-source mypy passed for 267 files; Ruff, compilation and repository audits passed.
- GUI focused route passed all 164 safe tests.
- Theme verification passed 60 non-Qt preference/legacy/registry tests, including 14
  new preference cases, plus two fresh visible native Qt tests covering palette
  application, live Welcome refresh, persistence and Settings binding.
- The 26 visible Settings cases and 10 inspected captures above passed. Final docs
  hygiene and all 13 focused documentation tests passed after archiving.

## Verification limits

An optional broader Welcome module contains 94 cases. It displayed 72 passing progress
markers (about 76%) before blocking; parent interrupted only that task's pytest process.
The suspected case passed alone in 0.42 s, and all nine neighboring Settings actions
passed in a bounded 1.61 s run: run export, reminder, ticker, four Windows/Linux
source/frozen variants, migration and root action. No production issue or corrective
change was identified. This remains an unexplained test-order limitation; the full
Welcome module is not recorded as passing.

Native visible evidence is Windows at DPR 1.0. Verification used native palettes and
notification events; it did not change the host-global OS scheme or exercise actual
OS-wide transitions, high-DPI scaling or a Mac GUI. These unperformed checks are not
implied by the completed implementation or registered test results.
