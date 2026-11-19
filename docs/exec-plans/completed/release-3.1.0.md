# Studio 3.1.0 release

Status: Completed

[FPVS Studio 3.1.0](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v3.1.0)
was published as the latest stable immutable Windows x64 release on November 19,
2026 at 19:56:24 UTC, GitHub release ID `451840732`. The tag resolves to
`d509713af37d7406d3bf764150a5070b3e6880b2`.

The Studio bundle was built from `5191069814a11eac0b5e7837ce0e691727aa1d65` using
the existing pinned environment. The only intervening edits were the updater
spec and its regression test. The updater and installer were built after adding
the shared progress control to the updater allowlist.

- The packaging, updater, GUI and docs focused scopes passed. The approved
  Windows desktop ran 246 visible Qt tests and the full packaged Studio and
  Update & Repair smoke checks. The exact-source Windows contracts and transfer
  fixture passed in [CI](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/44599849641).
- The DLL-origin audit passed for 492 Studio and 69 updater files. The authenticated
  3.0.1 baseline matched all 491 shared Studio and all 69 updater native files.
  The added native file is the `websockets` speedups extension.
- A [disposable Windows run](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/44602335434)
  verified a fresh install, upgrade from 3.0.1, installed Studio runtime and
  uninstall. Both installs matched all 7,995 owned files. The upgrade removed old
  package metadata while preserving test settings, project data and unrelated
  files. The full-size Library dialog passed on the native desktop where the
  requested geometry was available.
- All four public downloads matched the draft digests and passed GitHub asset
  attestation verification. The extracted 3.0.1 updater offered the new full
  installer and showed the project-versioning highlight.

The 301,603,233-byte installer has SHA-256
`4c5fedfbc74efac93e8bba4904697886dd6c1381d0a7ab48492c82084b37b266`.
Build and publication evidence is retained under `build/release-3.1.0-evidence/`
and `build/release-3.1.0/installer-inventory/`.
