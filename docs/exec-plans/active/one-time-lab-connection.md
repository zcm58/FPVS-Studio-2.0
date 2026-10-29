# One-time lab connection

Status: Active

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
- Focused baseline and implementation are in progress. Production deployment and
  new compiled distribution are not yet verified.
- The requested compiled release continues as version 2.5.5. A clean build checkout
  will exclude the unrelated untracked script without moving or changing it.
