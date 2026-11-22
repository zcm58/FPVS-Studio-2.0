# Windows release patches and acceptance

Status: Completed

## Release workflow

Build the full Windows x64 setup for every release. Stable releases may add direct
patches from up to five preceding patch numbers within the same major and minor
version. Count the numeric gap even when releases are missing. Each patch needs a
previously published immutable stable Windows x64 baseline, its authenticated
ownership inventory, and compiled bytes strictly smaller than setup. Reuse the
builder's matching arrays of baseline inventories and hashes, installer checks and
updater selection.

For 3.1.5, versions 3.1.0 through 3.1.4 can qualify. The full installer handles
3.1.0 to 3.2.0, 3.1.0 to 3.1.6, same-version repair, and installations without a
compatible patch. Each patch goes directly from its exact baseline to the target.

Use one manually dispatched Windows job to check an exact release draft.
Authenticate the annotated tag, published baselines and draft assets before
running any installer. Exercise fresh setup and full upgrade from the previous
stable Windows version, including across minor versions, with uninstall after each.
On the disposable hosted runner, install a fresh exact baseline for each offered
patch, apply that patch and uninstall. Compare installed ownership, confirm obsolete
files are removed and preserve project, settings and unrelated-file sentinels.
Keep packaged Studio and updater smoke reports with the install logs.

## Boundaries

Reuse the existing local build, source CI, DLL origin audit and public release
attestation checks. Keep publication separate from acceptance. This work leaves
existing releases and version metadata unchanged.

## Initial one-patch verification

- The retained 3.1.3 and 3.1.4 builds produced a 72,802,895-byte patch with
  Inno Setup 6.7.3. Compared with the 299,556,194-byte full installer, it saves
  226,753,299 bytes per eligible download (75.7%). It carries 13 changed or
  added files, retains 7,057 and removes ten. The measurement used the
  authenticated published installer hashes and hosted ownership inventories.
  This patch was compiled locally for measurement.
- Local verification passed 12 simulated draft cases, including full-only and
  patch drafts, the cutoff, integrity failures and an oversized patch. YAML
  and PowerShell parsing passed. The v3.1.3 installer passed GitHub's asset
  attestation check.
- Packaging passed 215 tests. The updater passed 377 with four Windows
  symlink-permission skips. Docs passed 13. The native synthetic Inno
  lifecycle passed all 15 cases, including patch parity, refusal, repair and
  uninstall.

## Five-patch verification

- The draft check passed 27 simulated release cases, including five patches,
  sparse patch sets, full-only drafts, skipped release numbers, rejection at the
  minor boundary, rejection beyond five revisions, and tampered assets.
- The existing updater selected the exact patch in all five 3.1.5 upgrade
  scenarios. It selected setup for 3.0.9 to 3.1.5, 3.1.0 to 3.1.6, and
  3.1.0 to 3.2.0.
- Workflow YAML and PowerShell parsed. Packaging passed 215 tests, updater
  passed 377 with four Windows symlink-permission skips, and docs passed 13.
- Exercise the workflow against a new draft in hosted CI before the first
  release using this policy. Record the exact assets and run link.

## Hosted 3.1.5 qualification

The [hosted acceptance run](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/45052929017)
authenticated all 14 draft assets and five published baselines. It verified a
fresh install, a full upgrade from 3.1.4, one direct upgrade from each of 3.1.0
through 3.1.4, and uninstall after all seven routes. Every target installation
matched the same 6,918 owned files and preserved the project, settings, and
unrelated-file sentinels.

The full installer is 282,494,129 bytes. The five direct patches range from
72,779,424 to 73,000,976 bytes. Release evidence and the target inventory hash
are in the [3.1.5 release record](release-3.1.5.md). The production updater
selected all five exact-baseline patches and verified full fallback and repair.
