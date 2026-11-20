# Studio 3.1.3 release

Status: Completed

[FPVS Studio 3.1.3](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v3.1.3)
was published as the latest stable immutable Windows x64 release on 2026-11-20.
Release ID is `453150394`. The tag points to `acded61388da131c50a7060560361166bd763183`.

- The update dialog wraps long release notes and lets users scroll the preview
  while keeping download progress and actions visible.
- The 215 packaging tests and 377 updater tests passed, with four Windows symlink
  skips. Archive inspection found the wrapping fix in the frozen app. The packaged
  updater passed its headless diagnostic. Visible checks were skipped as requested.
- Native origin audits covered 487 Studio files and 69 updater files. All 483
  DLLs and Python extensions shared with the verified 3.1.2 inventory matched by
  hash. The build environment omitted Tcl/Tk and two CPython test extensions.
- The [hosted Windows run](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/44812221241)
  passed silent fresh install, upgrade from 3.1.2, and uninstall. It verified all
  7,070 owned files and confirmed preservation of settings and project sentinels.
- All four draft assets matched the local sizes and hashes. The downloaded
  public assets matched the build and passed GitHub attestation verification.
  The live updater offered the full installer to 3.1.1 and 3.1.2 and reported
  3.1.3 as current.

The 299,563,496-byte full installer has SHA-256
`2e345061265e3c16570630d4c73561279e8099a22111c070c2181e17716aecb9`.
The build assets are retained under `dist/release-3.1.3/installer/` and the
verification evidence under `build/release-3.1.3-evidence/`.
