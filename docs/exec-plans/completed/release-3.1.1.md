# Studio 3.1.1 release

Status: Completed

[FPVS Studio 3.1.1](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v3.1.1)
was published as the latest stable immutable Windows x64 release on 2026-11-19 22:30:31 UTC.
The release ID is `452002251` and the tag resolves to `ba631d9badc25437f4ffaaf25249000474222175`.

- The packaged cursor module matches the tagged source. The native DLL origin
  audit covered 492 Studio files and 69 updater files. The Studio native
  payload matched the authenticated 3.1.0 installer inventory.
- The [disposable Windows installer run](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/44628226239) verified fresh installation,
  upgrade from 3.1.0, and uninstall. Both installations matched all 7,995
  owned files. The upgrade and uninstall preserved settings and project
  sentinels. The hosted desktop capped the Library dialog at 1028 × 749.
- All four public assets matched their draft sizes and SHA-256 digests and
  passed GitHub release attestation verification. The production updater
  selected the full installer from 3.1.0 and 2.9.1. A current 3.1.1 check
  reported that the installation was up to date.
- All 215 packaging tests passed across the focused run and serial retries.
  The updater suite passed 383 tests with four Windows symlink skips. Its local
  subprocess timing test exceeded five seconds during interpreter startup.
  Direct measurement recorded 0.24 seconds between the first phase and cancellation.

The 301,591,571-byte installer has SHA-256
`4416a06f8151c00671c93c59dcaf56359f8b6853a651f6bced3fe08cc8a33685`. The installer and its sidecars are retained in
`dist/release-3.1.1/installer/`. Build, lifecycle, and publication evidence is retained in `build/release-3.1.1-evidence/`.
