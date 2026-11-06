# Studio 2.8.0 release

Status: Active

The user requested the next GitHub release. Use a minor version for Trigger Tester
and the participant questionnaire builder. Include per-project Brain Products
setup and the menu dividers already on `master`. Bundle the full GPL version 3
text for the project's existing GPL-3.0-or-later declaration.

## Release gates

1. Commit and push the versioned source. Run packaging focused, exact-source
   local precommit, and GitHub source and documentation checks.
2. Build the full Windows installer from that commit in an isolated checkout.
   Preserve build dependencies, compare native inputs with the published baseline
   where available, and verify the bundled Studio and updater versions and payload.
3. Stage a draft with the full installer, an update manifest with an empty patch
   list, and both SHA-256 sidecars. Compare draft assets and the source target to
   the exact local artifacts. Verify candidate updater selection.
4. Run the packaged Studio and updater diagnostics in an explicitly approved
   visible Windows session. The diagnostics use synthetic data and disable
   network and installer actions. BioSemi Trigger Tester hardware confirmation
   is recorded separately in the [feature record](../completed/trigger-tester.md).
5. Publish the verified draft as latest and immutable. Check public downloads,
   release and asset attestations, and live updater selection. Archive this plan.
