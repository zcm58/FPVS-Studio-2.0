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
- [x] Pass focused packaging/Library checks and safe precommit on the isolated source.
- [x] Commit the final candidate on master and authenticate the public 2.2.6 baseline.
- [x] Build full installer, direct patch, update metadata and checksums.
- [x] Audit exact patch reconstruction, native dependencies and all embedded source.
- [x] Approved visible native submission tests and bounded packaged smoke, or explicit waiver.
- [ ] Verify/activate the companion service and live protected review endpoints.
- [ ] Publish the exact Studio release note and authenticated artifacts.
- [ ] Verify public assets/digests, updater choices and remote branch/tag identities.

## Boundaries

Release packaging is authorized. Native Qt testing still requires explicit approval
for a safe visible environment; do not use offscreen execution. Build without GUI
smoke while that approval is outstanding. No actual experimental stimulus playback,
participant data submission or installed upgrade is implied by artifact audits.
Keep precise verification and activation evidence here, outside public release notes.

## Prepared release evidence

The built source is `05e649675cb03a35e0402067c53b0715cbe0f969`, pushed and
verified on remote master. Focused packaging passed 181 tests; Library passed 309
with three Windows symlink skips. Safe precommit passed Ruff, mypy and repository
audits, then 2,639 tests with 11 Windows symlink skips. Two harness failures came
from ignored bytecode left by the preserved results-sharing branch; moving only
that cache into ignored release evidence resolved them. All nine harness tests
passed on the unchanged committed source (2,641 distinct safe tests now pass).

The user explicitly approved visible Windows verification. The GUI full tier was
narrowed to the five new registered submission tests; all passed. The packaged
visible smoke passed with exact version metadata; no experiment or installer ran.

The authenticated 2.2.6 baseline archive SHA-256 is
`71ef9259582b995b84f385e72fcc73099c08ebb027ed4c05f8474dddbe37a030`.
Full extraction verifies all 7,985 payload files. The direct patch has 14 changed
or added files and removes eight; reconstruction equals the full target exactly.
All 487 native payload files and 493 native build inputs match that baseline.
All 216 Studio modules match committed content and embedded bytecode; existing
mixed Windows checkout line endings are normalized explicitly. Unreleased
results/data-sharing packages are absent. Six assets are uploaded and their
GitHub sizes/digests match local files in draft release 406080714.

OpenFPVS main `b63263de860a80767e7811c24f5c4531623d4d0c` is pushed and verified.
Its 228 tests, syntax checks, binding types, and enabled dry packaging pass. The
App permission change was explicitly approved and applied to only private
`zcm58/OpenFPVS-Website`. The existing D1 was privately backed up (not included
in release assets) before applying only additive migration 0008. The feature
flag is enabled in source. Production deployment has not run: automatic approval
review rejected the documented routes-omitted, keep-vars deployment because its
exact authorization and routing impact were unclear. An explicit action question
is pending. Public release publication waits for service activation/live checks.
