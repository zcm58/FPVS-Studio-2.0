# Remove Create Control Condition workflow

Status: Completed

## Requested outcome and scope

Authorized on 2026-11-02: remove the entire dedicated `Create Control Condition`
workflow, including its Conditions action, modal dialog, handlers and document
convenience API after a caller audit. The user requested commit/push when finished.

Conditions retains manual Add/Duplicate/edit and normal image/word source authoring.
Existing saved conditions remain ordinary condition records with the same variants,
runtime transforms, timing, IDs and trigger codes. No saved-data migration, asset
removal, project/config/bundle schema or compiled/runtime format change is authorized.
General preprocessing variants and presentation transforms stay supported.

## Owners and work

- [x] GUI owner removes the action/button, imports/handlers and dedicated dialog,
  including obsolete registered dialog tests/registry entries where appropriate.
- [x] Document owner audits callers before removing the convenience API and private
  helpers used only by that workflow. Shared condition authoring and asset helpers stay.
- [x] Docs owner removes live workflow instructions from GUI workflow/Frontend and
  the published Prepare Stimuli guide, preserving manual image-variant preparation;
  audits architecture, agent guides/task routing and skills for stale ownership entries.
  Historical completed plans remain unchanged; no stale entries were found in those
  architecture/guide/routing sources.
- [x] Repair the verification driver's changed-file selection to exclude deleted paths
  from Ruff/compilation, with a real temporary-Git regression and `-CheckConfig`.
  This is required to verify this deletion; no broader harness refactor is in scope.
- [x] Update meaningful regression coverage for removed entry points, preserved manual
  authoring and saved-condition compatibility; complete applicable focused/precommit checks.

## Observable acceptance

- Conditions has no dedicated control-condition action or modal; the deleted document
  API has no remaining production callers. No UI gap or clipping appears at `1120x820`.
- Manual Add/Duplicate/edit still works for ordinary conditions; source import,
  normalization, general variants and image/word runtime transforms retain their flows.
- Existing transformed/derived-variant conditions survive save/reopen, portable
  interchange and compilation with scientific settings and asset bytes unchanged.
  Removal does not clean or rewrite user conditions, source pools or manifests.
- Tests cover actual retained behavior rather than replacing removed API calls with a
  second convenience workflow. Core/runtime consume the same persisted/compiled contracts.

## Verification and completion

Run selected GUI/document/preprocessing checks and repo precommit. Registered visible
Qt checks use only the existing approved visible environment and synthetic data;
ordinary checks must not launch experiments, access hardware or mutate real projects.
[GUI workflow](../../GUI_WORKFLOW.md), [Frontend](../../FRONTEND.md) and the published
Prepare Stimuli guide now describe the retained manual authoring workflow. The dedicated
workflow is removed, relevant verification passed and this plan is archived. Root owns
commit/push. Historical completed plans remain intact.

Dedicated GUI/dialog and document convenience-API removal is implemented. No production
references to the deleted route/API or public package exports remain. The caller audit
found no external API, dynamic-registry or package-export consumers. Shared
normalization, import/progress and image materialization APIs remain in place. Live
documentation no longer instructs users to create conditions through the dedicated workflow; manual
condition authoring and separately prepared image variants remain documented.

Documentation hygiene and all 13 focused docs tests passed with the complete canonical
and published-guide updates. A tracked `git grep` audit included hidden `.agents/`
skills, architecture, root/package guides, routing and `docs-site`; remaining live
matches are the intentional removal plan/index, while workflow instructions remain
only in historical completed plans.

Final verification recorded on 2026-11-02 (focused counts overlap the full suite):

- Normal repo precommit passed: 4,994 tests and 14 existing Windows symlink skips.
  Full-source mypy passed for 266 files; Ruff, compilation and repository audits passed.
- GUI focused route passed all 164 safe tests; 17 safe Attentional-Blink cases also passed.
- 27 visible Qt cases passed: 14 document/preview/transform cases (all 11 document
  cases plus three preview/presentation-transform cases), and 13 ordinary/masking
  cases at native Light/Dark `1120x820`. The latter cover four ordinary image/word
  lifecycle cases, three saved derived-variant edit/save/reopen cases and six masking cases.
- Parent inspected ordinary Dark and masking Dark captures in the task-owned
  `Temp/fpvs-condition-actions-audit-4820ebbc0fe840a4b8047a972d90f436/` directory.
  Masking verification exposed a narrow catch-summary layout; a local horizontal
  Expanding policy retains height-for-width, and queued-layout waits verify full
  summary text at the observed 34/51 px heights. No new workflow was introduced.
- The first precommit attempt stopped before tests because changed-file selection
  supplied deleted `control_condition_dialog.py` to Ruff (E902), even after staging.
  A minimal deletion filter repaired that verification path. Its real temporary-Git
  regression reproduced the failure before the fix; 28 harness tests passed with one
  existing Windows symlink skip, and all 15 scope `-CheckConfig` checks passed.
- Final documentation hygiene and all 13 focused docs tests passed after archiving.

Persisted project/config/bundle and compiled/runtime formats are unchanged. Existing
conditions, variants, transforms and assets remain supported; no migration, cleanup
or asset deletion occurred. Checks used synthetic data and no real user project or
hardware. The capture/test evidence does not claim physical hardware, Mac GUI or
high-DPI acceptance; those are not additional gates for this scoped deletion.
