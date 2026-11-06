# actiCHamp adversarial audit and Studio 2.7.2 release

Status: Completed

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
- Build, packaged acceptance and public release verification passed as recorded below.

## Exact-source build and acceptance

Source `e8c77a3b30383f7bd397951a8619e848f31d61df` was pushed to master and bound
to annotated tag `v2.7.2`. The clean isolated checkout at `C:\Users\zcm58\fa272`
built label `release-2.7.2`; retained evidence is in the main checkout's
`build/release-2.7.2-evidence/`. It includes the earlier COM-selection, native
pending-write and plain-language setup/error fixes since 2.7.1.

- All 7,987 extracted installer files match the staged inventory, SHA-256
  `465b1e79d09cfbd92e9ac4d352fa0221c1e11a5775bf51e8ffd5b3f603a72d16`.
- All 272 Studio and 25 updater embedded modules match the exact source commit.
  Third-party modules, native files, bootstrap code and both base libraries match
  authenticated 2.7.1. The same 21 reviewed build warnings remain; none were added.
- Visible packaged Studio startup passed with frozen and metadata version 2.7.2,
  runtime imports (including serial/PsychoPy), Test/Pilot controls and layout checks.
  Independent updater update/repair screens passed with network and installer
  execution disabled. Both captured updater screens were visually reviewed.
- [Exact-source CI](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/42143283710)
  passed Windows, Intel/Apple Silicon Mac, both Mac exports on Windows and both
  Mac-origin return checks. Documentation CI and local documentation checks passed.

## Publication

[v2.7.2](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.7.2) was published
at `2026-11-06T01:40:22Z` as latest, stable and immutable, release ID `435979114`.
The four draft assets, exact notes, live remote source, annotated tag and asset
sizes/digests were verified before publication. Independent public downloads match
all four local files, and GitHub release/asset attestations verify. Ten candidate
and ten live updater cases passed, including current/older versions, repair and
downgrade rejection. No installer was executed.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.7.2.exe` | 301,059,033 | `84b75ccad692f32a3fdff3904066c7f4741e372ccf33b02773f3535a4dd70922` |
| `FPVS-Studio-Setup-2.7.2.exe.sha256` | 95 | `2d408c31ba6b145d9b8fa170891ba7cef77b790d040b6ffad465b49d5bd078e1` |
| `FPVS-Studio-Update-2.7.2.json` | 107 | `78f2cc937442eaed29a7d76dd04ea20a8e24979c948f1f4e48f37a56bd99bbef` |
| `FPVS-Studio-Update-2.7.2.json.sha256` | 97 | `6f88e856cf2297e5b08ec66a46e3891214990b0d482435bfdc239b0faa47ca44` |

## Limits

No additional reachable transport, scheduling, condition-boundary, handoff or
COM-selection defect was reproduced by this audit. Simulation does not qualify
electrical marker receipt, physical trigger/display timing or every vendor driver.
Real actiCHamp/Plus and LiveAmp/Recorder checks remain necessary; the staff-reported
1 ms delay has not been measured here and no timing correction is applied. Mac
remains source-only. Production installation and upgrade/uninstall acceptance were
not performed; working user projects, settings and installation were preserved.
