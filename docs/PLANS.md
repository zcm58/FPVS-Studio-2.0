# Plans

Use this page to find planning material before making feature-sized changes.

## Execution Plans

- Plan instructions: `exec-plans/README.md`
- Review workflow: `exec-plans/plan-review-workflow.md`
- Planned future work: `exec-plans/planned/`
- Active plans: `exec-plans/active/`
- Completed plans: `exec-plans/completed/`
- Technical debt tracker: `exec-plans/tech-debt-tracker.md`

Current implementation:

- `exec-plans/active/project-bundle-import-export.md`

Concrete planned work:

- `exec-plans/planned/participant-electrode-exclusion-launch-prompt.md`
- `exec-plans/planned/luminance-rms-equalization-investigation.md`
- `exec-plans/planned/sinusoidal-contrast-modulation.md`

Completed plans are historical implementation notes. Read their directory only when
the current contracts do not explain why a landed decision exists.

Draft concrete future work in `planned/`. Move it to `active/` before implementing
changes that affect user workflows, public contracts, or multiple layers. Keep small bug
fixes and narrow refactors out of the planning system unless the work becomes
cross-cutting.

## Related Docs

- Product direction: `PRODUCT_SENSE.md`
- Architecture map: `../ARCHITECTURE.md`
- Current technical debt: `exec-plans/tech-debt-tracker.md`
