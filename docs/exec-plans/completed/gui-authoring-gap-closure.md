# GUI Authoring Gap Closure

Status: Completed

## Scope and acceptance

Close the four authoring gaps verified against the five saved projects in the
configured FPVS Studio Root. Saved experiments and their assets remain untouched.

1. Advanced Masking Settings exposes optional mask/catch event codes, including
   existing 56/57 values. Apply validates and saves a draft; Cancel preserves it.
2. Manual creation offers Cognitive Load FPVS through the existing category and
   scaffold service. Existing category immutability and unsupported choices remain.
3. A session pool containing one condition permits repeated presentations, including
   generated/saved four-occurrence orders. Multi-condition separation rules remain.
4. Timing & Display exposes Oddball every for ordinary image and word experiments,
   with persisted edits and no modality-switch workaround. Native AB stays unchanged.

## Implementation boundaries

Reuse core models, factories and ordering ownership. Add no project schema, trigger
transport, presentation engine or scientific protocol changes. Missing Katie Test
source folders and the empty Katie project require user assets/design, not new GUI
features. General custom-task editors already support the audited memory workflow.

## Verification

- Focused core/GUI regressions cover authoring, serialization and ordering contracts.
- Registered visible Qt checks cover minimum/default geometry, Apply/Cancel and
  recovery. User approval for isolated visible GUI checks carries from this session.
- Inspect changed screens in both themes at documented sizes, including Setup at
  1120x820. Never launch real experiments or use offscreen Qt.
- Run repo precommit in a clean QA checkout to preserve user-owned untracked files.
  Record exclusions and platform skips accurately.
- Refresh canonical workflow docs, archive this plan, then commit/push master.

## Progress

- Audit baseline: focused safe GUI checks passed (136 tests); original project
  hashes unchanged. Implementation is split across independent owners.
- Implemented all four changes without schema or runtime-engine edits. Masking marker
  controls explicitly update matching variant SOAs/catches in one staged draft,
  avoiding an inconsistent intermediate save.
- Compiler focused checks passed (739 tests). Real saved metadata compiled read-only:
  Demo four runs, Cognitive Load six and Masking thirty, with distinct run IDs.
- Registered visible Qt checks passed for creation, Timing, order, display and Masking
  (289 distinct cases, including updated Fixed/New seed preservation expectations).
- Native metadata-copy inspection passed in both themes: creation at 760x500, Setup
  at 1120x820 and Masking at 1100x720. Saved 56/57 markers and image cadence four are
  visible, with no clipping on changed surfaces. All five original project hashes
  match the audit baseline. Evidence: `build/gui-gap-closure/` and
  `build/gui-gap-saved-compilation.json`.
- Clean-checkout precommit passed: Ruff, compilation, full-source mypy, repository
  audits and 4,399 tests plus 24 subtests. Thirteen Windows symlink tests skipped for
  unavailable privileges. The pre-existing long-running
  `test_1500_acknowledged_sessions_retire_exact_history_and_keep_latest` was explicitly
  deselected, as in the baseline; it is not verified by this task.
- Final layout-only Masking row adjustment passed the visible suite and targeted
  static checks, with final source parity checked against the QA copy.
- Pytest's Windows startup logged the previously observed `0x8001010d` diagnostic;
  visible suites still completed with exit code zero. The separate native two-theme
  inspection completed without errors. Physical presentation/EEG checks remain
  outside this authoring-only change.
