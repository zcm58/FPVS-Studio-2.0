# Technical Debt Tracker

This is the single source of truth for measured engineering debt. It is not a product
backlog or a record of already-completed cleanup.

Measurements below were refreshed on 2026-07-10. Re-run the evidence command before
promoting an item to an execution plan.

## TD-001: Large Source Context Surfaces

**Evidence:** `scripts/report_line_counts.ps1 -Threshold 500 -Top 50` reports 12 source
modules above 600 effective lines. The largest are:

- `src/fpvs_studio/gui/components.py` (1707)
- `src/fpvs_studio/gui/setup_wizard_page.py` (1127)
- `src/fpvs_studio/gui/main_window.py` (1079)
- `src/fpvs_studio/gui/controller.py` (1051)
- `src/fpvs_studio/gui/condition_setup_step.py` (965)
- `src/fpvs_studio/runtime/session_export.py` (947)
- `src/fpvs_studio/gui/fixation_settings_page.py` (884)
- `src/fpvs_studio/runtime/run_worker.py` (810)
- `src/fpvs_studio/gui/home_page.py` (751)
- `src/fpvs_studio/gui/run_page.py` (697)
- `src/fpvs_studio/engines/psychopy_engine.py` (695)
- `src/fpvs_studio/gui/condition_pages.py` (666)

**Impact:** Narrow work can require loading unrelated responsibilities, increasing agent
context, review time, and regression risk.

**Next action:** When one of these modules is already in scope, inventory its distinct
responsibilities and extract only a cohesive helper with an independent test seam. Start
with mixed orchestration/presentation modules, not cohesive pages. Preserve existing
public imports through a facade while callers migrate.

**Constraints:** File length is a signal, not a failure. Do not split solely to satisfy a
line target. Keep `gui.components` as the public component/theme surface, compiler and
runtime ownership intact, and PsychoPy code within engines.

**Verification:** Run the affected driver scope focused after each extraction, then the
repo precommit tier.

## TD-002: Broad Exception Boundaries

**Evidence:**

```powershell
rg -n "except (Exception|BaseException)|except:" src/fpvs_studio --glob '*.py'
```

finds 87 handlers across 25 files. The highest concentrations are
`gui/condition_setup_step.py` (12), `gui/controller.py` (11), and
`gui/condition_pages.py` (10).

**Impact:** Some handlers correctly translate backend failures into recoverable GUI,
hardware, or optional-dependency errors. Others may hide the actual failure class and
make logs, tests, and corrective UX less precise.

**Next action:** Audit one user workflow at a time. Classify each handler as an intended
boundary, a narrowly catchable failure, or an unexpected-error safeguard. Narrow only
handlers whose expected exceptions are proven by the called API and tests; preserve
structured logging and user-visible recovery.

**Constraints:** Do not mechanically replace every broad handler. Top-level GUI event,
installer, serial-device, archive-validation, and PsychoPy boundaries may need a final
defensive catch.

**Verification:** Use the owning focused scope and tests for both expected failures and
unexpected-error reporting.

## TD-003: Large Test Context Surfaces

**Evidence:** The same line-count report identifies several test modules above 900
effective lines, including `tests/gui/test_welcome_settings_flow.py` (1353),
`tests/unit/test_psychopy_engine.py` (1142),
`tests/unit/test_runtime_launcher_flow.py` (964), and
`tests/gui/test_setup_conditions.py` (915).

**Impact:** Agents must load unrelated fixtures and workflows to change or diagnose one
behavior, and focused test selection becomes harder to infer.

**Next action:** When adding coverage to one of these files, split by user workflow or
contract boundary while retaining shared fixtures in narrowly named helper modules.
Keep test node names and ownership discoverable from the verification scope.

**Constraints:** Do not split stable tests mechanically or create a generic fixture
dump. Production seams take priority when a test is large only because its production
surface is too broad.

**Verification:** Run the original file before the move, the new focused files after it,
and the owning driver scope.

## Tracking Rules

- Record evidence, affected paths, impact, next action, constraints, and verification.
- Promote an item to `active/` only after the work is approved and cross-layer or
  contract-sized. Keep narrow cleanup here until selected.
- Remove an item when its evidence no longer exists; completed implementation history
  belongs in `completed/`, not this tracker.
- Re-measure instead of copying old counts into a new plan.
- Do not add feature ideas, passing gates, or recurring maintenance reminders as debt.
