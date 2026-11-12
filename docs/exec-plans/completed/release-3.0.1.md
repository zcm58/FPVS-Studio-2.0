# Studio 3.0.1 release

Status: Completed

[FPVS Studio 3.0.1](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v3.0.1)
was published as the latest stable immutable Windows x64 release on November 12,
2026 at 13:11:05 UTC, GitHub release ID `442962321`. The release uses manual
physical screen width calibration. Display detection fills pixel resolution
and refresh rate.

The installer was built from `87ef04ed683e0aaa16a3334fd9fe42b5e8995e58` with
the pinned 3.0.0 environment. The GitHub tag resolves to that commit.

- All 16 focused visible Qt tests passed on Windows at 100% scaling, including
  the import and macOS local test dialogs at minimum and default sizes. The
  macOS cases used simulated display metadata.
- All 212 packaging tests, packaged Studio and updater checks, and the exact-source
  [Windows contracts and transfer fixture](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/43222642621)
  passed. Both frozen display dialogs matched the tagged source.
- The extracted installer matched its inventory for all 7,987 owned files. All
  491 Studio and 69 embedded updater native files matched the authenticated 3.0.0
  baseline. The pre-upload DLL-origin check passed.
- The release and all four public downloads passed GitHub attestation and digest
  verification. The 3.0.0 updater selected the 3.0.1 installer and displayed
  the manual width calibration highlight.

The 301,211,547-byte installer has SHA-256
`1dc1533654758be167074583f79c70d7227da369169efeea6091e322e2c5083c`.
Evidence is retained under the isolated checkout's `build/release-3.0.1-evidence/`
and `build/release-3.0.1/installer-inventory/`.
