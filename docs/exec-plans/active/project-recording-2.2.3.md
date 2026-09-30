# Project recording persistence and 2.2.3 release

Status: Active

The user requested an immediate fix and release: recording device settings must
persist independently for each project. On this machine Semantic Categories must
use Unicorn and every other active project must use BioSemi.

## Implementation and acceptance

- Persist a typed optional recording configuration in ProjectSettings; absent
  configurations use BioSemi. Keep recording transport outside compiled contracts.
- Stop injecting the computer-wide preference when projects open. Settings Apply
  atomically saves only recording fields and preserves unrelated pending edits.
- Preserve the choice through project save/reopen, bundle and config interchange.
- Validate invalid input and failed writes without changing the accepted device.
- Back up and update the 15 active projects under the configured external-drive
  root, excluding archival backups and migration snapshots.
- Verify focused project-io/GUI/runtime checks and repo precommit. Add registered
  Qt coverage; do not run unapproved Qt or physical acquisition checks.
- Bump to 2.2.3, commit/push, build full installer and direct patches from published
  2.2.1 and 2.2.2 baselines, audit, verify draft assets and publish release notes.

## Evidence

Initial project-io checks passed 261 tests with two Windows symlink skips.
The existing global Unicorn QSettings preference overrides every opened document.
No user installation or acquisition process will be launched during checks.

The local project repair completed: 14 BioSemi selections and one Unicorn selection
for Semantic Categories; only recording fields changed. Exact originals are retained
under `build/project-recording-2.2.3/project-backups/`.
