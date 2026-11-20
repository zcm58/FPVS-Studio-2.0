# Studio 3.1.2 release

Status: Completed

[FPVS Studio 3.1.2](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v3.1.2)
was published as the latest stable immutable Windows x64 release on 2026-11-20
at 16:34 UTC. Release ID is `452925678`. The tag points to
`106e18af24309412253bd20443b0e5e824bf014d`.

- Setup refreshes the active Conditions list once per edit and defers the other
  views. Manual creation offers FPVS-Oddball and disabled Standard FPVS. The
  release also reduces redundant recovery, launch preflight, and reporting work.
- The local packaged Studio and updater smoke checks passed. The 215 packaging
  tests and 384 updater tests passed, with four Windows symlink skips. Native
  origin audits covered 492 Studio files and 69 updater files.
- The [hosted Windows run](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/44773833999)
  checked all 7,995 owned files after fresh install and upgrade from 3.1.1. It
  verified uninstall and preservation of settings and project sentinels. The
  hosted desktop limited the Library dialog to 1028 × 749. The local packaged
  smoke check passed at the requested size.
- All four public assets matched the draft digests and passed GitHub release
  attestation verification. The live updater offered the full installer to
  3.0.1 and 3.1.1 and reported 3.1.2 as current.

The 301,590,249-byte full installer has SHA-256
`67d06460275d92a30094678fb8f588e7147995e562663d82a370d7d3724f0d8c`.
The public assets are retained in `dist/release-3.1.2/publication/` and the
verification evidence in `build/release-3.1.2-evidence/`.
