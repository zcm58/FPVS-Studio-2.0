# FPVS Studio 2.3.0 condition publication release

Status: Active

Date: 2026-10-07

## Scope

The user authorized a new public Studio release with per-condition OpenFPVS Library
publication requests. Use semantic version 2.3.0 for the new user-facing feature.
Build from current released master plus the isolated request workflow; preserve
the unrelated results-sharing development branch and the existing 2.2.7 draft.
The latest public stable 2.2.6 is the supported direct patch baseline.

The private service's current main owns its repository rename and experiment tags.
Preserve those changes, integrate the reviewed submission flow, and use the next
additive migration. Activation must verify the existing GitHub App's fixed-repository
Contents write permission before enabling uploads. No paid services are required.

## Exact release note

- Users can now request access to upload experiments to the OpenFPVS Experiment Library.

## Gates

- [x] Isolate the feature onto current released master.
- [ ] Pass focused packaging/Library checks and safe precommit on the isolated source.
- [ ] Commit the final candidate on master and authenticate the public 2.2.6 baseline.
- [ ] Build full installer, direct patch, update metadata and checksums.
- [ ] Audit exact patch reconstruction, native dependencies and all embedded source.
- [ ] Approved visible native submission tests and bounded packaged smoke, or explicit waiver.
- [ ] Verify/activate the companion service and live protected review endpoints.
- [ ] Publish the exact Studio release note and authenticated artifacts.
- [ ] Verify public assets/digests, updater choices and remote branch/tag identities.

## Boundaries

Release packaging is authorized. Native Qt testing still requires explicit approval
for a safe visible environment; do not use offscreen execution. Build without GUI
smoke while that approval is outstanding. No actual experimental stimulus playback,
participant data submission or installed upgrade is implied by artifact audits.
Keep precise verification and activation evidence here, outside public release notes.
