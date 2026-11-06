# Studio 2.7.4 release

Status: Completed

## Scope and authorization

The user requested bundling and publishing 2.7.4 after the committed serial-error
and BioSemi recovery changes in `c93c7b3`. Publish a full Windows installer and
update manifest, as in 2.7.3. No direct patch baseline is newly promised.
Existing approval covers visible simulated GUI and packaged diagnostic checks.
Do not execute a production installer, access actual COM ports, install vendor
software, or claim physical EEG receipt or timing qualification.

Preserve user-owned untracked files, previous release evidence and temporary
directories whose cleanup was blocked. Build only the exact committed source in
an isolated checkout with the existing dependency versions.

## Gates

1. Bump canonical metadata, run packaging focused checks, and commit/push the
   release candidate. Verify the previously tested implementation is unchanged.
2. Run exact-source precommit and CI. Build the full installer, compare frozen
   source and dependencies with authenticated 2.7.3, and verify its complete payload.
3. Run approved visible packaged Studio and independent updater diagnostics,
   without network actions or installer execution, plus candidate updater selection.
4. Stage four assets and concise bullet-only notes in a draft. Verify source/tag,
   asset sizes and hashes before publishing immutable/latest. Verify public
   downloads, release attestations and live updater selection; archive this plan.

## Evidence

- Prior implementation: 5,699 safe tests passed, 32 platform/permission skips and
  24 passing subtests. All 24 Python/config/test files in the saved verification
  snapshot match the committed implementation; this release changes metadata/docs.
- Packaging baseline and versioned candidate: 192 passed each. Evidence is retained under
  `build/release-2.7.4-evidence/`.
- Physical hardware, installed-upgrade and another-PC checks remain unperformed.

## Release acceptance

Source `a8068c3d7cc089cbc8e5f9a181e3b14ef788dcc2` was committed and pushed to
master before packaging, then bound to annotated `v2.7.4`. The clean isolated
checkout `C:\Users\zcm58\fa274` built label `release-2.7.4`. All non-Studio
package versions match the authenticated 2.7.3 environment. The untracked
standalone source example was excluded from the build.

- Final exact-source precommit: **5,699 passed, 32 platform/permission skips,
  24 passing subtests**, in 753.39 seconds. Repository/document audits and
  Windows (274 source files) and Mac adapter (9 files) type checks passed.
- The initial local suite recorded two Windows file-access failures in unchanged
  `test_library_origin.py` and `test_serialization.py`: a denied import-directory
  rename and extra real file-replacement retries beyond simulated locks. Both
  modules then passed unchanged (35 passed, two symlink-permission skips), followed
  by the fully passing precommit run after packaging. No source or test changes
  were made to dismiss these failures; both run logs remain in the evidence folder.
- All **7,987 extracted installer files** match the staged ownership inventory,
  SHA-256 `1016f30bd31fa805e37641111048e2fc36a9b92fbd6fc6a3048edcb6b8d7c759`.
  All **274 Studio and 25 updater embedded modules** match committed source.
  Third-party code, native inputs, bootstrap and standard-library content match
  authenticated 2.7.3. The same 21 build warnings remain; none were added.
- Approved visible packaged Studio passed startup, frozen/metadata version 2.7.4,
  runtime imports and control/layout checks. Independent updater update/repair
  diagnostics passed with network and installer actions disabled; both screenshots
  were inspected. Ten candidate updater-selection cases passed.
- [Exact-source CI](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/42224855992)
  passed Windows, Intel/Apple Silicon Mac, Mac exports on Windows and both
  Mac-origin return checks. [Documentation CI](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/42224856083)
  passed build and deployment.

## Publication and public verification

[v2.7.4](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.7.4) was
published at `2026-11-06T13:55:36Z` as latest, stable and immutable, release ID
`436556934`. Source/tag identity, concise bullet-only notes and all four draft
asset hashes and sizes were checked before publication. No direct patches were
promised; the update manifest explicitly contains an empty patch list.

Independent public downloads match every local asset's size and SHA-256.
The release and all four asset attestations verify. Ten live updater cases passed,
covering previous versions, unregistered installs, explicit repair, the current
version with no update, and rejection of a downgrade from a newer version.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.7.4.exe` | 301,068,589 | `a1b9b5cb1d5e6238b3a95cac330b5b44adc97f6ec712dde29c334a61b5afe5bc` |
| `FPVS-Studio-Setup-2.7.4.exe.sha256` | 95 | `e243685f7745338d4268852257bbdd401d76a8e05309c02c0cceecf7469c7414` |
| `FPVS-Studio-Update-2.7.4.json` | 107 | `d4431637705be5f052e42f54770b62686ec279592ee9d6daf4ea6cb6c219f83b` |
| `FPVS-Studio-Update-2.7.4.json.sha256` | 97 | `95bd0d34e0ba91dfcd7fb621ff4561545a46fc27483232032280d8902e75d2c3` |

No production installer, vendor tools or actual COM port was used. Physical EEG
receipt and electrical timing remain separate hardware qualification tasks. The
source changes and their simulated/visible coverage are recorded in
[Serial errors and BioSemi recovery](serial-errors-biosemi-recovery.md).
