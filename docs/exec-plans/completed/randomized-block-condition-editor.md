# Drag-and-drop randomized condition blocks

Status: Completed

## Workflow and acceptance

Arrange condition presentations by dragging within real randomized blocks in the
Pseudorandom Condition Order Editor. Use fixed, nonselectable Block 1/2/3 headers and
label partial later blocks. Each block includes each condition with presentations
remaining once. User approved partial blocks for unequal requested counts. Retain the
no-adjacent-equal-condition rule, including across boundaries; incompatible count tails
must be explained rather than rerolled or silently changed. Single-condition studies
retain every requested presentation. Alt+Up/Down provides keyboard reordering without
visible Move buttons. External, cross-block, stale, busy and dismissed drops are refused.

Keep editor sizes 700x520 / 780x620 and Setup 1120x820 in both themes. Renumber names,
presentation occurrences, tooltips and accessible text after moves. Preserve duplicates
as distinct presentations and exact counts. Save persists the exact visible order and
block design atomically; Cancel and failed saves retain source and parent drafts.

## Compatibility and boundaries

An optional condition_ordering=randomized_blocks marker distinguishes new designs from
historical pooled plans. New Studio GUI projects opt in explicitly; absent fields retain
legacy behavior. Opening an old saved order creates a block-arranged draft, with explicit
Save consequence copy; it never rewrites the project. New schemas cover Project1.17,
config1.15, SessionPlan1.10 and result1.5. Use existing SessionBlock/occurrence fields and
new generated/saved block policies. Keep per-condition/presentation RNG namespaces and
historical recovery intact. Do not add participant block-break screens. AB and masking
retain their task/group workflows; ordinary block preference can remain dormant while
masking is active. Runtime and engines continue to consume compiled contracts only.

## Verification

Core tests cover block membership, unequal totals, seed determinism, cancellation,
backward generation, exact save/compile parity, legacy behavior and occurrence timing.
Contracts cover strict versions, project/config/result roundtrip, fingerprint identity,
recovery and participant flow. Safe drag tests exercise guarded actual handler methods
without Qt. Registered GUI tests cover headers, partial blocks, within-block drop,
keyboard boundaries, save/cancel, long names, themes and stale/busy/invalid states.
Run GUI/core focused, docs focused and repository precommit. Qt remains unrun without
explicit approval for a safe visible environment.

## Visible manual smoke path (not performed)

At 1120x820 in each theme, open the sole Session editor entry. At both dialog sizes,
inspect two and three blocks, unequal counts/partial blocks and long names. Drag within
a block, above/below rows and to its end; test scrolling, keyboard moves and attempted
header/cross-block/external drops. Check selection, complete tooltips, numbering and
Save enablement. Create/fix a boundary adjacency error. Save/reopen and inspect run-plan
blocks; Cancel an old pooled-order conversion and confirm it is unchanged. Exercise
busy generation, stale setup and failed-save retry using stubs. Runtime/hardware windows
require their own approved environment.

## Progress

- Implemented guarded within-block drag/drop, fixed partial-block headers and Alt+Up/Down
  keyboard moves; removed visible Move buttons. Draft conversion, exact Save and Cancel
  preserve source until explicit persistence. The sole setup entry remains Session.
- Core generates real randomized blocks backwards so feasible singleton tails do not
  trap a greedy forward algorithm. Saved flat lists validate exact round membership.
  Legacy pooled contracts, occurrence timing and specialized workflows are retained.
- New Studio creation explicitly opts in; direct/default legacy factory calls and old
  saved projects retain their ordering. Dormant masking markers roundtrip without
  changing specialized masking execution. No participant block-break screens added.
- Focused core ordering/compiler checks:193 passed. Contract/preflight final checks:43
  passed, including strict1.10 provenance. Safe drag handlers:19 passed. GUI focused:
  163 passed; full-source mypy261 files, changed-file Ruff and compilation passed.
- Full non-Qt precommit:4806 passed,13 Windows symlink skips,2 failures. One was the
  added architecture paragraph exceeding its1000-word budget; shortened and verified.
  The other was unchanged serialization's Windows-lock retry test[32], which observed
  extra real replacement retries. Final targeted run of serialization, docs, block
  contracts, runtime preflight and drag tests passed85 tests. The original full run is
  recorded as failed rather than a clean full-suite pass.
- Registered Qt coverage includes actual editor data/headers/drop integration, keyboard
  boundaries, partial rounds, default/legacy/AB creation, cancellation, save/reopen,
  busy/stale/external drops and both themes at minimum/default sizes. It was not run
  without explicit visible-environment approval.

## Changed files and path audit

Production: ARCHITECTURE.md; docs/FRONTEND.md, GUI_WORKFLOW.md, SESSION_PLAN.md, PLANS.md;
core/compiler.py, condition_timing.py, enums.py, execution.py, migrations.py, models.py,
project_config.py, session_ordering.py, session_plan.py; gui/AGENTS.md,
condition_order_dialog.py, condition_timing_table.py, controller.py, document.py,
document_conditions.py, randomization_editor.py, run_page.py, session_structure_page.py,
setup_wizard_page.py; runtime/preflight.py, run_worker.py. Package paths above are under
src/fpvs_studio/. Tests:tests/gui/test_condition_order_dialog.py,
test_conditions_session_fixation.py; tests/unit/test_block_ordering.py,
test_block_ordering_contracts.py, test_condition_order_drag.py. This plan is also tracked.

Creation, explicit editor Save and config export/import keep the active project root
as their path owner; no absolute user paths or new asset locations were introduced.
Tmp-path tests cover versioned roundtrips, invalid config rejection before import I/O,
exact recovery and legacy omission. Cancel never writes converted drafts.
