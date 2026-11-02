# Setup visual layout and hierarchy

Status: Completed

## Task and visual evidence

Improve all eight Setup pages using real rendered previews at 1120x820, keeping shared
stepper/navigation positions, scientific-tool styling and every setting/binding intact.
User explicitly requested visual peeks; this authorizes visible isolated synthetic Qt
review. No offscreen Qt and no real user project or participant runtime is involved.
Root inspected all eight before pages through Computer Use on a synthetic five-condition
image project. Project, Timing, Display/Session, Size, Fixation and Response had large
empty top margins from vertical centering. Timing showed only three condition rows in
a small fixed-height table. Image Size stretched tiny numeric values across 600px fields;
Review's shared grid rows padded small cards and left the final right cell empty.

## Design and acceptance

- All pages begin 24px below the shared body top, with bounded widths and stable nav.
- Project uses a 1040px workspace with Project details and Experiment setup columns.
- Conditions retains the list/editor/source layout, with natural-height details,
  left-aligned source hierarchy and useful room for word inputs.
- Timing expands its table into available height; five standard rows fit without an
  unnecessary inner scrollbar. Keep all draft and display/cadence bindings.
- Display/Session uses two softly framed sections with readable headings/padding.
- Size uses Stimulus size and Display calibration sections with bounded numeric fields,
  associated metrics/actions, and existing natural/masking/AB behavior.
- Fixation/Response use left-aligned section headings, top-aligned fields and proportionate
  controls; Response preview belongs beside configuration instead of a large full-width strip.
- Review uses independent natural-height columns so smaller tiles do not inherit the
  tallest tile's empty area. Keep summaries, edit links and blockers unchanged.
- Every surface fits minimum/default sizes in both themes, long values and relevant
  busy/error/disabled/draft states. Do not add redundant explanatory paragraphs.

## Verification

Update registered Qt geometry/text/binding coverage during implementation. Run focused
safe GUI checks, approved visible sizing tests with mocked dialogs/runtime, docs and
precommit checks. Reopen the synthetic preview for real after peeks at all eight steps;
record observed sizes/themes and any skipped states accurately. Preserve real-user data.

## Progress

All eight before/after pages were inspected through Computer Use using the actual
widgets, synthetic image sources and five realistic conditions at 1120x820. After
review covered both dark/light themes on the visible Windows desktop; no participant
runtime, real project, display-rate measurement or full-screen experiment was launched.
Timing's refresh/frequency/cadence controls now share one toolbar; its five rows fit.
Project, Display/Session and Size use coherent columns; Response keeps configuration
and preview side by side; Review no longer stretches small tiles to the tallest row.

Registered coverage exercises bounds, full labels, natural heights, long names,
image/word modes, unresolved/invalid timing, fixed/ranged/hidden fixation, native AB
and masking. The first visible run found stale navigation/layout assertions and an
invalid hidden-cross fixture; those were corrected without product changes. Native
AB timing keeps its compact natural height because it has no visible condition table.

## Final verification

- `./scripts/verify.ps1 -Scope gui -Tier focused -Workers 4`: 163 passed.
- `./scripts/verify.ps1 -Scope docs -Tier focused`: 13 passed and plan hygiene clean.
- Approved visible `gui/full` runs, with `FPVS_ALLOW_QT_TESTS=1` and focused
  `PYTEST_ADDOPTS=-k` filters, passed 57 cases in fresh per-module processes:
  Timing:20, Fixation/Response:6, Conditions:11, Display/Size:6, Project:2, Review:2,
  Shell:2 and native AB:8. The selected nodes cover the contracts listed above;
  this is scoped coverage, not a complete GUI-suite run.
- Combined visible batches timed out during repeated global palette changes.
  Geometry-only native AB/theme-label tests now apply a local window palette and
  the canonical stylesheet; isolated groups pass. Production theme ownership is
  unchanged, and no general theme-performance claim is made.
- `./scripts/verify.ps1 -Scope repo -Tier precommit -Workers 4`: Ruff, compilation,
  mypy (261 source files) and audits passed; 4808 tests passed, 13 Windows-symlink
  skips, one unrelated transient `WinError 5` while renaming a bundle folder in
  `test_library_origin.py`. Its complete isolated rerun passed 25 with 2 symlink skips.
  Final mypy, changed-file Ruff/compilation and whitespace checks also passed.
- Visible Conditions tests retain exact 1120x820 and 1120x960 sizes. The larger
  1448x1086 request is capped to the actual Windows work area (1061px client height
  on this display), with full child/text/selected-row checks. No additional DPI
  scaling, packaged application or physical presentation timing was qualified.
- Two final screenshots are retained outside the repository in this chat's
  visualization workspace. The synthetic preview is closed. Automatic approval
  review blocked recursive cleanup of its task-owned temporary directory with
  `blocked by policy`; those preview files were retained, and the repository's
  temporary preview-path marker was removed.

## Change inventory and preserved behavior

- `gui/setup_wizard_page.py`: shared surface positioning/widths, Timing toolbar,
  Display/Session framing and independent Review columns.
- `gui/project_overview_page.py`, `condition_setup_step.py`: metadata/setup columns,
  compact condition details and left-aligned source metrics.
- `gui/condition_timing_table.py`: optional refresh toolbar group and expanding table.
- `gui/runtime_settings_page.py`: separate stimulus geometry/calibration cards.
- `gui/fixation_settings_page.py`: section hierarchy, bounded fields and adjacent preview.
- Registered GUI modules: `test_setup_wizard_shell.py`, `test_setup_project_details.py`,
  `test_setup_conditions.py`, `test_setup_experiment_display.py`, `test_setup_review.py`,
  `test_condition_timing_table.py`, `test_conditions_session_fixation.py` and
  `test_attentional_blink_stream_designer.py`. All remain in the existing registry.
- `docs/GUI_WORKFLOW.md`, `docs/FRONTEND.md`, `gui/AGENTS.md` and plan index:
  current top-anchor, widths and column contracts.

Paths above are relative to `src/fpvs_studio/` for production GUI files and
`tests/gui/` for tests. This plan and `docs/PLANS.md` track the work. Existing
editors, controller/document bindings, draft handling,
navigation, save actions and persisted formats are preserved. Tests stub dialogs and
runtime calls and use temporary projects. Manual smoke path: open Edit Setup at the
minimum window size, visit all eight steps in both themes, inspect long values and
the count-mode/draft states, and confirm bottom navigation remains available.
