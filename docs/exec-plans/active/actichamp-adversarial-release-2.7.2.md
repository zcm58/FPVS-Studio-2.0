# actiCHamp adversarial audit and Studio 2.7.2 release

Status: Active

## Outcome and authorization

The user requested another attempt to break the actiCHamp trigger workflow, fixes
for reproduced defects, a summary of findings, pushed results, a version bump and
publication. Target the next patch release, 2.7.2, after confirming remote identity.
The prior visible Windows GUI approval persists. No actual TriggerBox/EEG hardware
is available; do not install vendor software or claim electrical/timing qualification.

## Work and verification

1. Audit independent transport, runtime/scheduling and GUI state boundaries using
   native API interception, fake services and realistic compiled configurations.
   Reproduce a failure before changing production; report explicitly if a probe
   finds no defect. Do not add retries, marker queues or silent fallbacks.
2. Verify focused regressions, affected visible GUI states and repository precommit.
   Preserve unrelated untracked source, existing build environments and retained
   artifacts. Prior policy-blocked cleanup targets remain untouched.
3. Bump only canonical package metadata, prepare concise release notes, build from
   an isolated exact source snapshot and preserve the published dependency baseline.
   Verify frozen source/imports, installer inventory and visible packaged startup.
4. Push source and its version tag; stage release assets as a draft, compare remote
   digests, publish, then verify public downloads, attestations and updater selection.
   Keep physical EEG, production installation and destructive upgrade testing separate.

## Starting evidence

- Source baseline: `618c084fa5f629712654b281bc43c8f92edec5ae`; package version 2.7.1.
- Previous audit: 308 trigger checks; 5,500 safe tests and 32 platform/permission
  skips; visible port/amplifier tests passed. Some unrelated file/settings fixture
  failures passed isolated reruns, with their cause unconfirmed.
- User-owned `.codex-tmp/` and `standalone_contrast_example.py` remain outside scope.

## Findings and release evidence

- Native transport: no new production defect found. Eight additional cases passed
  on unchanged code for rejected writes, startup timeout, failed cancellation and
  completion ownership. Native suite: 20 passed; trigger focused: 316 passed.
- Runtime: reproduced lost secondary TriggerBox close diagnostics after an existing
  playback/trigger failure. Existing interrupted evidence and logs now retain both
  errors without changing the raised primary exception or result schemas. Peer review
  also caught duplication when close repeated the primary error's retained cause;
  identity-based deduplication preserves genuinely distinct aggregate cleanup errors.
- GUI: no new COM-selection/amplifier-state defect found. Reproduced the USB reminder
  expanding its 480x170 minimum to 480x176; a six-pixel spacing reduction restores the
  documented size. Reminder tests now await asynchronous launch completion before
  teardown. Added actiCHamp port/rate override persistence across default changes.
  Targeted visible: 19 passed; an extended selection passed 176 before a transient
  QSettings fixture failure, which passed alone. An earlier broad run was interrupted
  and is not counted as passing. Safe GUI focused: 178 passed.
- Release baseline is immutable v2.7.1, release ID 435788428. Its live installer
  digest matches the retained authenticated artifact. Non-Studio package versions
  exactly match that release's environment; only editable Studio metadata was
  refreshed to 2.7.2. Dependency consistency and packaging baseline (192 tests) pass.
- Candidate-source precommit passed: 5,520 tests, 32 platform/permission skips and
  24 subtests; all audits and Windows/macOS type checks passed. Runtime focused:
  1,035 passed, four privilege skips; final recording/durability group: 202 passed,
  one privilege skip. Packaging after the version bump: 192 passed.
- Build, packaged acceptance and publication pending.
