# FPVS Studio 2.2.5 Release

Status: Active

## Scope

Release the requested compatibility fixes for bundle transfers, opening imported
projects, root/template setup, Windows path handling and scaled display calculations.
Build from committed master using the existing executable/installer scripts with
isolated release-2.2.5 outputs. Include the full installer, a direct 2.2.4 patch,
update metadata and checksum files.

## User Authorization And Check Boundary

The user requested publication and then explicitly said "skip release checks to be
faster." Additional release tests, installer extraction/reconstruction audits, source
and native payload audits, GUI smoke, installed-upgrade tests and live updater-selection
tests are waived for this release. Existing implementation verification remains recorded
in the active private-library audit. Packaging focused had already started before the
waiver and completed with 181 tests passing.

The build retains required metadata/inventory checks and its bounded updater backend
diagnostic. Baseline identity is required for patch creation. Publication uses the
resulting installer/update files and confirms GitHub accepted the assets; waived tests
must not be described as passed. No existing installation or project data is modified.

## Release Notes

Use the user's exact text:

Improved backend handling of long windows filepaths causing errors on some systems.

## Progress

- Version bumped to 2.2.5 in the canonical pyproject.toml metadata.
- Published latest baseline confirmed as v2.2.4.
- Build and publication pending.
