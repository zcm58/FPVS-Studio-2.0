# Plans

Use this map for feature-sized work; read only the plan matching the task. Current
behavior belongs in architecture/package guides and focused contracts. An active
plan may track external acceptance after the source ships. The active and planned
scopes below were reviewed against Studio 3.1.0 and its integration baseline on
2026-11-19.

## Unattended verification on November 19, 2026

The linked plans record the Windows source, visible desktop, packaged updater,
and local Toolbox, OpenFPVS and Feedback results for this pass. The visible
Windows selections passed 141 Qt cases with two expected refresh-mode skips.
The native PsychoPy probes passed window lifecycle, a short compiled condition
and synthetic image/shape responses. The 15 active plans retain their physical,
installed, or live-service acceptance gates. The three planned features have
current baseline results and still require implementation.

The branch-wide precommit run passed Windows type checking (303 files),
Darwin type checking (nine files), repository audits, and 6,571 unit tests
with 41 platform or permission skips and 24 passing subtests. The unit run
used a 120-second default watchdog and left the separately run 1,500-session
archive fixture out. That fixture reached its own 600-second watchdog twice.
The previously timed-out packaging PATH and repeated-participant cases passed
in the branch-wide run. Verification corrected two test fixtures to use
explicit Experiment Test Mode and to measure updater cancellation from the
request. See [Results reporting](exec-plans/active/remote-experiment-results-reporting.md)
for archive-volume follow-up.

The November 20 follow-up completed the 1,500-session test under its original
watchdog and matched every retained report payload, receipt and capture.

## Active Work and Acceptance

| Plan | Current scope or remaining gate |
| --- | --- |
| [Slate & Signal Teal](exec-plans/active/slate-and-signal-teal-appearance.md) | Theme switching, contrast, experiment isolation and full-window 125% checks passed. Repeat the full-window matrix at 150% on a taller display. |
| [Trigger Tester serial discovery](exec-plans/active/trigger-tester-serial-discovery.md) | Recorder 2 digit sends verified. Qualify physical automatic discovery and BioSemi reconnect in ActiView. |
| [Windows refresh recommendation](exec-plans/active/windows-refresh-recommendation.md) | Native 60.02 Hz advisory and keyboard actions passed. Qualify the fixed 60/120 Hz display switch. |
| [Cursor regression audit](exec-plans/active/cursor-regression-audit-20261104.md) | Windows cursor passed Parsec, Escape and relaunch. Qualify the original reporter's Creatine project on the direct host. |
| [Fit task screens](exec-plans/active/task-screen-fit.md) | Viewport fitting shipped in 2.9.1. Repeat the affected Creatine laptop runs at 125% and 150%. |
| [macOS source support](exec-plans/active/macos-source-phase-1.md) | Source and hosted ARM/Intel transfer checks passed. Verify the physical GUI, Test/Pilot, affected-Mac repair and interactive services. |
| [Automatic crash reporting](exec-plans/active/automatic-crash-reporting.md) | Live intake enabled. Qualify packaged Studio and Toolbox end to end and track the separate crash filename/email rollout. |
| [Bounded updater storage and upgrades](exec-plans/active/bounded-updater-storage-and-clean-upgrades.md) | Fresh install, direct 3.0.1 upgrade and uninstall passed for 3.1.0. Qualify managed upgrades, historical upgrade paths and native recovery/cache behavior. |
| [Cloudflare bug reporting](exec-plans/active/cloudflare-bug-reporting.md) | Activate and verify direct feature requests in production. Finish packaged/native manual-report acceptance. |
| [OpenFPVS account portal](exec-plans/active/fpvs-account-portal.md) | Migration 0028 is deployed. Verify owner sign-in and lab membership, then enrollment, download and revocation on a second computer. |
| [Private Experiment Library](exec-plans/active/private-experiment-library.md) | Whole-project install, guarded updates and personal accounts shipped. Qualify installed multi-machine, credential and larger-project cases. Individual-condition import remains deferred. |
| [Results reporting](exec-plans/active/remote-experiment-results-reporting.md) | Live study receipts verified. Check two-machine presentation and metrics, plus cancellation during shutdown. |
| [Whole-project review uploads](exec-plans/active/streamlined-project-submission.md) | Standard and PI paths are deployed. Verify packaged authenticated uploads, notification and publication of the exact reviewed artifact. |
| [Studio/Toolbox/OpenFPVS integration](exec-plans/active/studio-toolbox-integration.md) | Studio export shipped and matching Toolbox support is in source. Verify the installed pair, roll out collection/roster support, then qualify the three-product workflow. |
| [Unicorn recording](exec-plans/active/unicorn-hybrid-black-support.md) | Raw BDF markers and offline timing report verified. Qualify receiver loss, Toolbox processing and optical timing. |

## Planned Work

Proposals are not implemented behavior. Start in `planned/` and move a plan to
`active/` when implementation is authorized.

- [Image pool reset policy](exec-plans/planned/image-pool-reset-policy.md) adds
  opt-in carryover between repeated Shuffle runs while retaining 3.1.0 seed behavior by default.
- [Participant results and question presentation](exec-plans/planned/participant-results-and-question-presentation.md)
  adds a filtered response viewer and Masking export using the existing result readers.
  Optional question styling remains a separate slice.
- [Named local recording profiles](exec-plans/planned/lab-independent-recording-setup.md)
  builds reusable per-computer profiles on the current Recording settings and selected-display preflight.

These future changes came out of the November 22 optimization review.


## Plan Rules and History

- [Execution-plan instructions](exec-plans/README.md)
- [Plan review workflow](exec-plans/plan-review-workflow.md)
- [Measured technical debt](exec-plans/tech-debt-tracker.md)
- [Completed implementation/release records](exec-plans/completed/)
- [Archived release drafts and proposals](references/archive/README.md)
- [Master consolidation](exec-plans/completed/master-consolidation.md):
  merged ImageEqualizer, Library updates and pending work with current updater/Mac repair source.
- [Targeted SciPy repair](exec-plans/completed/targeted-scipy-repair.md):
  preserve working SciPy versions and consolidate the helper into Repair Mac 2.
- [Mac repair preflight](exec-plans/completed/macos-repair-preflight.md):
  engine checks before changes, preserved initial health and distinct compatibility
  update/repair reports; affected-Mac acceptance remains under macOS Phase 1.
- [Mac repair completion reports](exec-plans/completed/macos-repair-completion-reports.md):
  one-click source repair, SciPy selection, accurate dependency errors and deployed
  automatic completion reports; affected-Mac acceptance remains under macOS Phase 1.
- [Project import progress](exec-plans/completed/import-progress-clarity.md)
- [Participant workbook wrap cache](exec-plans/completed/participant-workbook-wrap-cache.md)
  reuses text-wrap calculations within a single fit, with byte-identical exports and measured speedups.
- [Participant workbook source resolution](exec-plans/completed/participant-workbook-source-resolution.md)
  reuses the resolved project root while checking each source path independently.
- [Legacy recovery plan inventory](exec-plans/completed/legacy-recovery-plan-inventory.md)
  reads unchanged legacy plans once per search and revalidates the selected plan for rerun.
- [Passive fixation key filter](exec-plans/completed/passive-fixation-key-filter.md)
  builds one Escape filter per timed step and preserves each frame and key poll.
- [Legacy Attentional Blink ISI validator](exec-plans/completed/legacy-attentional-blink-isi-validator.md)
  shares the legacy source default across Studio and Toolbox model validation.
- [Responsive Assets stimulus import](exec-plans/completed/assets-stimulus-import-responsiveness.md)
  keeps the compatibility view responsive during source intake and preserves imported files and saved state.
- [Windows Builder demo bundle size](exec-plans/completed/windows-builder-demo-bundle-size.md)
  removes the upstream examples and saves 17.08 MB on the full 3.1.5 installer.
- [Windows release patches and acceptance](exec-plans/completed/windows-release-patches-and-acceptance.md)
  limits direct patches to five preceding patch numbers within the same major and minor version.
- [Studio 3.1.5 release](exec-plans/completed/release-3.1.5.md)
  records the published installers and verification results.
- [Normalization promotion recovery](exec-plans/completed/normalization-promotion-recovery.md)
  restores prior normalized image folders after a failed batch and retains a recovery copy if restoration is blocked.
- [Image Equalizer in-place rounding](exec-plans/completed/image-equalizer-in-place-rounding.md)
  lowers peak working memory while preserving exact PNG and report bytes.
- [Public Experiment Library](exec-plans/completed/public-experiment-library.md)
- [60.02 Hz display support](exec-plans/completed/60-02-hz-display-support.md):
  added the authored rate and verified two fullscreen runs on the Lenovo's 60.020425 Hz signal.
- [Image Equalizer](exec-plans/completed/image-equalizer.md): optional grayscale batch
  preparation with shared targets and parallel processing; current mission/spec
  updated. Focused and approved visible Windows checks passed; verification recorded.
- [Desktop panel hierarchy](exec-plans/completed/desktop-panel-hierarchy.md):
  flattened redundant framing and verified the affected layouts in Light and Dark.
- [Desktop text hierarchy](exec-plans/completed/desktop-text-hierarchy.md) records
  Windows text, launch status, keyboard and Reduce motion verification.
- [Desktop interface polish](exec-plans/completed/desktop-interface-polish.md):
  simplified project entry, guided setup, runtime diagnostics, Settings and Image Resizer.
  Verified in Light and Dark on the Windows desktop at 100% scaling.
- [macOS monitor selection](exec-plans/completed/macos-monitor-selection.md):
  per-launch Mac primary/default selection, chosen-display refresh checks and Retina
  presentation routing; source checks passed, with physical Mac acceptance unperformed.
- [Experiment monitor selection](exec-plans/completed/experiment-monitor-selection.md):
  per-launch Windows display choice defaults to the current primary monitor; selected
  display checks and fake-engine regressions pass, with visible acceptance unperformed.
- [Windows source setup](exec-plans/completed/windows-source-setup.md)
- [Inline Recording settings](exec-plans/completed/inline-recording-settings.md):
  hardware fields and project/default save actions share one Settings page; safe
  focused/precommit checks passed, with visible Qt acceptance unperformed.
- [Configurable demographics](exec-plans/completed/configurable-demographics.md)
- [Demographics form builder](exec-plans/completed/demographics-form-builder.md)
- [Condition Figure](exec-plans/completed/condition-figure.md)
- [Condition Figure waveforms](exec-plans/completed/condition-figure-waveforms.md)
- [Condition Figure stimulus sequence](exec-plans/completed/condition-figure-sequence.md)
- [Trigger Tester](exec-plans/completed/trigger-tester.md)
- [Manual project versions](exec-plans/completed/manual-project-versions.md)
- [History compatibility and Studio 2.8.2](exec-plans/completed/history-updates-release-2.8.2.md):
  history encoding, source/macOS updates, reviewed logs and Windows bundle fixes
  published immutable/latest; exact-source, packaged and public verification passed.
- [Studio 2.8.1 release](exec-plans/completed/release-2.8.1.md)
- [Studio 3.0.1 release](exec-plans/completed/release-3.0.1.md)
- [Studio 3.1.0 release](exec-plans/completed/release-3.1.0.md)
- [Studio 3.0.0 release](exec-plans/completed/release-3.0.0.md)
- [Studio 2.9.1 release](exec-plans/completed/release-2.9.1.md)
- [Studio 2.9.0 release](exec-plans/completed/release-2.9.0.md):
  scrollable Settings, guarded packaging, exact-source CI and verified immutable release.
- [Packaging DLL origin checks](exec-plans/completed/packaging-dll-origins.md)
- [Project Brain Products recording setup](exec-plans/completed/project-brainproducts-recording-setup.md):
  modal setup errors and first-launch project timing confirmation.
- [Studio 2.7.4 release](exec-plans/completed/release-2.7.4.md): serial/BioSemi fixes
  published immutable/latest; exact-source CI, packaged checks, public downloads,
  attestations and updater selection passed.
- [Serial errors and BioSemi recovery](exec-plans/completed/serial-errors-biosemi-recovery.md):
  actionable setup/launch recovery, pending-write ownership and consistent interrupted
  marker evidence; simulated, visible and full precommit checks passed.
- [TriggerBox full-exit guidance and 2.7.3](exec-plans/completed/triggerbox-full-exit-release-2.7.3.md):
  explicit Stop-versus-exit wording and Windows ownership guidance published;
  visible, exact-source, packaged and public download/updater checks passed.
- [actiCHamp adversarial audit and 2.7.2](exec-plans/completed/actichamp-adversarial-release-2.7.2.md):
  secondary cleanup diagnostics and reminder layout repaired; native failure probes,
  exact-source CI, packaged checks and immutable public release verification passed.
- [BrainVision transport qualification](exec-plans/completed/brainvision-transport-qualification.md):
  Windows pending-write completion, COM-selection preservation and LiveAmp/Recorder 1
  plus actiCHamp/Recorder 2 guidance; software and visible checks recorded, physical
  qualification remains separate.
- [Plain-language error recovery](exec-plans/completed/plain-language-error-recovery.md):
  common popup/inline failures explain the problem, possible cause and recovery;
  focused checks passed, precommit recorded a confirmed pre-existing Windows import
  failure, and visible GUI/hardware acceptance remains unperformed.
- [TriggerBox setup and error guidance](exec-plans/completed/triggerbox-setup-and-error-guidance.md):
  installed-driver/closed-utility guidance and specific serial recovery messages;
  safe precommit and post-integration checks passed, with GUI/hardware checks unperformed.
- [TriggerBox occupied-port recovery](exec-plans/completed/triggerbox-occupied-port-recovery.md):
  explicit manual COM access checks and actionable denied-access guidance; safe
  regression checks passed, with visible GUI and physical hardware checks unperformed.
- [Studio 2.7.1 release](exec-plans/completed/release-2.7.1.md):
  USB TriggerBox and launch-setting fixes published immutable/latest; 2.7.0
  source/dependency freshness, full CI, packaged checks and public updater verification passed.
- [TriggerBox USB edge cases](exec-plans/completed/triggerbox-usb-edge-cases.md):
  discovery cancellation, cleanup evidence and plain-language errors repaired;
  Recorder 1/2 guidance added. Further testing deferred at the user's request.
- [Studio 2.7.0 release](exec-plans/completed/release-2.7.0.md):
  unified participant workbook published immutable/latest; Windows checks,
  visible smoke, public bytes/attestations and updater checks passed. Mac ARM
  and dependent return checks await a hosted-runner capacity retry.
- [Results workbook automatic sizing](exec-plans/completed/results-workbook-auto-fit.md):
  content-fitted columns/rows, readable long-value disclosure, 13 existing workbooks
  updated without data changes, and runtime/precommit checks passed.
- [Participant output consolidation](exec-plans/completed/output-consolidation.md):
  one results workbook per project, 13 existing projects consolidated and 8165 CSVs
  plus two covered backup workbooks reversibly archived; parity and safe precommit
  passed, with optional native GUI smoke unperformed.
- [Vertical image visual angle](exec-plans/completed/vertical-image-visual-angle.md):
  Setup/preview expose width and height with explicit sizing modes; height-only
  persistence repaired, and core/GUI focused plus safe precommit checks passed.
- [macOS regression audit](exec-plans/completed/macos-regression-audit-20261104.md):
  repaired local-display readiness, engine compatibility, Finder metadata processing
  and cross-platform resolution checks; focused checks and safe precommit passed.
- [Studio 2.6.1 release](exec-plans/completed/release-2.6.1.md):
  merged Mac fixes and session-reporting repair published immutable/latest; source CI,
  visible packaged checks, public bytes/attestations and eight updater checks passed.
- [Reporting protocol and delivery audit](exec-plans/completed/reporting-protocol-audit-20261103.md):
  eleven additional current scopes connected, four proven sessions recovered,
  legacy electrode placeholder handling fixed and all eligible completed output reconciled.
- [Mac Retina presentation](exec-plans/completed/macos-retina-presentation.md):
  one-to-one backing pixels, restorable fullscreen chrome and explicit saved target
  resolution at Home/Run launch; native first-task pixels and safe/visible checks passed.
- [Mac Test/Pilot display freeze](exec-plans/completed/macos-test-display-freeze.md):
  nonexclusive display, bounded callback wait and foreground input; native refresh,
  callback-failure recovery and Cognitive Load abort/finalization passed. Literal
  keyboard interaction and full-session physical acceptance remain open.
- [Mac refresh recovery](exec-plans/completed/macos-refresh-recovery.md): bounded
  cancellable refresh-only children, protected automatic preflight and no duplicate
  Mac constructor check; safe precommit and 58 visible fake-only Qt checks passed.
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
- [Settings sidebar navigation](exec-plans/completed/settings-sidebar.md):
  six category pages, independently scrollable content and retained preferences;
  focused, precommit and 99 visible Windows cases passed at minimum/default sizes.
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
- [Sequential stimulus order](exec-plans/completed/sequential-stimulus-order.md):
  filename and word-list order, plus the shuffled image pool refill guard.
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
