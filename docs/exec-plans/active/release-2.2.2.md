# FPVS Studio 2.2.2 release

Status: Active

The user requested a version bump, a full Windows installer and a direct patch,
with exactly this release note:

> Recording device name is now shown on the home screen prior to launching an experiment.

## Release scope

- Bump the canonical package version from 2.2.1 to 2.2.2.
- Build from the committed source in an isolated `release-2.2.2` build label.
- Authenticate the published 2.2.1 full installer and extract its ownership manifest
  without executing setup; use that exact manifest for the direct patch.
- Preserve the packaging environment's dependency versions and check native payload
  changes against the authenticated baseline.
- Audit the full installer, patch payload and update metadata before publication.
- Create the GitHub Release as a draft, verify every uploaded asset's size and
  SHA-256, then publish with the exact requested release note.

## Verification boundaries

Packaging focused passed 181 tests before the version bump. The preceding Home
change passed focused GUI checks and static repo checks; its two unchanged Windows
unit-test failures passed on targeted rerun outside the sandbox. Registered Qt
coverage was added but not run. This release task does not authorize installing over
the user's working installation or running unapproved visible Qt checks. Record
source, frozen non-GUI and artifact checks separately from those pending outcomes.

## Progress

- Published latest version confirmed as 2.2.1; no published assets will be replaced.
- Version set to 2.2.2; metadata refresh, build and publication are pending.
