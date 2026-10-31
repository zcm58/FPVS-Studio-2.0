# Plans

Use this map for feature-sized work; read only the plan matching the task. Current
behavior belongs in architecture/package guides and focused contracts. A plan may
remain active for external acceptance after its desktop source ships. An unfinished
historical release draft does not authorize publishing an old version.

## Active Work and Acceptance

| Plan | Current scope or remaining gate |
| --- | --- |
| [Automatic crash reporting](exec-plans/active/automatic-crash-reporting.md) | Default-on desktop source implemented; independent service activation/live delivery remains pending |
| [Bounded updater storage and upgrades](exec-plans/active/bounded-updater-storage-and-clean-upgrades.md) | Current combined install action implemented; visible/packaged and installed-upgrade acceptance remains separate |
| [Cloudflare bug reporting](exec-plans/active/cloudflare-bug-reporting.md) | Manual service implemented; retained native/packaged acceptance and automatic-crash follow-up have separate evidence |
| [Error reporting and 2.2.5 proposal](exec-plans/active/error-reporting-and-release-2.2.5.md) | Implemented source with an unfinished historical release request; preserve its evidence without republishing the already released version |
| [OpenFPVS account portal](exec-plans/active/fpvs-account-portal.md) | Live portal recorded; another-machine enrollment/download/revocation qualification remains pending |
| [Private Experiment Library](exec-plans/active/private-experiment-library.md) | Whole projects/current-project updates implemented; wider installed/Linux/keyring/hardware acceptance remains separate; individual-condition Phase 2 deferred |
| [Independent 2.2.7 release draft](exec-plans/active/release-2.2.7.md) | Built unpublished draft explicitly retained by later releases; its visible/release gates are unfinished |
| [Results reporting](exec-plans/active/remote-experiment-results-reporting.md) | Deployed integration and synthetic acceptance recorded; real two-machine presentation/metrics and shutdown cancellation remain operational checks |
| [Whole-project review uploads](exec-plans/active/streamlined-project-submission.md) | Desktop/service deployment recorded; authenticated live upload/email/publication qualification remains unperformed |
| [Studio/Toolbox/OpenFPVS integration](exec-plans/active/studio-toolbox-integration.md) | Completed handoff/shared reporting implemented; manual workflow and hardware/montage qualification remain separate |
| [Unicorn recording](exec-plans/active/unicorn-hybrid-black-support.md) | Normal markers/readiness implemented; full receiver, Toolbox and physical timing qualification remain pending |

## Planned Work

Proposals are not implemented behavior. Start in `planned/` and move a plan to
`active/` when implementation is authorized.

- [Image pool reset policy](exec-plans/planned/image-pool-reset-policy.md)
- [Participant results and question presentation](exec-plans/planned/participant-results-and-question-presentation.md)
- [Luminance/RMS equalization investigation](exec-plans/planned/luminance-rms-equalization-investigation.md)
- [Lab-independent recording setup](exec-plans/planned/lab-independent-recording-setup.md)

## Plan Rules and History

- [Execution-plan instructions](exec-plans/README.md)
- [Plan review workflow](exec-plans/plan-review-workflow.md)
- [Measured technical debt](exec-plans/tech-debt-tracker.md)
- [Completed implementation/release records](exec-plans/completed/)

Completed plans are historical evidence, not initial task context. Consult them only
when current contracts omit the rationale needed for the task. Keep old verification
limits intact; age alone does not complete an unperformed check. Small bug fixes and
narrow refactors need no plan unless they become cross-cutting.
