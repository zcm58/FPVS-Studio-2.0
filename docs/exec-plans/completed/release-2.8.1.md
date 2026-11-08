# Studio 2.8.1 release

Status: Completed

The user requested the next GitHub release. Bump the source from 2.8.0 to
2.8.1 for the Condition Figure updates after the 2.8.0 draft. The public release
also includes Trigger Tester, questionnaire editing, per-project Brain Products
setup and menu dividers since the public 2.7.4 release. Retain the earlier draft.

## Release gates

1. Commit and push the versioned source. Run packaging-focused verification,
   exact-source local precommit, and GitHub source and documentation checks.
2. Build the full Windows installer in an isolated checkout with the preserved
   dependency versions. Verify bundled versions, exact-source modules, and
   installer payload against its ownership inventory.
3. Stage the full installer, an update manifest with an empty patch list, and
   both SHA-256 sidecars in a new draft. Check the source target, asset bytes
   and candidate updater selection.
4. Run the packaged Studio and updater diagnostics in an approved visible
   Windows session. Use synthetic inputs with network and installer actions
   disabled.
5. Publish the verified draft as latest and immutable. Verify public downloads,
   release and asset attestations, and live updater selection. Archive this plan.

## Release acceptance

Built from `2155c0f9d262944315603743a913bd6af1726105` in an isolated
checkout. The build preserved all 144 non-Studio dependency versions from
the prior isolated environment. The first build picked up native files
through the host PATH. The final `release-2.8.1-clean` build used a restricted
PATH and replaced the installer and checksum in the draft before publication.

- Packaging-focused checks passed 192 tests. Exact-source local precommit
  passed 5,788 tests and 24 subtests, with 33 platform or permission skips.
- Installer extraction verified all 7,989 owned files against the staged
  manifest. The manifest SHA-256 is
  `54f2a048ee3146c273061b7e33f86c1927dc31ff300174c1642d5c0c089165b6`.
  The 283 Studio and 24 updater modules match the release source. The 487
  native and 922 Tcl/Tk files match authenticated 2.7.4.
- The approved visible Studio diagnostics passed 58 workflow states,
  packaged version checks, runtime imports, and layout checks. The
  independent updater passed its backend, update, and repair diagnostics
  with network and installer actions disabled.
- All six exact-source CI jobs passed, including Windows and both Mac
  architectures and their fixture round trips. Documentation build and
  deployment passed. [Source CI](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/42495213868)
  · [Docs CI](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/42495213873)

## Publication and verification

Release ID `438340413` was published as latest, stable, and immutable at
`2026-11-08T16:01:51Z`. The annotated tag resolves to the exact source
commit. Candidate and live updater selection each passed ten cases.
Public downloads matched all four local assets, and GitHub verified the
release and all four asset attestations.
[FPVS Studio v2.8.1](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.8.1)

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.8.1.exe` | 301,157,567 | `8746959c4eedd996eb29a320c078c05d46988391459195b28271984638c094c6` |
| `FPVS-Studio-Setup-2.8.1.exe.sha256` | 95 | `2794847a3a96e773a32a4f8a9d5519cb406808ff69e3d00d66bb4501129482dd` |
| `FPVS-Studio-Update-2.8.1.json` | 107 | `577ae003f432b9c8bd5ad30034f7ea94dbfe1ab2b95df126008fbda670856210` |
| `FPVS-Studio-Update-2.8.1.json.sha256` | 97 | `cea667e380856832a1aa9d852d11309d8bc44c8dc46a756cf0bb9b57e99cdc0f` |
