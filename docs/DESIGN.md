# Design

Use this page as the design-document hub. FPVS Studio design decisions should support
fast returning-user launches, low-friction setup, and clear scientific/runtime status.

## Current Design Sources

- Core UX beliefs: `design-docs/core-beliefs.md`
- PySide6 GUI workflow and test guidance: `GUI_WORKFLOW.md`
- Public GUI component/theme surface: `../src/fpvs_studio/gui/components.py`
- GUI package guidance: `../src/fpvs_studio/gui/AGENTS.md`

## Update Rules

- Put reusable design principles in `design-docs/`.
- Put concrete GUI behavior and smoke-test expectations in `GUI_WORKFLOW.md`.
- Put feature-sized redesign plans in `exec-plans/active/` before implementation.
- Keep page-local styles out of GUI modules unless the visual need is truly local.
