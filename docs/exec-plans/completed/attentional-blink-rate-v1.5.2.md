# Editable Attentional Blink Rate And v1.5.2

Status: Completed

## Outcome

Expose the existing project-wide presentation rate in Setup > Design for native
Attentional Blink streams. Keep 10 Hz as the default, accept positive finite decimal
rates, and preserve exact whole-frame presentation and onset-to-onset SOA validation.
Changing rate does not silently rescale authored SOAs or round presentation timing.
Build and publish v1.5.2 with a full installer, a direct v1.5.1 patch, and update JSON.

## Implementation And Verification

1. Add a model-backed draft rate control to the existing Design header. Apply rate,
   sources, colors, and all SOAs atomically; invalid changes leave the project intact.
   Update timeline and quarter-speed preview copy/timing from the draft rate.
2. Verify decimal rates, persistence, unchanged SOAs, compiled event timing, invalid
   rate/frame combinations, and draft apply/cancel behavior. Retain registered GUI
   geometry coverage at the existing 1120x820 wizard minimum.
3. Run focused GUI/core/packaging/docs checks and repository precommit. Visible Qt
   execution requires an approved safe session and is otherwise reported as skipped.
4. Authenticate the exact published v1.5.1 baseline, retain build dependencies, build
   isolated v1.5.2 artifacts, verify patch/full equivalence and GitHub digests, then
   publish and check the public updater feed. Keep release notes to one sentence.

## Progress

- Initial GUI and core focused checks passed. Core already supports non-10 Hz rates;
  the editor lacks a rate field. Exact frame/SOA rules remain authoritative.
- Added the shared rate draft, atomic apply, dynamic timeline/preview timing, and
  full-precision editable SOAs. Animation rejects timer intervals outside its range
  without clamping authored rates. Independent code review found no remaining blockers.
- Core focused: 345 passed, one Windows symlink privilege skip. Atomic document
  rate tests: 24 passed. Packaging focused: 168 passed. GUI non-Qt checks, docs
  hygiene and nine docs tests passed.
- Repository precommit passed Ruff, compilation, mypy, repository audits, and all
  1,356 non-Qt unit tests, with five Windows symlink permission skips. The final process
  used `PYTEST_ADDOPTS=--basetemp=build/u152b` to avoid known Windows temporary-path
  limits without changing the harness. Evidence: `build/release-1.5.2/precommit-final.log`.
- The v1.5.1 baseline matches published GitHub assets and all 8,030 owned files.
  Its exact inventory SHA-256 is
  `9961840684982e9c4ff1f1cce253a6a50250ed40777da77babf46b9e84f85073`.
- Only FPVS Studio metadata changed in the build environment, from 1.5.1 to 1.5.2;
  runtime dependencies were retained.
- SOA validation messages give sufficient precision for non-terminating decimal
  intervals (7.5/12 Hz); a regression reuses the actual suggested interval
  successfully. All 66 core-stream tests passed.
- Final installers were rebuilt from source commit
  `97f3c57a551d3f6234496edae341a9ed569c73e9`. All four changed modules embedded in
  the executable match their source code, and all 8,030 extracted full-installer
  files match the final bundle. The sparse patch has 11 changed/added files and
  eight removals, retaining 8,019 files and reconstructing the exact full target.
  Evidence: `build/release-1.5.2/embedded-module-verification.json` and
  `build/release-1.5.2-artifact-verification/verify-5q_plpfm/report.json`.
- Published [v1.5.2](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v1.5.2)
  as the latest stable release. The public tag points to the verified source commit;
  all three GitHub asset sizes and SHA-256 digests match the final local artifacts.
  Release notes: "Added editable presentation rates for Attentional Blink experiments."
  Evidence: `build/release-1.5.2/published-release.json`.
- Public updater verification passed using production metadata, manifest validation,
  and baseline file hashing. The authenticated v1.5.1 installation selects the patch;
  v1.5.0 and unregistered/source installations select the full installer; v1.5.2
  reports no newer update. Only installation discovery used the extracted baseline
  fixture. No application or installer was launched.
  Evidence: `build/release-1.5.2-artifact-verification/live-ykd3zvgu/live-update-verification.json`.
- Registered GUI coverage includes rate drafts, fractional SOA persistence, invalid
  input, extreme-rate preview behavior, and both-theme wizard geometry. Visible Qt
  tests and packaged GUI smoke remain unrun without approval for a safe visible
  session; manual acceptance steps are in `docs/GUI_WORKFLOW.md`.

## Published Artifacts

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-1.5.2.exe` | 259,071,415 | `795ca89b6a73dc21b2bb0b96a6b100727f903ce2d371045792579c680854b10a` |
| `FPVS-Studio-Patch-1.5.1-to-1.5.2.exe` | 27,614,361 | `2383a3c7867cc28449134d4024effaf2ae17448756c1c4138e73a3ece564ac35` |
| `FPVS-Studio-Update-1.5.2.json` | 435 | `e083f2531be0079283700ba9c7b64cc939f0d55886b638f0d47caed455f72d90` |
