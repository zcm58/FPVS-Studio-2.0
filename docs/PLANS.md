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

- [Studio to Toolbox and OpenFPVS integration](exec-plans/active/studio-toolbox-integration.md)
- [Experiment data sharing and comparison](exec-plans/active/remote-experiment-results-reporting.md)
- [Unicorn Hybrid Black recording support](exec-plans/active/unicorn-hybrid-black-support.md) (normal marker output enabled; full receiver, Toolbox and physical timing validation pending)
- [Experiment Library: Phase 1 whole projects](exec-plans/active/private-experiment-library.md)
- [Cloudflare bug reporting: desktop implementation](exec-plans/active/cloudflare-bug-reporting.md)
- `exec-plans/active/bounded-updater-storage-and-clean-upgrades.md`

Concrete planned work:

- [Optional image pool reset policy](exec-plans/planned/image-pool-reset-policy.md) (retain reset per condition run; future carryover option with user-facing pros/cons)
- [Participant results and question presentation](exec-plans/planned/participant-results-and-question-presentation.md) (proposal; not implemented)
- [Luminance/RMS equalization investigation](exec-plans/planned/luminance-rms-equalization-investigation.md) (algorithm and validation investigation; not implemented)
- [Lab-independent recording setup](exec-plans/planned/lab-independent-recording-setup.md) (named profiles and display selection; not implemented)

Completed plans are historical implementation notes. Read their directory only when
the current contracts do not explain why a landed decision exists.

Recent completion: [Setup Next validation dialog and optional description](exec-plans/completed/setup-next-validation-dialog.md)
(optional description, modal blockers and visible GUI acceptance; broad verification limitations recorded).

Recent completion: [Separate Setup timing/display and session pages](exec-plans/completed/setup-timing-session-split.md)
(eight-step wizard, atomic order repair, visible GUI acceptance and clean integration precommit verified).

Recent completion: [Conditions authoring consolidation](exec-plans/completed/conditions-authoring-consolidation.md)
(seven-step Setup, per-condition image folders and modal instructions; visible Qt acceptance remains separate).

Recent completion: [Setup image source selection](exec-plans/completed/setup-image-source-selection.md)
(simple per-condition Base/Oddball folders without image previews; visible Qt acceptance remains separate).

Recent completion: [Simplified modifiers and post-condition questions](exec-plans/completed/simple-condition-modifiers-and-post-questions.md)
(simple Yes/No authoring, retained answer journals and cumulative project-root CSV; visible GUI acceptance remains separate).

Recent completion: [Condition order preview and saved manual arrangements](exec-plans/completed/condition-order-preview-and-manual-order.md)
(exact reusable arrangements, compact preview/reordering and atomic saves; visible GUI acceptance remains separate).

Recent completion: [Independent randomization and seed reuse](exec-plans/completed/reproducible-randomization-controls.md)
(three domains, one Fixed/New policy, pending launch snapshots and immutable full/compact provenance; visible GUI acceptance remains separate).

Recent completion: [Per-condition presentation counts](exec-plans/completed/per-condition-repeat-counts.md)
(exact totals, constrained pooled order, preserved task/recovery occurrence identity and ordering fingerprints; visible GUI acceptance remains separate).

Recent completion: [Per-condition stream duration](exec-plans/completed/per-condition-stream-duration.md)
(exact seconds, preserved legacy continuous streams and requested/resolved export fields; visible GUI acceptance remains separate).

Recent completion: [Clear presentation frequency and confirmed condition overrides](exec-plans/completed/clear-presentation-frequency.md)
(shared/default frequency, confirmed condition overrides and atomic duration preservation; visible GUI acceptance remains separate).

Recent completion: [actiCHamp parallel-port output](exec-plans/completed/actichamp-parallel-port.md)
(explicit Windows LPT connection, metadata-only detection, checked installed-driver
I/O, pulse/reset validation and portable recording evidence; visible GUI and physical
hardware qualification remain separate).

Recent completion: [BioSemi project serial-port selector](exec-plans/completed/biosemi-port-selector.md)
(editable ActiveTwo/ActiveThree port selection, selected-port availability checks
without marker bytes, and atomic saves to existing project trigger settings).

Recent completion: [TriggerBox serial-port access checks](exec-plans/completed/triggerbox-port-access-check.md)
(explicit Detect opens/closes recognized candidates without marker bytes; automatic
discovery stays metadata-only, with fake serial and registered GUI coverage).

Recent completion: [Computer default EEG hardware](exec-plans/completed/default-eeg-hardware.md)
(first-run hardware choice, computer defaults, project overrides/reset and captured
completed-session export; source and visible GUI checks passed in 2.5.0).

Recent completion: [One-time incomplete-session acknowledgement](exec-plans/completed/interruption-acknowledgement.md)
(explicit project-local acknowledgement, quiet project reopening, retained manual
history and unchanged incomplete-session evidence; source and visible Qt checks passed).

Recent completion: [Branch feature consolidation and cleanup](exec-plans/completed/branch-consolidation-2026-10-26.md)
(missing Library cleanup and bundle/compiler safeguards integrated; 11 local and two
remote branches deleted after ancestry/equivalence checks and verified backup).

Recent completion: [TriggerBox discovery and pulse validation](exec-plans/completed/triggerbox-recording-setup.md)
(editable detected COM ports, amplifier/rate pulse limits and verified compiled
6 Hz / 60 Hz marker spacing; visible GUI passed in 2.5.0; physical hardware acceptance remains).

Recent completion: [Studio 2.5.0 release](exec-plans/completed/release-2.5.0.md)
(BrainVision setup, default EEG hardware, full installer and direct 2.4.8 patch;
visible GUI, artifact hashes, public downloads and updater checks passed).

Recent completion: [Studio 2.5.6 release](exec-plans/completed/release-2.5.6.md)
(automatic Library project update offers; full installer, signed release/assets,
public download hashes and eight live updater checks verified).

Recent completion: [Studio 2.5.3 release](exec-plans/completed/release-2.5.3.md)
(updater bullet formatting and compact release notes; full installer, signed
release/assets, public downloads and eight live updater cases verified).

Recent completion: [Studio 2.5.2 release](exec-plans/completed/release-2.5.2.md)
(Library GUI cleanup, restored report versions and ActiveThree labels; full installer,
signed release/assets, public downloads and eight live updater cases verified).

Recent completion: [Studio 2.5.1 release](exec-plans/completed/release-2.5.1.md)
(full installer published; signed release/assets, public download hashes and eight
live updater cases verified; native GUI and installed-lifecycle checks remain pending).

Recent completion: [Studio 2.4.8 minor bug fixes release](exec-plans/completed/release-2.4.8.md)
(full installer, direct 2.4.7 patch, public updater checks, downloaded bytes and
signed release attestations verified; installed 2.4.7 retained).

Recent completion: [Runtime reliability audit](exec-plans/completed/runtime-reliability-audit.md)
(task graphics lifetime, numeric input, result durability, interruption recovery and
worker/launch races; Windows rename-test intermittency and native acceptance limits
are documented). These source fixes are published in 2.4.8.

Recent completion: [Graphics crash repair and condition recovery](exec-plans/completed/crash-condition-recovery.md)
(graphics-thread cleanup, durable interrupted-condition guidance and targeted reruns
that preserve completed results). Published in
[Studio 2.4.7](exec-plans/completed/release-2.4.7.md), with full/patch payloads,
signed release assets and public updater selection verified. Visible and physical
acceptance remain documented; automatic-email service activation is separate.

Recent completion: [Behavior-preserving cleanup](exec-plans/completed/behavior-preserving-cleanup.md)
(dead-code removal and shared compiler, export and image-size logic; 421 fewer production
lines, focused/visible checks passed, with baseline-reproduced Windows bundle rename
failures documented for the broader precommit suite).

Recent completion: [GUI responsiveness during authoring and project discovery](exec-plans/completed/ui-responsiveness.md)
(background project scans, deferred hidden-page refreshes, and per-update AB preview
reuse; safe verification passed, with visible GUI acceptance still documented).

Recent completion: [ActiveThree and Brain Products recording support](exec-plans/completed/additional-eeg-hardware.md)
(ActiveThree via BioSemi serial and TriggerBox/Plus via pulse/reset adapter;
hardware/visible qualification and unprofiled Toolbox montage support remain separate).

Recent completion: [UI action discovery and condition navigation](exec-plans/completed/ui-action-discovery.md)
(File > Find Action with Ctrl+F, condition filtering, and frontend agent guidance;
registered Qt and full visible acceptance remain documented).

Recent completion: [Studio crash reliability](exec-plans/completed/studio-crash-reliability.md)
(native worker cleanup, shutdown, startup recovery and local crash diagnostics; packaged
and physical runtime acceptance remain separate).

Recent completion: [Studio 2.4.2 startup crash fixes release](exec-plans/completed/release-2.4.2.md).

Recent completion: [Studio 2.4.3 updater GUI release](exec-plans/completed/release-2.4.3.md).

Recent completion: [Studio 2.4.5 Toolbox handoff and shared reporting](exec-plans/completed/release-2.4.5.md)
(hardware declarations, automatic completed handoff and default-on first enrollment;
full installer, direct 2.4.4 patch and public updater checks pass; manual hardware
and compatible Toolbox release qualification remain separate).

Recent completion: [Studio 2.4.4 minor bug fixes](exec-plans/completed/release-2.4.4.md)
(project handoff, upload ownership/context, durable opt-out, capture review and crash
recovery; immutable full/patch release and public updater selection verified).

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

Recent completion: [Inter-lab reliability and Studio 2.5.4](exec-plans/completed/interlab-reliability-release-2.5.4.md)
(Library permissions, retained canceled submissions, guarded pending enrollment recovery;
compiled screens, full installer and public updater/asset verification passed).
