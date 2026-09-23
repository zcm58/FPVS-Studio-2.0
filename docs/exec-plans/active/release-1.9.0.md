# Library project updates and Masking release 1.9.0

Status: Active

## Authorized scope

The user requested a version bump and release of the completed features. Use minor
version 1.9.0 for the new project-version workflow. Merge the feature into master,
publish the Windows full installer and a direct patch from the latest published
version, 1.8.1. Source-only version 1.8.2 has no published installer baseline.
Older and unregistered installations retain the full installer path.

Include on-open Library version checks, passive Home notices, explicit separate-copy
updates, version receipts and legacy linking. Also include the native Masking framework,
corrected Color circle sizing, nine condition markers and intervening master changes.
Keep authored projects and participant data outside installer ownership.

## Delivery and verification

1. Bump canonical metadata, refresh the editable package without dependency upgrades,
   run packaging checks and commit the exact candidate on master.
2. Build under ignored build/release-1.9.0 and dist/release-1.9.0 paths, using the
   authenticated published 1.8.1 installer inventory as the only patch baseline.
3. Verify full payload hashes, exact patch reconstruction, embedded changed modules,
   native inputs, release asset digests and live updater selection.
4. Upload a draft, verify all assets, publish, and record the source commit and URL.

The feature precommit gate passed 2,065 tests with 10 unavailable Windows symlink
skips, plus Ruff, compilation, mypy and repository audits. Its live Masking catalog
and temporary separate-import checks passed. Visible Qt/packaged GUI, clean-PC
installation, installed upgrade, physical display and EEG checks remain unrun.
This release request follows disclosure of the unrun GUI checks; do not claim them
as verified or run destructive lifecycle checks on the working installation.

## Progress

- Packaging baseline: 181 tests passed before the version bump.
- Release candidate preparation in progress.
