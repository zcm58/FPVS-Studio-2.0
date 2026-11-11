# Studio 3.0.0 release

Status: Completed

[FPVS Studio 3.0.0](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v3.0.0)
was published as the latest stable immutable Windows x64 release on November 11,
2026 at 22:19:35 UTC, GitHub release ID `442249402`. The release leads with
Recorder 2 support. The operator verified the Trigger Tester and marker sending
on a 2026 actiCHamp setup with Recorder 2 and a USB TriggerBox.

The installer was built from `82e70bc0c860e28b1b507a7529b308119bf04081` with
the pinned 2.9.1 environment. The GitHub tag resolves to that commit.

- Documentation hygiene and context-budget checks passed. Focused checks
  passed 212 packaging tests and 180 GUI unit tests. All 17 visible Trigger
  Tester tests passed at 560 × 340 and 100% scaling with simulated hardware.
- Packaged Studio and updater smoke checks passed. Frozen Trigger Tester and
  discovery modules matched the tagged source. The exact-source [Windows
  contracts and transfer fixture](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/43108871844)
  passed.
- The extracted installer matched its inventory for all 7,987 owned files.
  The 491 third-party Studio native files and 69 embedded updater native files
  matched the authenticated 2.9.1 baseline. The pre-upload DLL-origin audit
  passed against the exact release assets.
- All four public downloads matched the draft digests and passed GitHub asset
  attestation verification. The 2.9.1 updater selected the new full installer
  and showed the Recorder 2 release highlight.

The 301,216,488-byte installer has SHA-256
`c0df7ef00ee6bc8a753427ed427904340b2abb282b92f526e3d6283a83de190d`.
Build and publication evidence is retained under the isolated checkout's
`build/release-3.0.0-evidence/` and `build/release-3.0.0/installer-inventory/`.
