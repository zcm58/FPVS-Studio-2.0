# Plans

Automatic crash-report implementation and service rollout are tracked in
[the active plan](exec-plans/active/automatic-crash-reporting.md), with default-on
desktop preferences, persistent opt-out and existing maintainer email delivery.
Browser-free service registration is implemented; live activation remains pending there.

Use this page to find planning material before making feature-sized changes.

## Execution Plans

- Plan instructions: `exec-plans/README.md`
- Review workflow: `exec-plans/plan-review-workflow.md`
- Planned future work: `exec-plans/planned/`
- Active plans: `exec-plans/active/`
- Completed plans: `exec-plans/completed/`
- Technical debt tracker: `exec-plans/tech-debt-tracker.md`

Current implementation:

- [Studio 2.4.2 crash fixes release](exec-plans/active/release-2.4.2.md)
- [Opt-in experiment data sharing and comparison](exec-plans/active/remote-experiment-results-reporting.md)
- [Unicorn Hybrid Black recording support](exec-plans/active/unicorn-hybrid-black-support.md) (normal marker output enabled; full receiver, Toolbox and physical timing validation pending)
- [Experiment Library: Phase 1 whole projects](exec-plans/active/private-experiment-library.md)
- [Cloudflare bug reporting: desktop implementation](exec-plans/active/cloudflare-bug-reporting.md)
- `exec-plans/active/bounded-updater-storage-and-clean-upgrades.md`

Concrete planned work:

- [Participant results and question presentation](exec-plans/planned/participant-results-and-question-presentation.md) (proposal; not implemented)
- [Luminance/RMS equalization investigation](exec-plans/planned/luminance-rms-equalization-investigation.md) (algorithm and validation investigation; not implemented)
- [Lab-independent recording setup](exec-plans/planned/lab-independent-recording-setup.md) (named profiles and display selection; not implemented)

Completed plans are historical implementation notes. Read their directory only when
the current contracts do not explain why a landed decision exists.

Recent completion: [Studio crash reliability](exec-plans/completed/studio-crash-reliability.md)
(native worker cleanup, shutdown, startup recovery and local crash diagnostics; packaged
and physical runtime acceptance remain separate).

Recent completion: [Reporting upload lifecycle](exec-plans/completed/long-running-results-reporting.md)
(automatic local retirement and offline startup retry; visible/live qualification
remains documented).

Recent completion: [FPVS Studio 2.2.6 Library reconnection release](exec-plans/completed/release-2.2.6.md).

Recent completion: [Upload/download source security hardening](exec-plans/completed/upload-download-security-hardening.md) (runtime/dependency acceptance limits remain documented).

Recent completion: [FPVS Studio 2.2.1 release](exec-plans/completed/release-2.2.1.md).

Recent completion: [FPVS Studio 2.2.4 release](exec-plans/completed/release-2.2.4.md).

Recent completion: [MSMS AB repeated targets](exec-plans/completed/msms-ab-repeated-targets.md).

Recent completion: [MSMS AB all-character triggers](exec-plans/completed/msms-ab-all-character-triggers.md).

Recent completion: [Masking condition modifiers](exec-plans/completed/masking-condition-modifiers.md).

Recent completion: [Masking event markers](exec-plans/completed/masking-event-markers.md).

Recent completion: [Masking 1.4.0 and Studio 2.2.0](exec-plans/completed/masking-1.4-release.md).

Recent completion: [Frontend usability and responsiveness](exec-plans/completed/frontend-usability-polish.md).

Recent completion: [Backend reliability and compilation efficiency](exec-plans/completed/backend-reliability-efficiency.md).

Recent completion: [FPVS Condition Modifiers](exec-plans/completed/fpvs-condition-modifiers.md).

Recent completion: [Cognitive Load FPVS](exec-plans/completed/cognitive-load-fpvs.md).

Recent completion: [Attentional Blink pilot mode and release v1.8.0](exec-plans/completed/attentional-blink-pilot-release.md).

Recent completion: [Multi-session release v1.5.3](exec-plans/completed/multi-session-release-v1.5.3.md).

Recent completion: [Attentional Blink burst recall study](exec-plans/completed/attentional-blink-burst-recall.md).

Recent completion: [Typed Attentional Blink recall and readiness gates](exec-plans/completed/attentional-blink-typed-recall.md).

Recent completion: [Category-aware accuracy view](exec-plans/completed/category-aware-accuracy-view.md).

Recent completion: [Editable Attentional Blink rate and v1.5.2](exec-plans/completed/attentional-blink-rate-v1.5.2.md).

Recent completion: [Multi-session participant projects](exec-plans/completed/multi-session-participant-projects.md).

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
- [Streamlined project review uploads](exec-plans/active/streamlined-project-submission.md)
