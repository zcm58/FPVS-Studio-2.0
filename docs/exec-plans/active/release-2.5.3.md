# Studio 2.5.3 release

Status: Active

Date: 2026-10-28

## Authorized outcome

Bump Studio to 2.5.3, compile the updater bullet-formatting fix and publish it on
GitHub with compact, bullet-only release notes. Use isolated `release-2.5.3`
outputs; preserve dependencies, prior artifacts, the working installation and
all project/user data.

## Scope

Source `446e0ff` keeps release-note bullets on separate lines, bounds the preview
to four lines and 240 characters, and retains full summary text in the tooltip
and accessible description. The release-page action and update lifecycle retain
their current behavior. Release notes contain two short bullets under 240 characters.

## Verification and build

The fix passed 52 updater unit cases, GUI focused (95), docs focused (10), Ruff,
compilation and mypy over 245 source modules. Four line-preservation regressions
also failed against the previous implementation. Registered Qt coverage exists
at both dialog sizes and palettes and remains unrun.

Run packaging-focused checks before/after the version bump; refresh only editable
app metadata using `--no-deps --no-build-isolation`. Build with the preserved
environment and `build_release.ps1 -SkipInstall -SkipSmoke -BuildLabel release-2.5.3`.
Publish the full installer, update JSON and both checksum sidecars; no optional
direct patch is planned.

Audit frozen versions, compiled source, ownership inventory, native inputs and
artifact hashes. Compare warnings/native input bytes with the preserved local
2.5.2 audit. Verify draft asset sizes/digests before publication, then check the
immutable release attestation, public downloads and production updater selection.

## Boundaries

The user explicitly authorizes publication. Visible GUI, install/upgrade/uninstall,
physical EEG and display timing checks remain unrun. Do not execute an installer
or uninstaller on the working installation. Preserve documented native warnings;
publication does not establish acceptance of unrun checks.

## Progress

- Clean source and remote checked; no incoming changes.
- Packaging baseline passed all 181 tests.
- Canonical version advanced to 2.5.3.
- Packaging checks after the bump passed all 181 tests; docs checks passed ten.
- Among 145 installed distributions, only `fpvs-studio` changed (2.5.2 to 2.5.3).
  Source and installed versions agree, and `pip check` passes.

Build and publication evidence will be added after verification.
