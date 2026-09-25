# Masking 1.4.0 and supporting Studio 2.2.0

Status: Completed

The user requested a new Masking Library release with condition-start and 55/56/57
target, mask and omitted-target markers. The implemented project requires new Studio
features, so publish supporting Studio 2.2.0 before Masking 1.4.0 with that minimum.
Preserve one Library listing by retiring the older Masking catalog entry after the
replacement is ready, retaining immutable release assets and installed participant data.

The user additionally asked about easier participant-answer access, group summaries,
and improved participant question presentation. A read-only audit informed the
[planned proposal](../planned/participant-results-and-question-presentation.md).
Those GUI features are not implemented or included in this release.

## Release sequence

1. Verify source and package metadata; record the existing Windows file-lock test
   limitations from the marker implementation separately from feature checks.
2. Commit the release candidate and merge to master; build the full installer and
   a direct patch from authenticated Studio 2.1.0 in isolated output directories.
3. Audit extracted payload, exact patch reconstruction and updater choices; publish
   Studio and compare local/server asset digests. Record unrun GUI/hardware checks.
4. Prepare/import/compile Masking 1.4.0, preserving assets, task scoring and timing.
   Verify 30 runs and 2,430 markers (30 starts, 1,080 targets, 1,200 masks, 120 catch slots).
5. Publish the immutable Library bundle and catalog entry; remove the older listing,
   then verify live catalog/download/import, upgrade detection and duplicate prevention.

Release notes use only brief bullet points, one or two sentences per major change.
Do not include verification text or installer directions in those notes.

## Publication evidence

- Studio source commit `490ee16855efc4f71152a8c6773c291586d1e856` was committed,
  fast-forwarded to `master`, pushed, and built from the clean checkout. Annotated tag
  `v2.2.0` resolves to that commit.
- [Studio 2.2.0](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.2.0)
  is public with the full installer, direct 2.1.0 patch, update manifest and three
  checksum files. All six GitHub asset sizes/digests match local audited files.
- Full extraction verified 7,985 files. The authenticated 2.1.0 patch changes/adds
  11 files, removes 8 and retains 7,974, reconstructing the exact full target.
  All 493 native inputs match the published baseline. Nine changed embedded Python
  modules equal source-compiled code after normalizing source filenames.
- Live updater selection: registered 2.1.0 selects the patch; unsupported versions
  or missing installed inventories select the full installer; 2.2.0 has no update.
- Full installer: 300,981,984 bytes, SHA-256
  `7b4156afb7c1f43b2276d5f8322fe60b00c71df968509b82e39371c6cc82a797`.
  Patch: 72,359,176 bytes, SHA-256
  `d7af6e884cdfcaa563ded227cb8724f1aff64cf46bb7677d8b9a89a495fc2b24`.
- [Masking 1.4.0](https://github.com/zcm58/FPVS-Studio-Library/releases/tag/masking-v1.4.0)
  requires Studio 2.2.0 and was published through the canonical maintainer publisher.
  Bundle: 31,431,983 bytes, SHA-256
  `df0709b64d16c885d7124b3b318950df8c8b0ae04f24cb0f0731444c683f3d37`.
- Library publication commit `d3a2925c93b63deece5a76ecb5b8e6baaf5a0471` added 1.4.0.
  Catalog commit `d5ea372` removes only the 1.3.0 listing; seven unrelated entries
  and the archived 1.3.0 release/assets remain intact.
- Live Library service download/import, provenance receipt and all 126 asset hashes
  passed. The 12 conditions produce 30 runs and 2,430 markers. Removing trigger lists
  yields the same compiled scenes, tasks and schedule as 1.3.0. Both duplicate
  download paths and a duplicate direct import are blocked before creating a copy.
- A scratch import using the retained, actual 1.3.0 Library receipt was offered
  live 1.4.0 through the normal automatic update check after 1.3.0 was unlisted.
  The existing explicit update workflow imports a separate newer project; it does
  not update in place. All 132 old project files, including three synthetic
  participant-data sentinels and its receipt, remained byte-identical. The new copy
  compiled correctly and repeated 1.4.0 download/import attempts were blocked.
- Prepared evidence is retained in ignored `build/release-2.2.0/` and
  `build/masking-1.4.0/`. Release notes contain only brief feature bullets.

## Verification boundaries

Compiler, engine and project-I/O focused routes passed as recorded in the
[marker implementation](masking-event-markers.md). Release packaging focused:
181 passed; Library focused: 225 passed and three unavailable Windows-symlink skips;
docs focused: nine passed. Ruff/compilation, mypy and repository audits passed.
The broad safe suite had two failures in unchanged Windows filesystem operations;
their targeted outcomes are recorded in the marker plan. A fully passing broad
suite is not claimed.

No Qt/participant GUI, installer execution, installed upgrade, clean-machine install,
physical display timing, serial transport or EEG receipt acceptance was performed.
Artifact equality and compiled marker tests do not establish those hardware results.
