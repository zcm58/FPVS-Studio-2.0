# Studio 2.8.1 release

Status: Active

The user requested the next GitHub release. Bump the source from 2.8.0 to
2.8.1 for the Condition Figure updates after the 2.8.0 draft. The public release
also includes Trigger Tester, questionnaire editing, per-project Brain Products
setup and menu dividers since the public 2.7.4 release. Retain the earlier draft.

## Release gates

1. Commit and push the versioned source. Run packaging-focused verification,
   exact-source local precommit, and GitHub source and documentation checks.
2. Build the full Windows installer in an isolated checkout with the preserved
   dependency versions. Verify bundled versions, exact-source modules, and
   installer payload against its ownership inventory.
3. Stage the full installer, an update manifest with an empty patch list, and
   both SHA-256 sidecars in a new draft. Check the source target, asset bytes
   and candidate updater selection.
4. Run the packaged Studio and updater diagnostics in an approved visible
   Windows session. Use synthetic inputs with network and installer actions
   disabled.
5. Publish the verified draft as latest and immutable. Verify public downloads,
   release and asset attestations, and live updater selection. Archive this plan.
