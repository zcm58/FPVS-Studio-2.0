# Studio 2.5.7 Release

Status: Completed

Published November 1, 2026 as the latest stable immutable release:
[Studio 2.5.7](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.5.7).

## Scope and release workflow

The user requests a new published Studio release with the shared mouse-selection
repairs. Capture native presses immediately after the first visible task flip,
before keyboard clearing can dispatch and discard them. Match text hit areas to
rendered alignment and wrapping, including overflowing lines. These are application
renderer repairs shared by Creatine, Cognitive Decline, Cognitive Load and other
mouse-response tasks; experiment modifiers and selection protocols are unchanged.

Include the verified Library publisher compatibility guard and the existing
Cognitive Load pilot timing implementation, required by published project 1.0.5's
minimum Studio version 2.5.7. Pull recent master changes before building, preserve
the restored work and rerun the safe non-Qt repository gate after integration.

Set the canonical version in `pyproject.toml`, refresh only editable application
metadata and preserve all dependency versions. Use an isolated
`release-2.5.7` build label and constrained native dependency PATH through the
canonical release script. Audit frozen application source, metadata, ownership
inventory, native inputs and warnings against the preserved 2.5.6 evidence.

Publish a draft with the full installer, update manifest and both checksum
sidecars. Verify exact asset identities, sizes and SHA-256 digests before publishing
as latest; then verify immutable release attestations, independent public downloads
and production updater selection. Retain detailed evidence under ignored
`build/release-2.5.7-evidence/` and output under `dist/release-2.5.7/`.

## Acceptance boundaries

No Qt or fullscreen presentation is launched, and no installer is executed against
the user's working installation. Static frozen-code checks and non-Qt regressions
do not establish visible participant interaction, clean-PC installation, native
upgrade recovery or physical display/EEG timing acceptance. Existing native-library
warnings must be compared and disclosed. Release provenance is GitHub's immutable
release attestation, not Windows Authenticode signing.

## Progress

- Pulled master from `e904dac` to `5ad86a2`; resolved documentation conflicts while
  preserving the new concise navigation and existing mouse/pilot additions.
- Packaging focused baseline: 183 passed. Documentation integration: 13 passed.
- Version set to 2.5.7. Only editable application metadata changed among 145
  distributions; dependency versions are unchanged and `pip check` passes.
- Packaging focused after the bump: 183 passed. Library focused with the future
  mouse-task publication floor raised to 2.5.7: 540 passed, three permission skips.
- Saved Creatine, Cognitive Decline and Cognitive Load projects pass all 40 simulated
  first-visible-frame target clicks at scales 1 and 2; their project JSON is unchanged.
- Engine focused: 547 passed. Repository precommit: Ruff, compilation, mypy over
  261 source files, audits and 4,572 non-Qt tests passed; 13 Windows symlink-privilege
  checks skipped. The storage stress case completed within its explicit timeout.
- Build, artifact audits, publication and public verification completed successfully.

## Build and artifact evidence

All 7,062 bundle files match the complete ownership inventory, SHA-256
`4c37ad7c6e3f4784dee3ab0435c8de3eb54adfcde0ec43a92b0536dae7cbf51f`.
Studio and updater package metadata both report 2.5.7. The independent updater's
frozen diagnostic passes with protocol 1 and `gui_loaded=false`.

All 261 frozen Studio modules plus entry and all 22 updater modules plus entry
match current compiled source. A separate required-module check confirms the
mouse renderer, Library compatibility guard/final publisher verification and pilot
model/compiler changes are present and source-equal without executing them.

All 486 Studio and 69 updater native input paths and hashes exactly match the
preserved 2.5.6 audit. All 22 normalized build warnings match that baseline,
including the five known optional MeshPy/PyTables dependency warnings described in
the [2.5.1 record](release-2.5.1.md#existing-native-library-warnings). No new native
sources or warnings were accepted. This audit does not extract or execute setup.

| Published artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.5.7.exe` | 298937914 | `8819e8ec63e6d91ff7260e1d6ef83fb86fb45a69578dce470cb5a4be35782880` |
| `FPVS-Studio-Setup-2.5.7.exe.sha256` | 95 | `7e195d0389493dc3c5b552eb1cbe79637fe8cddf1da5b751cacedfb84ae5a9b9` |
| `FPVS-Studio-Update-2.5.7.json` | 107 | `7caf7f83f022bcf968854adfe3b395e32c57fbd080adac8e2c718b2416351904` |
| `FPVS-Studio-Update-2.5.7.json.sha256` | 97 | `51113c095bcbd481fbd4cbf47f53e01508ad1e4d2bd4d75fad217354a55dab02` |

The manifest identifies 2.5.7/windows-x64 with an empty patch list. Both checksum
sidecars match their artifacts. No previously published artifact was replaced.

## GitHub publication and public checks

Release `430616991` is stable, immutable and latest. Annotated tag
`ab801e4d2c8a56a6a03bb7b1483d7198847f883a` resolves to exact build source
`1c5ba0f862c486bf26cc65dfa639ba006bbbfffe`, pushed to master.

All four draft assets matched local names, sizes and GitHub SHA-256 digests before
publication. GitHub's release attestation binds the tag and all four artifacts.
Independent unauthenticated public downloads match every audited size/hash and pass
`gh release verify-asset`. The CLI intermittently reported that no Sigstore verifier
could initialize; bounded retries repeated only that initialization failure and all
four cryptographic asset checks subsequently passed. No artifact or verifier policy
was changed to obtain acceptance.

Eight live production updater cases pass: older 2.4.4 and previous 2.5.6 select the
full installer, including registered-style, forced-full and repair cases; current
2.5.7 reports no update and permits repair; newer 2.5.8 rejects downgrade repair.
Production bounded fetching authenticates the public update manifest. These checks
read no working installation, import no Qt and execute no installer.

The new application repairs apply to all projects using the shared task renderer.
Future mouse-task Library publications must require 2.5.7 or later. Historical
immutable experiment versions retain their declared minimums; no unchanged project
bundle was republished for this application release. The installed 2.5.6 application
was not replaced. Visible fullscreen and installed-lifecycle acceptance remain
separate as stated above.

## Published notes

- Fix missed clicks and text selection hit areas in participant tasks.
- Support Cognitive Load pilot timing and guard Library mouse-task compatibility.
