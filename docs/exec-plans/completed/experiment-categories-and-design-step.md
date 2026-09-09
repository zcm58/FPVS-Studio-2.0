# Experiment Categories and Design Step

Status: Completed

## Accepted scope

Experiment category is chosen on a dedicated first screen with no other question.
The available categories are FPVS-Oddball and Attentional-Blink; FPVS is a disabled
base-only Coming soon option. Category is locked after creation. Changing category
requires a new experiment. A dedicated Design step reuses the visual designer across
supported categories, with T1/ISI/T2 controls available only for Attentional-Blink.
All existing ordinary behavior belongs to FPVS-Oddball. Existing AB defaults and
frame-based playback remain intact.

Old projects without a category are classified as Attentional-Blink if any condition
has AB timing, otherwise FPVS-Oddball. Mixed legacy projects require explicit
separation; never silently reinterpret an oddball condition as an AB condition or
discard its source data. A category conflict must prevent saving a valid mixed
experiment or launching one while keeping the project recoverable in Setup.

## Implementation boundaries

- Core owns the category enum, persisted immutable choice, legacy classification,
  homogeneous-category checks and project/config/template propagation.
- GUI owns the category-first creation flow, locked category display, dedicated
  Design step and category-specific authoring. Reuse native widgets and existing
  document bindings. Preserve long Windows image path handling.
- Preserve engine/runtime boundaries and existing frame scheduling. Category
  validation must protect direct compilation as well as GUI launch.
- Preserve unrelated work on this experimental branch and real user project files.

## Steps and verification

1. Add project rules and migration -> verify persistence round trips, legacy
   classification, conflicting conditions and launch/config/template boundaries.
2. Build category-first creation and Design navigation -> verify creation/cancel,
   locking, placeholder behavior and conditional controls.
3. Integrate designer and condition authoring -> verify no oddball/AB mixing,
   separate image pools, selection/saving, preview and legacy repair behavior.
4. Verify shared contracts and the visible Setup workflow at 1120x720 in light and
   dark themes. User approval for safe visible Qt checks persists from this session.
   No physical experiment or hardware-trigger checks are part of GUI verification.
5. Update current architecture/workflow guidance and archive this plan when complete.

## Progress

- Category-first creation, frozen project category, schema 1.4 migration, compatible
  template choices and whole-project save/compile guards are implemented.
- Conditions and Design are separate steps in the nine-step wizard. ISI is AB-only;
  ordinary image/word modes remain FPVS-Oddball. Pending design edits apply before
  navigation/save, with explicit invalid-draft discard and safe image-worker teardown.
- Legacy separation copies source/task assets into a collision-safe sibling, retains
  a recovery snapshot, and saves the AB original last. Missing populated sources,
  missing referenced manifest assets and foreign manifests fail before file creation.
  Copy/replace rollback and empty-draft behavior are covered. Dormant T2 assignments
  in otherwise ordinary legacy projects have an explicit cleanup action preserving files.
- Core focused: 271 passed, one unavailable Windows symlink test skipped. Project I/O
  focused: 79 passed. Final separation regressions: 13 passed. Safe suite: 1192 passed,
  five Windows symlink skips; the subsequent manifest-identity guard passed its targeted
  separation suite. Changed-file Ruff/compilation, repository audits, verification
  configuration, docs hygiene and targeted source mypy pass.
- Repo precommit stops at the pre-existing `gui/controller.py:373` return-type error
  (`object` returned where `str` is declared). Remaining audits and safe tests were
  run independently. This unrelated error has not been changed by this work.
- Visible category/designer/setup checks pass, including all 20 dedicated Design
  cases after deferring embedded thumbnail decoding until the editor is visible.
  Saving outside Design no longer starts hidden image jobs. Both Review regressions
  and the positive GUI separation/save handoff pass; the shared launch/abort batch
  completes normally after this fix.
- Full `1120x720` populated AB and Oddball pages plus the `800x430` category chooser
  were captured and inspected in light/dark themes. All default cycle cards are visible.
  Captures are retained under `build/categories-visible-20260908-233032/`.
- The broader shared-GUI pass found four unrelated existing checks: a reference to
  missing `_fixation_review_line`, old disabled-fixation defaults, Welcome column-count
  expectations, and a Settings checkbox click expectation. Their owners/defaults were
  compared with HEAD; no unrelated behavior was changed to satisfy these tests.
  Native clipboard checks report Windows COM `0x800401d0`; the remaining callback
  verification uses an isolated test clipboard and does not certify OS clipboard access.
- Final full Timing plus Design suites: 29 passed. The Timing check now waits for
  queued layout completion before checking parent bounds and complete wrapped text;
  no production geometry change was required. The full settled Timing screenshot
  was inspected at `1120x720`. Four copy-path callbacks pass with the isolated
  clipboard in `build/category_clipboard_check.py`; native clipboard access remains
  unverified in this session. The positive legacy-separation GUI path also passed.
- The requested category/design workflow is complete on the experimental branch.
  No physical PsychoPy presentation or hardware-trigger run was performed. Wider
  pre-existing GUI/type-check issues above prevent claiming a clean full-repository gate.
