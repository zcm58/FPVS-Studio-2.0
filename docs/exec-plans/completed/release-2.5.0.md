# Studio 2.5.0 release

Status: Completed

Date: 2026-10-26

## Authorized outcome

Publish the Brain Products / BrainVision trigger setup and computer default EEG
hardware workflow, after approved visible GUI checks. Preserve and merge the other
PC's mouse-response fixes and BrainVision labels. Release notes remain brief bullets.

## Acceptance

1. Reconcile both checkouts, then exercise onboarding, recording setup, manual and
   detected COM ports, pulse validation, inheritance and Settings in a visible,
   isolated Qt profile. Repair concrete failures and rerun affected checks.
2. Run packaging focused and repository precommit verification. Record passes and
   skips separately from physical EEG/display validation, which needs lab hardware.
3. Commit version 2.5.0 on master, refresh editable metadata without dependency
   upgrades, and build a full installer plus a direct authenticated 2.4.8 patch.
4. Verify extracted payload hashes, exact patch reconstruction, native dependency
   custody, packaged startup, updater diagnostics and selection. Publish and verify
   remote asset hashes and updater metadata.

## Progress

- Local implementation preserved in f4825d0; remote commits 43cfec7 and 0cd0bc7
  merged in 6b67d09. The documentation merge keeps the updated BrainVision label
  and the new discovery/amplifier/rate fields.
- Visible Qt checks started with the Windows platform and workspace test settings.
  Final combined run passed all 303 selected tests. Screenshots cover the picker
  at 640x300, BrainVision setup at 700x640, Settings at 700x560 and Welcome at
  760x520, including long labels, at device pixel ratio 1.0. Tests also exercise
  both theme palettes. Evidence is under `build/release-2.5.0-evidence/`.
- Visible testing repaired compact Welcome spacing, aligned the onboarding
  BrainVision label, and updated three tests to existing asynchronous behavior.
  A transient Windows clipboard lock passed unchanged on retry and in the final run.
- Packaging focused: 181 passed. GUI safe focused: 83 passed. Documentation: ten
  passed. Ruff, compilation and mypy for all 242 source files pass. Final
  repository precommit passed: 3,464 tests, 12 Windows symlink-permission skips
  and 20 passing subtests, in 780.07 seconds. Packaging ran concurrently with
  this broad suite; publication waited for its successful result.
- Published 2.4.8 baseline installer, signed release/asset attestations and all
  7,989 owned file hashes verified. Dependency versions and reviewed native source
  bytes match baseline. Build-only `editables==0.5` was added to refresh app metadata
  with `--no-deps --no-build-isolation`; `pip check` passes.

## Boundaries

No physical amplifier/TriggerBox, EEG sampling or display timing qualification is
claimed. Clean-machine installation and installed-upgrade/uninstall lifecycle
checks were not performed. No installer was executed on the working machine.
The user's installed app, project roots and preferences remain preserved.

## Release source and build

Release source `9341de5cf1ddcadc289ba518a60c53703ce98550` was committed and pushed on master before publication.
The annotated `v2.5.0` tag resolves to that exact source. Changes include TriggerBox
discovery and pulse validation, computer default EEG hardware and project overrides,
and the other PC's mouse-response capture repairs. Public notes contain three brief
bullets, with no verification or installation section.

The existing Python 3.10.11 environment and runtime dependency versions were
preserved. `build_release.ps1 -SkipInstall -AllowVisibleGui -BuildLabel release-2.5.0`
built the full installer and authenticated direct 2.4.8 patch with Inno Setup 6.7.0.
The build-process PATH excluded unrelated application directories. Studio's packaged
smoke reports version 2.5.0, matching installed metadata, working runtime dependency
imports and fitting controls. The independent updater's backend and visible GUI
smokes passed, without network or installer execution.

## Artifact and dependency acceptance

All 7,987 full-installer payload hashes match the target bundle. The 25 changed or
added patch files plus 7,962 retained files reconstruct that exact target. Twelve
obsolete baseline paths are removed. Target inventory SHA-256:
`c6fbb9782b2831fb34f9980c7ef83bffbdd77bd46a0b26b9b58680531254924f`.

All 242 frozen Studio application modules and 23 updater application/entry modules
match the committed source. All 487 native payload files and reviewed 491 Studio
plus 69 updater native source records match authenticated 2.4.8 bytes. All 4,448
Studio and 126 updater dependency modules match baseline module sets and normalized
code. Both 151-module standard-library ZIPs have matching headers and normalized code.
All 24 dependency METADATA files are byte-identical.

The first strict audit stopped on local pip installation receipts, after proving
full extraction and exact patch reconstruction. A narrowly pinned checker then
verified two added and four removed empty REQUESTED markers and eight changed
RECORD CSVs. Their only row changes concern those markers and seven launcher
receipts for executables absent from both bundles. Every other dependency payload
byte matches, except the equivalent standard-library ZIP. The exact ledger,
inventory hashes and CSV differences are retained in the evidence folder. No
dependency code or native-library change was accepted through this exception.

## Publication and updater acceptance

Immutable release `424912548` is latest stable at
[v2.5.0](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.5.0). Draft identity, notes and all six server asset
digests matched before publication. All six independently downloaded public assets
match audited sizes and SHA-256 values. Signed release and downloaded-file asset
attestations pass for all six assets. These attestations are provenance checks;
Authenticode signing is not configured.

Eleven candidate and eleven live updater cases pass. Authenticated 2.4.8 selects
the direct patch. Older versions, missing inventory, forced full and repair select
the full installer. Current 2.5.0 reports no update, with full reinstall available
for explicit repair. Evidence, screenshots, audit helpers and independent downloads
remain under ignored `build/release-2.5.0-evidence/`; the authenticated baseline is
under `build/release-2.5.0-baseline/`. Release payloads are under
`dist/release-2.5.0/installer/`.

## Published assets

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.5.0.exe` | 300780355 | `287aad020c5d12dc0a3488b498f716deac8241961192941e80aa30678a7539b4` |
| `FPVS-Studio-Setup-2.5.0.exe.sha256` | 95 | `e70d70cf1d9a99ab26d816bbc90b87583fe45b5564f8ba773176cc1cd5d450fe` |
| `FPVS-Studio-Patch-2.4.8-to-2.5.0.exe` | 72436197 | `7dbb515534e33230267d7717e79e19538f4d7027da682d92134e386abb62b1b5` |
| `FPVS-Studio-Patch-2.4.8-to-2.5.0.exe.sha256` | 104 | `559e75a3e971d9a703ad374f4ec3232c3eab27a171f014ac001f550af1ad040e` |
| `FPVS-Studio-Update-2.5.0.json` | 435 | `8b84a5eab2db6dc32c752cdeb69cc6d78b7cc00b301413fb19fb8022cf5c4ee6` |
| `FPVS-Studio-Update-2.5.0.json.sha256` | 97 | `dca5dd1f7cb962bd59ae1e5d7662a1029e00cac15538efb022134835baf12420` |
