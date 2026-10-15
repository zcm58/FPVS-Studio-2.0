# GUI responsiveness during authoring and project discovery

Status: Completed

Implemented and verified on `feature/ui-responsiveness` in `3461bc7`, merged into
`master`. Visible GUI acceptance remains documented below.

## User outcome and scope

The user requested investigation and implementation of UI responsiveness improvements.
Work on `feature/ui-responsiveness`, starting from clean `master` at `851bb73`.
Keep the Home/eight-step Setup workflow, appearance, current drafts and experiment
contracts unchanged. Avoid speculative caching or a new worker lifecycle.

## Investigation evidence

- Hidden Home refreshes on project changes and performs project validation.
  Instantiated Run also refreshes while hidden and can validate twice per refresh.
  Avoid unnecessary hidden-page work; refresh current state when the page is shown.
- The hidden compatibility Assets page also rebuilds its table and validates on
  edits. Together these hidden pages can perform four redundant validation passes.
- Attentional-Blink draft previews repeatedly calculate descriptions for all
  conditions within a single update, then calculate the selected condition again.
  Reuse calculations within that update without retaining stale cross-edit data.
- Manage Projects loads project discovery and JSON metadata synchronously before
  the dialog is visible. Move read-only loading to the existing owned worker path,
  preserving sorting, selection, rename/delete behavior and safe close handling.
- Image thumbnails already decode in a worker with metadata-key reuse; shared Setup
  styling already avoids identical restyling. Preserve those existing optimizations.
- The retained Find Action dialog rebuilds its full result tree for every QAction
  change while closed. Skip those notifications and refresh once when reopened.

These are source-observed costs, not measured end-to-end latency claims.

## Acceptance and verification

- No extra hidden Home/Run validation for ordinary edits; showing them presents
  fresh readiness, dirty state and summaries. Existing launch gates remain authoritative.
- Each AB draft update computes a condition description at most once for its
  validation/summary/table/preview uses, preserving errors and derived values.
- Slow project discovery leaves the GUI event loop and Cancel/Close responsive;
  failures and stale results never replace the wrong list or touch destroyed widgets.
- Preserve documented sizes, including the eight-step `1120x820` wizard and the
  `860x520` Manage Projects dialog. No additional required controls or scrolling.
- Add or update registered Qt regressions with deterministic call counts and fake
  workers/delays. No local Qt execution without an approved safe visible session.
- Run GUI/docs focused checks and repo precommit. Where useful, measure pure backend
  calculations without importing Qt; distinguish operation counts from elapsed UI time.

## Progress

- [x] Confirm clean branch and GUI baseline (17 safe tests pass).
- [x] Inspect refresh fanout, preview work and synchronous project discovery.
- [x] Implement scoped changes and registered regression coverage.
- [x] Review changes, verify safe checks and document remaining visible acceptance.

## Implemented behavior

- Home/Assets/Run keep one pending refresh while hidden and use fresh document state
  when shown. Explicit refresh and visible updates stay synchronous. Run's display
  editor retains its independent settings subscription; launch settings remain current.
- AB preview calculations drop from `2n + 1` to `n` descriptions for `n` valid
  conditions per edit (seven to three in the default study). Invalid calculations
  are reused only within that update; error priority and recovery remain unchanged.
  Unchanged digit cells retain their existing items.
- Manage Projects shows Loading before its app-owned worker discovers folders and
  reads metadata. Paths are snapshotted on the GUI thread, with cancellation checks
  during discovery and between files. Close/destroy/supersession/shutdown guards
  discard stale results. Failed reads offer inline retry, and rename/delete rescan
  asynchronously with rename selection restored.
- Find Action skips closed-dialog updates, rebuilds once on reopening, and preserves
  immediate enabled/visible/text/shortcut changes while open.
- Added 26 registered GUI regression cases, including loading/error layouts in both
  themes at `860x520`, blocked-reader event-loop checks, hidden-page freshness and
  AB invalid-input recovery. Existing rename/delete assertions await the scan.

## Evidence and verification

- GUI focused: 17 safe tests passed, changed-file Ruff and compilation passed.
- Docs focused: hygiene and 10 documentation tests passed.
- Independent source review found no blocking worker lifetime, stale-result,
  launch-setting, action-dispatch or validation-order regression.
- Pure-core AB benchmark on Python 3.10.11, with no PySide6 imported: 11 alternating
  batches of 5,000 updates after 1,000 warmups, SOAs 100/300/500 ms, draft rate 20 Hz,
  selecting the first condition. Normal five-second bursts: median description work
  15.689 to 8.017 microseconds/update. Repeated-target nine-second bursts (six targets,
  10 Hz saved rate, ten-slot interval, first T2 omitted): 44.026 to 20.082 microseconds.
  Outputs matched. This includes temporary dictionary reuse but excludes widget work,
  document lookups, Pydantic checks and painting; it is not an overall GUI speed claim.
- Repo precommit passed: 3,043 safe tests passed, 11 Windows symlink-permission
  skips in 274.30 seconds. Mypy passed across 236 source files; Ruff, compilation,
  harness audits and documentation hygiene also passed.

## Remaining visible acceptance and limits

Qt tests and rendered/manual GUI checks were not run: local Qt requires a user-approved
safe visible environment. The smoke path is recorded in
`docs/GUI_WORKFLOW.md#authoring-and-project-discovery-responsiveness`; no offscreen Qt
was used. End-to-end latency has not been measured. Root setup/template normalization
and rename/delete writes retain their existing synchronous behavior. Current scan
cancellation is cooperative between filesystem calls; it cannot interrupt an OS read.
