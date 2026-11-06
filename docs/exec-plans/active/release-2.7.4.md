# Studio 2.7.4 release

Status: Active

## Scope and authorization

The user requested bundling and publishing 2.7.4 after the committed serial-error
and BioSemi recovery changes in `c93c7b3`. Publish a full Windows installer and
update manifest, as in 2.7.3. No direct patch baseline is newly promised.
Existing approval covers visible simulated GUI and packaged diagnostic checks.
Do not execute a production installer, access actual COM ports, install vendor
software, or claim physical EEG receipt or timing qualification.

Preserve user-owned untracked files, previous release evidence and temporary
directories whose cleanup was blocked. Build only the exact committed source in
an isolated checkout with the existing dependency versions.

## Gates

1. Bump canonical metadata, run packaging focused checks, and commit/push the
   release candidate. Verify the previously tested implementation is unchanged.
2. Run exact-source precommit and CI. Build the full installer, compare frozen
   source and dependencies with authenticated 2.7.3, and verify its complete payload.
3. Run approved visible packaged Studio and independent updater diagnostics,
   without network actions or installer execution, plus candidate updater selection.
4. Stage four assets and concise bullet-only notes in a draft. Verify source/tag,
   asset sizes and hashes before publishing immutable/latest. Verify public
   downloads, release attestations and live updater selection; archive this plan.

## Evidence

- Prior implementation: 5,699 safe tests passed, 32 platform/permission skips and
  24 passing subtests. All 24 Python/config/test files in the saved verification
  snapshot match the committed implementation; this release changes metadata/docs.
- Packaging baseline: 192 passed. Release evidence will be retained under
  `build/release-2.7.4-evidence/`.
- Physical hardware, installed-upgrade and another-PC checks remain unperformed.
