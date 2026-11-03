# Plans

Use this map for feature-sized work; read only the plan matching the task. Current
behavior belongs in architecture/package guides and focused contracts. A plan may
remain active for external acceptance after its desktop source ships. An unfinished
historical release draft does not authorize publishing an old version.

## Active Work and Acceptance

| Plan | Current scope or remaining gate |
| --- | --- |
| [macOS source support: Phase 1](exec-plans/active/macos-source-phase-1.md) | Source implementation and automated Mac/bundle checks passed; physical GUI/display/service acceptance deferred |
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
- [Simple Mac clone setup](exec-plans/completed/mac-clone-bootstrap.md): automatic
  project-contained Python/dependencies, Finder shortcuts and scoped PyCharm setup;
  fresh install, focused/native Qt and safe precommit checks passed.
- [Studio 2.6.0 release](exec-plans/completed/release-2.6.0.md):
  Setup/session, themes and Mac-source features published immutable/latest; frozen
  build, public-byte/attestation and eight production-updater checks passed.
- [Windows-primary platform test adapters](exec-plans/completed/windows-primary-platform-test-adapters.md):
  explicit platform seams, native environment selection and Windows-first CI; obsolete
  environments removed, native Windows/Mac safe checks and 100 visible Qt cases passed.
- [Remove Create Control Condition](exec-plans/completed/remove-control-condition-workflow.md):
  dedicated GUI/document workflow removed; saved conditions, formats, assets and manual
  authoring preserved, with full safe precommit and 27 visible Qt cases passed.
- [Settings hierarchy and theme preference](exec-plans/completed/settings-hierarchy-and-theme.md):
  flat Settings and persisted Light/Dark/Auto implemented; precommit and focused/visible
  checks passed, with optional Welcome test-order and native/scaling limits recorded.
- [Setup visual layout and hierarchy](exec-plans/completed/setup-visual-layout.md):
  all eight pages visually reviewed in both themes, balanced workspaces and 57 focused
  visible sizing checks; safe-suite transient Windows access failure recorded.
- [Drag-and-drop randomized condition blocks](exec-plans/completed/randomized-block-condition-editor.md):
  real/partial blocks, within-block dragging and versioned compatibility; source checks
  and full-run limitations recorded, visible Qt acceptance remains manual.
- [One pseudorandom condition-order editor](exec-plans/completed/single-condition-order-editor.md):
  sole Display & Session entry, clearer arrangement controls and retained atomic
  order repair; verification results and a transient Windows access failure recorded.
- [Display and Session columns](exec-plans/completed/display-session-columns.md):
  combined step 4 with eight-step navigation; safe precommit passed, visible Qt
  acceptance remains manual.
- [Separate Timing and Display](exec-plans/completed/separate-timing-display-steps.md):
  nine-step Setup and exact shared-refresh compatibility for mixed image rates;
  source checks recorded, visible Qt acceptance remains manual.
- [Plain-language randomization](exec-plans/completed/plain-language-randomization.md):
  independent participant reuse choices and seed-free Session/Review; source checks
  passed, visible Qt acceptance remains manual.
- [Studio 2.5.8 release](exec-plans/completed/release-2.5.8.md): measured participant
  instruction layout, Birth Control overlap repair, full installer and public updater checks.
- [Studio 2.5.7 release](exec-plans/completed/release-2.5.7.md): shared mouse-selection
  repairs, pilot timing, full installer, immutable attestations and live updater checks.
- [Cognitive Load pilot timing](exec-plans/completed/cognitive-load-pilot-timing.md):
  project-specific 40-second repetitions, subtract-three counting, immediate endpoints
  and one late fixation target; source checks passed, visible presentation remains manual.

Completed plans are historical evidence, not initial task context. Consult them only
when current contracts omit the rationale needed for the task. Keep old verification
limits intact; age alone does not complete an unperformed check. Small bug fixes and
narrow refactors need no plan unless they become cross-cutting.
