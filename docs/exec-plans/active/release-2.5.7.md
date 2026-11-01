# Studio 2.5.7 Release

Status: Active

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
- Build and publication remain pending.
