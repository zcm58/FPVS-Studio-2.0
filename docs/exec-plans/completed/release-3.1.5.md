# Studio 3.1.5 release

Status: Completed

## Scope

Ship the November 22 efficiency work as the next Windows x64 patch release.
The next patch version is 3.1.5. Build the full installer from the exact tagged
source and prepare direct patches from published stable versions 3.1.0 through
3.1.4 using authenticated installed ownership inventories. Offer each patch
only when its compiled download is smaller than the full installer.

## Verification

- Run Windows and macOS source verification and bidirectional project transfer
  checks for the exact release commit.
- Audit both frozen packages' DLL origins and compare the full installer with
  a reference that adds back only the excluded Windows Builder examples.
- Authenticate the draft tag, inventory and assets and run the standard hosted
  installer verification. Check fresh install, full upgrade, each direct patch,
  preservation of projects and settings, and uninstall.
- Publish the verified draft separately from acceptance. Check the immutable
  public release and each asset attestation, download hashes, and production
  updater selection for direct patches, full fallback, repair, and current users.

Release acceptance uses disposable hosted Windows. Synthetic playback and
physical presentation or timing evidence are recorded separately.

## Release evidence

GitHub published [FPVS Studio 3.1.5](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v3.1.5)
as the latest stable immutable Windows x64 release on 2026-11-22 at 18:24 UTC.
Release ID `454635560` and annotated tag source
`37e258d955c0f06cf3013b5c3934acf29585b3c5` match the accepted draft.

- Local precommit passed 6,623 tests with 41 platform or permission skips.
  Packaging passed 216 tests and Updates passed 377 tests with four skips.
  [Docs CI](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/45050892864) passed.
- The [exact-source rerun](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/45051836856)
  passed all six jobs, including 6,636 Windows tests with 28 skips and
  24 passing subtests, 2,005 tests on each Mac architecture with 14 skips each,
  and both directions of project transfer. The first Windows workflow lost a
  test worker. The rerun kept the same source and reduced Windows concurrency
  from four to two workers with a 120-second default watchdog.
- Both native origin audits passed, with 485 Studio and 69 updater entries.
  The [Windows installer run](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/45052929017)
  verified all 6,918 owned files, obsolete-file removal, and preservation of
  project and settings files on fresh install, full upgrade, and all five
  direct patches. All seven uninstall checks and installed updater smokes
  passed. The Library preview and PsychoPy calibration checks passed.
- The hosted desktop limited one Library test to 1,028 × 749. The fullscreen
  Test Mode fixture compiled to 50 frames and stopped at the hosted OpenGL
  version limit. The accepted rerun used the same tagged artifacts and a test
  script that records the specific host error separately.
- The 14 downloaded public assets matched the staged hashes and passed GitHub
  attestation. One checksum sidecar passed on retry after a Sigstore verifier
  initialization error. The production updater selected the exact direct patch
  from each supported baseline. Full fallback, forced full update, repair, and
  detection of the current version also passed.

The full installer is 282,494,129 bytes with SHA-256
`257090da19872de76890e60b839e0f10a5cbf79e905953eaa2563c298639c3d4`.
The target ownership inventory SHA-256 is
`a99f94466a9c06e4c9b227a4ca4b0b907aabf401fd54f46f876abc756999657e`.
Patch sizes and retained artifacts are below.

| Exact update source | Direct patch bytes |
| --- | ---: |
| 3.1.0 | 73,000,807 |
| 3.1.1 | 73,000,976 |
| 3.1.2 | 73,000,751 |
| 3.1.3 | 72,811,988 |
| 3.1.4 | 72,779,424 |

Local installer artifacts are under `dist/release-3.1.5/installer/` and the
accepted receipts, reports, and public verification evidence are under
`build/release-3.1.5-evidence/`.
