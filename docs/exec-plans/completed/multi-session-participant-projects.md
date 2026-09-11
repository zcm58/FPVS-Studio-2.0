# Multi-Session Participant Projects

Status: Completed

## Authorized Workflow

The user requested a new branch, safe repeat visits under the same participant ID,
explicit first/second session labels, and repeat-session setup for the Cognitive
Decline project. Work is on `codex/multi-session-projects`. Preserve the unrelated
updater-plan edit, untracked output, and all existing participant data.

## Design And Boundaries

- Add `ProjectSettings.allow_repeated_participant_sessions`, default false, with a
  Setup > Project control. Existing projects remain readable with the default.
- Reject reused participant IDs in single-session projects; enabling repeat sessions
  permits an explicit confirmation of the next numbered participant session.
- Runtime previews and atomically reserves participant session numbers from full,
  compact, aborted, partial, and historical run storage. Preserve PID text/leading
  zeros. Reserve only after preflight and before playback; never recycle a crashed
  launch's reservation or overwrite earlier output.
- Keep visit identity in execution metadata and exports, outside compiled timing,
  `RunSpec`, and `SessionPlan`. Preserve existing session randomization and scoring.
- Give each new detailed session its own `runs/P<PID>_session<NN>/` folder. Compact
  mode reserves identity under `logs/` and does not create `runs/`.
- Preserve legacy folders/files in place; assign historical visit numbers in reporting
  without rewriting raw recordings. Append fields compatibly to reporting formats.
- Project configuration handoff preserves the repeat-session setting. GUI history
  lookup stays on a worker, and runtime checks the confirmed number again at launch.
- Enable the actual Cognitive Decline project after validating the implementation,
  with a byte-for-byte backup and a metadata-only settings edit. Birth Control is
  unchanged; it can use the same new setting.

## Verification

- Baseline runtime focused: 230 passed.
- Add model/config compatibility, repeat-launch full/compact, collision, old-history,
  aborted/partial-session, reporting and task-checkpoint regression coverage.
- Add registered GUI state and no-clipping coverage for Setup at `1120x820` and
  repeat-session launch confirmation. Do not run Qt locally without an approved
  visible environment; document manual acceptance.
- Run runtime/core/project-io/GUI focused checks as implicated and repo precommit.
- Verify Cognitive Decline loads with the enabled setting and that other metadata and
  existing run/log bytes are preserved, apart from explicitly regenerated summaries.

## Progress

- Located the configured Cognitive Decline project on the external Studio root.
  Existing data includes both bare legacy and `P`-prefixed session folders, compact
  indexes, and already repeated participant IDs. No participant responses inspected.
- Sequential full runs already suffix existing output folders, but launch copy offers
  overwrite, no visit number exists, allocation is not atomic, and compact launches
  of a reused compiled plan can merge reporting/checkpoint identity.
- Implemented project authoring, config handoff, shared worker-backed Home/Run launch
  checks, numbered runtime exports, per-visit electrode snapshots, and compatible
  reporting. Closing/switching projects is blocked while launch checks/playback run.
- Native project reporting locks serialize header migration, appends, and summary
  writes. Malformed CSV headers/cells fail without rewriting data. Legacy compact
  executions of the same plan remain separate using original export timestamps.

## Final Verification And Project Setup

- Runtime focused: 269 passed, one Windows directory-symlink privilege skip.
- Core focused: 365 passed, one Windows directory-symlink privilege skip.
- Project I/O focused: 116 passed. GUI focused, Ruff, compilation, and config validation
  passed; no local Qt execution was performed.
- Final repo precommit: 1,410 passed, six Windows symlink-permission skips; Ruff,
  compilation, mypy over 153 source files, and repository/documentation audits passed.
- Enabled `allow_repeated_participant_sessions` in the actual Cognitive Decline
  `project.json` using a metadata-only edit after staging validation. Regenerated its
  CSV/XLSX participant summaries with the added Session Number column; all prior
  summary values are unchanged. Checksums confirm all other 248 original run/history
  files are unchanged. Birth Control remains unchanged.
- Preserved original project/summary files and the original-file checksum inventory
  under the project's `backups/before-multi-session-20260911T222928Z/` directory.
- Automatic approval review blocked deletion of the agent-created temporary validation
  folder (`fpvs-multi-session-before-8773wocj` in the user's local Temp directory).
  That temporary copy remains; the unrelated user-owned `output/` was untouched.
- This setup requires the updated source branch. An older installed application
  rejects the new project setting; no installed application was replaced or launched.
- Visible/manual acceptance remains the path in `docs/GUI_WORKFLOW.md`: Setup at
  `1120x820`, returning-participant confirmation at `600x260`, and Home/Run fresh,
  repeated, cancelled, disabled, aborted, and compact session flows. Registered Qt
  coverage exists but was not executed without an approved visible environment.
