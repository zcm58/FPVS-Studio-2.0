# One-time lab connection

Status: Completed

Date: 2026-10-29

## Outcome and boundaries

Researchers enter their reusable lab access code once to enroll their computer.
The existing protected Library identity then discovers the studies their lab may
contribute to. Data Sharing & Comparison offers study names and Connect, without
asking for the code again or requiring a copied project UUID. A unique match is
selected; multiple matches require an explicit choice. Library browsing continues
to expose the lab's granted experiments with the existing download permissions.

The Library credential stays in the OS secure store. No lab code is saved. Results
retain their separately scoped credential and administrator approval. Live lab and
experiment grants remain authoritative. First approved results enrollment keeps
the current sharing default, saved off choices survive, and history is not uploaded.
Old clients retain code-based enrollment. An old individual Library invitation
cannot gain lab-wide Results permission; the UI directs that user to Lab access.

Linked projects require their exact installed Library item/version and protocol.
Locally authored projects can discover by protocol, preserving existing enrollment
support. Requests never transfer a Library token to a different service origin.

## Implementation and verification

1. Add authenticated study discovery and enrollment to OpenFPVS, reusing current
   Results authorization and quotas. Verify rejected tokens, revoked labs/codes,
   absent/read-only grants, ambiguous studies, approval retries and exact scope.
2. Add a narrow cache-locked Library credential reader and neutral Results methods.
   Verify secure-store isolation, fixed origin, strict bounded responses,
   cancellation, pending-token replacement and preserved consent.
3. Replace code/UUID inputs with a study chooser, Refresh studies and Lab access.
   Keep worker ownership, stale-project guards, launch cancellation and shutdown.
   Verify zero/one/many studies, errors, pending approval and busy states.
4. Run focused checks and repository precommit. Update canonical workflow docs.
   Build and inspect the compiled dialog in the already approved isolated visible
   profile; do not substitute source Qt execution for compiled acceptance.

## GUI brief

The researcher has opened a downloaded or authored experiment and wants to connect
it to the correct shared study. The primary action remains Connect. The existing
quiet Sharing/Comparison dialog and shared component styles are the visual anchor.
Keep its `820x480` minimum and `880x540` default size, with long study names exposed
in tooltips when intentionally elided. Successful acceptance means no code or UUID
entry after machine enrollment, an explicit choice for multiple studies, actionable
empty/rejected states, and no clipped controls at either size.

## Progress

- Existing 2.5.4 release is complete; this feature is a new cross-layer change.
- Studio has an unrelated untracked `engines/standalone_contrast_example.py`; leave
  it untouched and outside this feature's commits/build inventory.
- Implementation and focused checks passed: Library 399 plus 24 subtests (three
  Windows symlink skips), affected sharing 146, coordinator 76, GUI-safe 95,
  packaging 183 and backend 461. Source Qt execution remains unrun.
- Backend commit `b9c0be8` is deployed as
  `ea526bbd-f19f-484e-8212-eac2abbfc148`; no migration was needed. Live anonymous
  website/catalog/new-route checks passed. An offline cross-repository roundtrip
  used real client and Worker code with two permitted synthetic labs and a third
  ungranted lab; discovery, approval, upload/retry and revocation checks passed.
  No real research data or credentials were used.
- The first compiled sweep passed structural checks but visual inspection found
  that its synthetic light palette retained dark text roles. The fixture was corrected and visible acceptance repeated before publication;
  this is not a product theme fix.
- The requested compiled release continues as version 2.5.5. The clean build checkout
  excluded the unrelated untracked script without moving or changing it.

## Final verification and release

- Safe repository precommit passed: **3839 passed, 12 skipped, 24 subtests passed in 1074.13s (0:17:54)**. The 12 skips require Windows symlink privilege. The final palette-fixture/documentation delta also passed changed-file Ruff, mypy over all 245 source files and four packaging smoke-contract tests. No application workflow changed after the safe-suite candidate.
- The frozen 2.5.5 build passed 58 synthetic screen states, including both sharing themes at 820x480 and 880x540. All states were visually reviewed; 24 received full-size inspection. Long study titles retain full-value tooltips. Pending replacement stays plain text and defaults to No.
- The first partial-palette captures are explicitly superseded. Final screenshots, hashes, source mapping and visual verdict are retained under `build/release-2.5.5-evidence/screenshots-final/`. Both Qt settings scopes and the smoke profile were isolated.
- All 7,987 extracted installer files match the target inventory, SHA-256 `9c8a7c87306826564f4d2625d084671c67672e041342560d67877a57b54de78b`. All 245 Studio and 23 updater application modules match committed source; the unrelated untracked engine example is absent.
- All 491 Studio and 69 updater native inputs match the authenticated 2.5.4 baseline. Frozen dependency modules, all 140 dependency distribution versions and the 21 distinct build warnings are unchanged.
- Source `950343c42ac78baaf23fb586c4e6902807f94f18` is the exact `v2.5.5` tag target. The four assets were hash-checked before immutable [GitHub publication](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.5.5), then independently downloaded and checked with signed release/asset attestations.
- Ten candidate and 10 live updater cases passed, including current-version repair, downgrade rejection and a real bounded manifest fetch. The full installer is selected; no direct patch is advertised.
- Backend 461-test coverage and the offline two-lab/third-denied roundtrip are recorded in sibling OpenFPVS `INTEGRATION_PLAN.md`. Its source and deployment record are pushed on main (`b9c0be8`, `8476e3f`); production Worker identity and anonymous checks are recorded above.
- No source Qt test, installer execution, actual lab approval, authenticated production report upload or EEG/display experiment was performed. Local synthetic clients and the frozen GUI provide separate evidence; live probes establish routing/authentication denial, not live two-lab collection.

## Published assets

The versioned `build/release-2.5.5/` and `dist/release-2.5.5/` outputs are retained
in the primary workspace. The retained bundle was rechecked against the same
7,987-file inventory. Historical audit paths are mapped in
`build/release-2.5.5-evidence/retained-output-paths.json`. Git unregistered the
temporary checkout, but Windows path lengths prevented full directory removal.
Automatic approval review blocked the subsequent bounded PowerShell cleanup
with only "blocked by policy" as its reason. Remaining temporary files at
`C:\Users\zcm58\PycharmProjects\Studio-255-release` were left in place; cleanup
is pending and does not affect the preserved or published release.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.5.5.exe` | 300830865 | `3f35516ec569638b64c1c1bd204ff6a446e47ee4400ed7b55597f420619e9c18` |
| `FPVS-Studio-Setup-2.5.5.exe.sha256` | 95 | `820c9c334be341bf802ae13c0341982f4a779736e5bfd63c405e5b5a43947e7d` |
| `FPVS-Studio-Update-2.5.5.json` | 107 | `91009cb8219cc7c1acc9dcaf762d32aba1e1c5597482f66c9094cd68c699c75d` |
| `FPVS-Studio-Update-2.5.5.json.sha256` | 97 | `6db4d4c04f39e9aee74ec2416da44c605c2b9544c86e55e85cc3752f0043c56b` |

## Published notes

- Connect your computer to your lab once. Shared studies now use that saved access, with study names instead of extra code and project-ID prompts.
