# Technical Debt Tracker

Use this tracker for debt items that may become execution plans. Keep detailed historical
notes in `../TECH_DEBT.md`.

## Active Candidates

- Monitor large cohesive GUI modules with `.\scripts\report_line_counts.ps1`; split only
  when responsibilities diverge or focused tests become hard to locate.
- Continue replacing one-off GUI styling with helpers in `src/fpvs_studio/gui/components.py`.

## Tracking Rules

- Promote debt to `active/` when it needs cross-layer work, workflow changes, or public
  contract changes.
- Keep narrow cleanup notes in `../TECH_DEBT.md`.
- Move completed execution plans to `completed/` after the work lands.
