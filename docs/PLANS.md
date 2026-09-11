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

- `exec-plans/active/attentional-blink-rate-v1.5.2.md`
- `exec-plans/active/bounded-updater-storage-and-clean-upgrades.md`

Concrete planned work:

- `exec-plans/planned/restore-tutorials-file-menu-entry.md`
- `exec-plans/planned/luminance-rms-equalization-investigation.md`

Accepted future improvements (implementation has not started):

1. [Lab-independent recording setup](exec-plans/planned/lab-independent-recording-setup.md)
2. [Explicit session-design controls](exec-plans/planned/explicit-session-design-controls.md)
3. [Rehearsal in the installed application](exec-plans/planned/packaged-experiment-rehearsal.md)
4. [Stimulus comparison and preprocessing previews](exec-plans/planned/stimulus-comparison-and-preprocessing-previews.md)
5. [Persistent session quality report](exec-plans/planned/persistent-session-quality-report.md)

These five plans record the user's accepted product direction and remain in `planned/`
until implementation begins. The stimulus-comparison plan links to the existing
luminance/RMS algorithm investigation instead of duplicating its scientific decisions.

Completed plans are historical implementation notes. Read their directory only when
the current contracts do not explain why a landed decision exists.

Recent completion: [Patch updates and v1.5.1](exec-plans/completed/patch-updates-v1.5.1.md).

Recent completion: [Setup UX refinement](exec-plans/completed/setup-ux-design-refinement.md).

Recent completion: [Retire Attentional-Blink image pairs](exec-plans/completed/retire-attentional-blink-image-pairs.md).

Recent completion: [Attentional-Blink letter stream study](exec-plans/completed/attentional-blink-letter-stream-study.md).
Also completed: [Attentional-Blink fixation visibility](exec-plans/completed/attentional-blink-fixation-visibility.md).

Draft concrete future work in `planned/`. Move it to `active/` before implementing
changes that affect user workflows, public contracts, or multiple layers. Keep small bug
fixes and narrow refactors out of the planning system unless the work becomes
cross-cutting.

## Related Docs

- Product direction: `PRODUCT_SENSE.md`
- Architecture map: `../ARCHITECTURE.md`
- Current technical debt: `exec-plans/tech-debt-tracker.md`
