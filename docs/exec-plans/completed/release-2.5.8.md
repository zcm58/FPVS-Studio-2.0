# Studio 2.5.8 Release

Status: Completed

Published November 1, 2026 as the latest stable immutable release:
[Studio 2.5.8](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.5.8).

## Problem and scope

Birth Control's four conditions share normal condition instructions, with no task
modules or authored instruction geometry. The saved project compiles to eight
runs. Runtime adds the block/item label to its authored instruction body.
Installed Arial metrics estimate nine wrapped lines at the old 1200 px width;
the body overlaps the heading by about 35 px even at 1920x1080. This is a shared
Studio text-screen layout defect, not a project-specific modifier or setup error.

Replace fixed text centers with measured heading/body/footer flow inside the
actual viewport. Use explicit pixel units and top anchors, remeasure after font
or wrapping updates, and reflow only for viewport/countdown changes. Preserve
one-time stimulus construction, all cleanup paths, wording, keys and countdowns.
Fit exceptional overflow only to a readable minimum, then report an actionable
error. Do not silently clip, delete text or introduce instruction pagination.

Leave local study JSON, stimuli, timing, triggers and participant data unchanged.
The renderer fix applies to all experiments using ordinary instruction, transition,
break, feedback and completion screens. No project bundle update is required.

## Verification and release

Add non-Qt rendered-bounds regressions using the Birth Control text, several window
sizes, resizing, countdown changes, fitting and explicit overflow.
Preserve resource reuse and error/abort cleanup coverage. Run engine focused,
repository precommit and packaging focused checks.

Ship as the next patch in the ongoing authorized Studio release workflow. Change
only canonical package version to 2.5.8, refresh editable metadata without changing
dependencies, and build with the canonical release script under an isolated label
and constrained native PATH. Compare warnings/native paths/hashes with 2.5.7.
Audit frozen source and the complete inventory, verify all four draft assets,
publish immutable/latest and check independent public downloads, attestations and
the production updater. Retain evidence in `build/release-2.5.8-evidence/`.

No Qt/PsychoPy windows or installers are run on the working installation. Visible
presentation, clean-PC installation, update lifecycle and physical timing checks
remain separate from non-Qt/static evidence. No claim of native screenshot
verification is made from font-metric estimates or fake rendered bounds.

## Progress

- Pulled master; clean and current at `0251743` before the repair.
- Engine focused baseline: 547 passed.
- Shared renderer now measures and separates instruction blocks. Twelve new
  regressions include the exact Birth Control text; all four viewport cases fail
  against the old renderer. Engine focused passes 559 tests, and participant input
  passes 41 tests after updating older fake stimuli to expose measurement APIs.
- All eight actual compiled study screens pass 32 simulated viewport/layout cases;
  project JSON remains byte-identical. Independent dependency/API review found no
  Windows blocker. No native window was launched.
- Packaging focused passes 183 tests; config checks pass all 14 scopes. Only
  editable application metadata changed among 145 distributions, and `pip check`
  passes.
- Final repository precommit passes Ruff, compilation, mypy over 261 source files,
  audits and 4,584 non-Qt tests, with 13 Windows symlink-privilege skips. Docs focused
  passes 13 tests. An earlier broad run encountered the existing temporary import
  staging-directory rename failure (`WinError 5`); its isolated rerun and the final
  full gate both pass. No import implementation was changed for this text repair.
- Build, artifact audits, immutable publication and public verification completed.

## Built and published artifacts

All 7,062 bundle files match the complete ownership inventory, SHA-256
`ba5a244fe0d0c1e49c03a04f3160cd1fa54b0b80a617e314ba0aabba48e5cc7d`.
Studio and updater metadata both report 2.5.8. The updater's frozen diagnostic
passes with protocol 1 and `gui_loaded=false`.

All 261 frozen Studio modules plus entry and all 22 updater modules plus entry
match compiled release source. A separate required-module check confirms the
repaired instruction renderer is present and source-equal without executing it.
All 486 Studio and 69 updater native source paths/hashes, and all 22 normalized
build warnings, exactly match the preserved 2.5.7 audit. The five known optional
MeshPy/PyTables warnings remain as described in the
[2.5.1 record](release-2.5.1.md#existing-native-library-warnings). No new native
dependencies or warnings were accepted; the resulting installer was not executed.

| Published artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.5.8.exe` | 298933928 | `accf2cf18ad5509af7012f59ed750b44199c821ec5b7e4154109a1c1e5b53c15` |
| `FPVS-Studio-Setup-2.5.8.exe.sha256` | 95 | `841ed936814c74a00935d960531e3782e2ef7580f6723b5c000dcce8caf885f7` |
| `FPVS-Studio-Update-2.5.8.json` | 107 | `1e57c7e89c6b96e759a2173323752191539a088b84d82c6a22c6e6e2b22ea428` |
| `FPVS-Studio-Update-2.5.8.json.sha256` | 97 | `4371eb717f1833b296a8424e7b8fdbe4aade780bddbfaf0bdaaff78f15196893` |

The update manifest identifies 2.5.8/windows-x64 with an empty patch list. Both
checksum sidecars match. Build outputs remain under `dist/release-2.5.8/`; rerunnable
audit evidence remains under ignored `build/release-2.5.8-evidence/`.

## Publication and public verification

Release `430636735` is stable, immutable and latest. Annotated tag
`f393ca7b37503d6509cec18c8bb47aaba289bab1` resolves to exact build source
`178591a06f3e27dceb3fde66cffef37c357008f4`, pushed to master. Every draft asset's
name, size and GitHub SHA-256 digest matched the local audit before publication.
Previously published artifacts and tags were not changed.

GitHub's release attestation verifies the tag and all four assets. Independent
public downloads match every audited size/hash and pass `gh release verify-asset`.
Eight live production updater cases pass: older 2.4.4 and previous 2.5.7 select the
full installer, including registered-style, forced-full and repair selection;
current 2.5.8 reports no update and permits repair; newer 2.5.9 rejects downgrade
repair. Production bounded fetching authenticates the update manifest. These checks
read no working installation, import no Qt and execute no installer. GitHub release
attestations do not constitute Windows Authenticode signing.

No Birth Control project or Library version was changed: this is a shared renderer
repair delivered by updating Studio. The installed application was not replaced.
Visible fullscreen acceptance remains pending; deterministic geometry checks and
font-metric estimates do not substitute for native presentation qualification.

## Published notes

- Fix overlapping participant instructions, including the Birth Control study.
- Keep instruction text within smaller presentation windows.
