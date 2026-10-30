# Conditions Authoring Consolidation

Status: Completed

## Workflow and boundaries

Select a condition, choose its Base/Oddball image folders and optionally edit its
participant instructions in a Save/Cancel dialog. Default and short condition names
must not block Setup. Conditions advances directly to Timing & Session, with the
existing image-readiness and normalization handoff. The guided flow has seven steps
at `1120x820`; native AB editor work is deferred, preserving saved AB settings.

Reuse the existing compact source cards, canonical fresh-source import/document
adoption services and app-owned worker lifecycle. Keep project formats, compilation,
runtime timing, modifiers, word lists, and source pixels unchanged.

## Implementation and acceptance

1. Remove descriptive-name checks and messages. Expose per-condition source controls,
   with busy navigation guards and source-import errors/retry.
2. Replace inline instructions with a modal dialog. Save updates only that condition;
   Cancel and closing preserve text; saving empty text clears instructions.
3. Remove Design from navigation/review and route its legacy keys to Conditions.
   Preserve the existing normalization flow on Conditions Next.
4. Maintain registered GUI coverage for seven-step navigation, names, source isolation,
   picker cancellation/replacement, imports, modal Save/Cancel, long content and
   empty/populated/busy states. Run non-Qt GUI/docs focused checks and repo precommit.
   Qt/visible checks require an approved visible environment and remain separate.

## Progress

- Baseline GUI focused passed: 98 tests.
- Current branch is clean apart from the two pre-existing untracked paths.
- Removed the custom descriptive-name helper, gate and messages. Default and short
  names are valid under the existing nonempty backend name contract.
- Exposed the existing compact Base/Oddball source cards and moved fresh image intake
  to an app-owned background task. The GUI adopts results for the captured condition
  and role. Busy controls and navigation protect imports and project handoff.
- Added `ParticipantInstructionsDialog` with plain text, Save/Cancel and the captured
  condition as its target. Saving empty text clears instructions; cancellation and
  closing do not change the document. Minimum/default sizes are `520x360`/`640x460`.
- Removed Design from the guided flow, step metadata and review. Conditions Next owns
  the existing readiness/normalization handoff. Saved AB settings and detached editor
  source remain intact; guided AB design editing is deferred as requested.

## Verification and remaining acceptance

- GUI focused passed: changed-file Ruff/compilation and 98 safe tests.
- Docs focused passed: hygiene and 10 tests.
- Additional harness, import-boundary, Qt-registry, verification-driver and modality
  checks passed: 73 tests. Repository garbage-collection checks passed.
- Mypy passed for all 260 source files; changed-file whitespace checks passed.
- Repo precommit was attempted and stopped on six pre-existing Ruff E501 findings in
  `.codex-tmp/cognitive-load-library-2026-10-29/prepare.py` and
  `src/fpvs_studio/engines/standalone_contrast_example.py`. Those user-owned files
  were preserved. The repo-wide gate is not claimed as passing.
- Registered GUI coverage was updated for seven-step navigation, source selection,
  default/short names, source replacement/cancel/error recovery, busy guards, dialog
  Save/Cancel/clear, and long content at `1120x820` and both dialog sizes. Qt tests
  were not run, and source checks do not establish visual/no-clipping acceptance.
- Manual visible smoke: at `1120x820` in both themes, add a default-named condition,
  choose its Base/Oddball folders, add/select a second condition, and confirm source
  isolation. Open Edit Instructions, cancel a draft, save new text, reopen and clear
  it. Cancel a folder picker, retry a failed import, and advance directly to Timing
  with uniform and mixed-size sources to check readiness/normalization.

## Changed files

- GUI: `condition_setup_step.py`, `setup_wizard_page.py`, `main_window.py`,
  `components.py` under `src/fpvs_studio/gui/`.
- Registered GUI tests: `test_setup_conditions.py`, `test_setup_wizard_shell.py`,
  `test_action_palette.py`, `test_attentional_blink_stream_designer.py`,
  `test_condition_search.py`, `test_design_setup_step.py`,
  `test_experiment_categories_gui.py`, `test_setup_project_details.py`.
- Guidance: root/source/GUI `AGENTS.md`, `ARCHITECTURE.md`, `docs/FRONTEND.md`,
  `docs/GUI_WORKFLOW.md`, `docs/agent/agent-index.md`, `docs/EXPERIMENT_CATEGORIES.md`,
  `docs/VISUAL_EXPERIMENT_DESIGNER.md`, `docs/COGNITIVE_LOAD_FPVS.md`,
  `docs/CONDITION_MODIFIERS.md`, `docs/PLANS.md`, and this completed plan.
