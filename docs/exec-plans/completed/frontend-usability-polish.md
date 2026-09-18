# Frontend usability and responsiveness

Status: Completed

## Scope and authorization

The user approved fixing the four frontend priorities and committing/pushing the
result: Attentional Blink clipping, authoring responsiveness, clear loading and
save/validation feedback, and consistent layouts in both themes. Visible Qt checks
are authorized using synthetic projects and isolated settings without playback or
EEG hardware. Work starts from the accepted backend and Edit Setup fixes.

## Boundaries

Keep project formats, compilation, runtime, engines, and trigger sending unchanged.
Reuse the GUI's shared components and worker/lifecycle services. Preserve the eight
Setup steps and the existing save/apply/navigation contracts. New save feedback may
use existing window chrome but must not crowd or reduce the guided content area.
Keep existing active Library, feedback-service, and updater plans separate.

## Work and acceptance

1. Reproduce AB clipping, correct measured row/header sizing, and verify all eight
   steps at 1120x820 in both themes, with fixation shown/hidden and validation errors.
2. Trace project opening, setup navigation and image selection. Remove demonstrated
   redundant work or move blocking file work to existing Qt workers. Test delayed,
   failed and superseded work without changing project data or touching widgets from
   workers.
3. Make loading and save state visible and truthful. Retain edits on failures and
   preserve invalid-draft navigation guards. Test saved/dirty/error transitions.
4. Review main authoring surfaces, long content, supported minimum/default sizes,
   and light/dark themes. Fix reproduced clipping or inconsistent controls. Keep
   intentional elision accessible through full-value tooltips/copy affordances.

## Verification

Run the GUI focused route, registered visible GUI tests for the affected paths,
manual screenshot inspection, and repo precommit. Use real workers with blocked
synthetic callbacks for responsiveness checks; stub file dialogs and runtime calls.
Report exact coverage and remaining limitations. Remove temporary diagnostic files,
complete this record, commit, push, and verify the remote commit and clean worktree.

## Progress

- Baseline GUI focused route passes (7 non-Qt tests).
- Reproduced AB default-window clipping in the existing geometry test.
- AB clipping was caused by a minimum table height smaller than its styled header
  plus three rows. Eight original layout variants now pass without changing timing.
- Project reads now run in existing app-owned jobs, with cancel/failure/supersession
  coverage. GUI documents are created on the GUI thread after successful completion.
- A real-worker test demonstrated seven thumbnail decodes during three unchanged
  refresh/navigation cycles; per-editor reuse removes the six redundant decodes.
  Fresh source intake still reloads previews, and failed previews retry cleanly.
- Added Save/Ctrl+S and truthful save feedback, including focused name and pending
  text edits. Added loading copy in existing image-card count areas.
- Reproduced/fixed clipped long Home titles and a launch-button overlap with wrapped
  descriptions. Full names remain available through accessible text/tooltips.
- Broader visible checks exposed older test assumptions: obsolete AB image-pair
  profiles/two-second cycles, old review methods, obsolete persistence patch points,
  mojibake, and fixed button-grid expectations. Updated tests to current contracts;
  production backend/experiment behavior is unchanged.
- Screenshot review found a clipped menu-corner save badge after its text grew.
  Refreshing the corner-widget geometry fixes all four states; light/dark tests now
  assert both the text width and the menu boundary.
- Conditions alignment checks now wait for the queued layout pass. Modality tests
  explicitly show Setup, and normalization checks use the existing unique source
  paths while asserting that the uniform oddball set is unchanged.

## Acceptance results

- Final combined visible suite: 343 passed across 14 affected GUI modules, covering
  authoring, Home, Settings, project management and creation. Two collection warnings
  concern imported application classes whose names begin with Test; no tests failed.
- Repo precommit: 1,952 passed, eight Windows symlink permission skips. Ruff,
  compilation, repo/docs audits and mypy passed. After the final badge fix, GUI
  focused checks and mypy were repeated successfully (193 source files).
- Visible screenshot review: Home plus all eight Setup pages for native Attentional
  Blink and a six-condition Oddball project, in both themes (36 surfaces). Home fits
  1120x720 and Setup fits 1120x820. Rechecked the corrected badge and long Home names
  in both themes. Registered geometry tests also cover larger Conditions windows,
  long text, validation errors, and fixation shown/hidden.
- Confirmed no production changes in core, preprocessing, runtime, engines or
  triggers relative to the accepted backend/Edit Setup commits. No physical EEG,
  PsychoPy playback, display-timing checks or installer build were performed.
- Delivery branch: `codex/frontend-usability-polish`. Temporary diagnostic scripts
  are removed. Automatic approval review blocked screenshot deletion, so the two
  ignored `build/debug/frontend-visual-*` folders remain local. Only source,
  registered tests and documentation are included in the change.
