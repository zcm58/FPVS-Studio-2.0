# Studio 2.4.7 crash recovery release

Status: Completed

Date: 2026-10-24

## Authorized outcome

Build and publish the Studio graphics crash repair and interrupted-condition recovery
as version 2.4.7. Work used the isolated `fix/crash-condition-recovery` worktree;
unrelated edits and the environment in the primary checkout were preserved. The full
installer and direct 2.4.6 patch include the independent updater. All six release
assets are published; the installed application was not replaced during this task.

## Source and verification

Release source `8547d7a9ebbe8a26235f62de4b3e0ffbdbcf2d4c` was committed and pushed
to master before the final canonical build. It includes graphics-thread cleanup,
chained-exception cleanup, local condition recovery and an explicit Windows packaging
exclusion that preserves the published OpenMP policy. The annotated `v2.4.7` tag
resolves to that exact commit.

- Final application precommit: 3,198 passing tests, 20 passing subtests and 12
  Windows symlink-permission skips, in 496.93 seconds. Ruff, compilation, mypy and
  repository audits pass. Log: `build/crash-recovery-release-precommit.log`.
- Engine focused: 389 passing tests, including chained and suppressed constructor
  errors that must release native locals on the graphics thread.
- Safe GUI focused: 17 passing tests; registered visible tests remain unexecuted.
- The final packaging-spec follow-up passes 181 focused tests, including executable
  Windows/Linux spec checks, plus Ruff and compilation.
- The actual Cognitive Decline acquisition receipt was queried read-only and its
  hash retained: run six was interrupted after five completed runs.

The [recovery implementation record](crash-condition-recovery.md) describes the
incident evidence, ownership boundaries and remaining visible acceptance.

## Build environment and baseline custody

The authenticated baseline is immutable release `v2.4.6`. Its full installer has
size 300,721,672 bytes and SHA-256
`f3bea0e8bf2fe63cbab258c000a081e14e959c5cfe291f08710e211ee0c4949b`.
All 7,987 owned-file hashes pass, and its inventory SHA-256 is
`05075c4977e36538aa03704b36ae731438bf8627ed54c940996378a0772f30fb`.
The installed inventory independently has the same digest. Baseline GitHub release
and asset attestations pass.

The isolated environment uses the existing PsychoPy Python 3.10.11 base with system
site-packages excluded. Its Python DLL, 346 collected standard-library modules, five
Python/Tcl/Tk native files and 922 Tcl/Tk data files match the authenticated baseline.
The initial copied environment's stripped Python base could not reproduce those
files; that candidate was rejected before publication.

Eight isolated dependency installations were restored from hash-locked wheels whose
513 collected modules match the baseline: pytest 9.1.1, Pygments 2.21.0,
beautifulsoup4 4.14.3, arabic-reshaper 3.0.0, markdown-it-py 4.0.0,
platformdirs 4.9.6, tomli 2.4.0 and trove-classifiers 2026.1.14.14. These versions
satisfy the existing security floors; exact-version OSV/PyPI checks reported no
advisories. `pip check` passes, and Studio source and installed metadata resolve to
the isolated worktree and version 2.4.7.

The Windows spec explicitly excludes optional `threadpoolctl`: its presence in the
copied environment otherwise introduced an import-time `KMP_DUPLICATE_LIB_OK`
change. NumPy and SciPy support its absence. This restores the exact baseline
dependency graph; Linux collection is unchanged. See [Packaging](../../PACKAGING.md).

The canonical build used Inno Setup 6.7.3, a restricted process `PATH` containing
only required verified native directories, and these release arguments:

```powershell
.\scripts\build_release.ps1 -SkipInstall -SkipSmoke `
  -BuildLabel release-2.4.7 `
  -InnoCompiler "$env:LOCALAPPDATA\Programs\Inno\ISCC.exe" `
  -BaselineInventory 'build/release-2.4.7-baseline/extracted/{app}/fpvs-owned-files-v1.txt' `
  -BaselineInventorySha256 05075c4977e36538aa03704b36ae731438bf8627ed54c940996378a0772f30fb
```

The extractor SHA-256 is
`1c8453c198dd3fe7947f3705e59d2294ddce3dfa9f96a737e94449b119f44181`.
Authenticode is not configured. GitHub's signed immutable-release attestations
authenticate the published tag and assets; they are not Authenticode signatures.

## Artifact and publication acceptance

The extracted full installer matches all 7,989 target owned-file hashes. The direct
2.4.6 patch reconstructs the exact target with 31 changed/added files, 7,958 retained
files and ten removals. The target inventory SHA-256 is
`520ebb0394aa538de6e8adf196534a2c931aa6b6414ae15d5bf2ae12232cbd3b`.

All 240 frozen Studio modules, 22 updater modules and both entry points match the
source commit. All 4,448 Studio and 126 updater dependency modules match the baseline
set and normalized code. All 487 native payload files, 491 Studio native analysis
inputs and 69 updater native inputs match authenticated baseline bytes. Both
151-entry standard-library ZIPs match their baseline module headers and code.
The updater's non-GUI packaging diagnostic confirms frozen version 2.4.7, protocol 1
and no GUI imports.

Non-application payload differences are limited to six empty installation-request
markers and eight RECORD files. Their reviewed row differences concern those markers
and seven environment-specific script launchers that are not bundled. Every other
row group matches, including the duplicate NumPy bytecode row already present in the
baseline. These explicit metadata exceptions permit no changed runtime bytes.

Immutable release `422854499` is published as latest stable at
[FPVS Studio 2.4.7](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.4.7).
The exact title, release-note bullets, source tag and all six uploaded asset sizes
and digests passed draft verification before publication. Public anonymous metadata,
the update manifest, all six downloaded asset hashes and signed release/asset
attestations pass.

Eleven candidate and public updater cases pass: authenticated 2.4.6 selects the direct
patch; older versions, missing registration/inventory, forced full and repair select
the full installer; current 2.4.7 reports no update, with full reinstall available
for explicit repair. Evidence and rejected-candidate diagnostics are retained under
ignored `build/release-2.4.7-evidence/` and isolated release build directories.

## Published assets

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.4.7.exe` | 300764605 | `2c08d51976796dcb38dfffa939eef1724aea2f81b88385c568d54a4a5ffae1bd` |
| `FPVS-Studio-Patch-2.4.6-to-2.4.7.exe` | 72433368 | `44fc72834fb6c66d98fbf9bf23276538e6eeecb9351d7baca7b6d9650199785c` |
| `FPVS-Studio-Update-2.4.7.json` | 435 | `0009eed1669e4b0a8eaa68015f8f9e94a6b321a6dda7802b94b395fdf9544290` |
| `FPVS-Studio-Setup-2.4.7.exe.sha256` | 95 | `f4ff8c78e60e954031a8e768d6528d75332287b3445b5fed3c3b5052a939110b` |
| `FPVS-Studio-Patch-2.4.6-to-2.4.7.exe.sha256` | 104 | `09e5eed892e956f761bc2584c83b3f8503700217cb38a6cdff79050028c7b303` |
| `FPVS-Studio-Update-2.4.7.json.sha256` | 97 | `4da6da68d3d79198c21ba379ba845071f4176bfac57e806d511399d4bd752df9` |

## Remaining qualification

Visible Qt and native graphics checks were requested but not approved or executed.
No offscreen Qt tests, real EEG markers, research uploads, installed upgrade or
clean-machine installation were performed. Physical display and hardware timing
remain separate qualification. Source checks and artifact verification do not prove
that every possible native crash is eliminated.

Automatic crash email remains unavailable because the separate deployed feedback
service has not activated registration/intake. Local condition recovery works
independently. Backend activation remains in the
[automatic crash-reporting plan](../active/automatic-crash-reporting.md); this release
does not deploy that service.
