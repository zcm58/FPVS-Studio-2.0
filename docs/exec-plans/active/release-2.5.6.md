# Studio 2.5.6 release

Status: Active

Date: 2026-10-30

## Authorized outcome

Bump the version, compile automatic Library project update detection and publish
a stable GitHub release with compact bullet-only notes. Current source/public
version is 2.5.5; the next patch is 2.5.6. Preserve dependencies, existing artifacts,
the working installation, projects and preferences. Use isolated `release-2.5.6` outputs.

## Scope and verification

Source `3862f41` checks linked projects on open and every five idle minutes, offers
eligible new published versions once per project/release/session, defers during
presentation/modal/background activity, and respects opt-out. Installation remains
an explicit separate-project import. The change passed 3,980 non-Qt tests with 12
Windows permission skips, Library focused (416 with three skips), GUI focused (98),
docs focused (10), Ruff/compilation and mypy over 249 source modules.

Run packaging checks before/after the bump. Refresh only editable app metadata
with `--no-deps --no-build-isolation`, preserving dependency versions. Compile using
`build_release.ps1 -SkipInstall -SkipSmoke -BuildLabel release-2.5.6`. Publish the
full installer, update manifest and both checksum sidecars; no optional patch.
Audit frozen source/versions, inventory/hashes, native input paths and warnings.
Compare with preserved local 2.5.3 evidence, since no local 2.5.5 build is available.
Verify draft asset digests before publishing, then immutable-release attestations,
independent public downloads and the production updater's version/repair selection.

## Boundaries

The user explicitly authorizes publication. Qt/visible GUI, installation lifecycle,
physical EEG and display timing checks remain unrun. No installer/uninstaller is
executed on the working installation. Preserve and disclose existing native-library
warnings. Publication does not establish acceptance of unrun checks.

## Progress

- Clean source; remote pulled and already current.
- Canonical version advanced to 2.5.6.
- Packaging checks passed 183 cases before and after the bump; docs checks passed ten.
- Only `fpvs-studio` changed among 145 installed distributions (metadata 2.5.3 to
  2.5.6); source metadata had already been 2.5.5. All dependencies remain unchanged,
  source/installed versions now agree, and `pip check` passes.

Build and publication evidence will be recorded after verification.
