# Masking 1.4.0 and supporting Studio 2.2.0

Status: Active

The user requested a new Masking Library release with condition-start and 55/56/57
target, mask and omitted-target markers. The implemented project requires new Studio
features, so publish supporting Studio 2.2.0 before Masking 1.4.0 with that minimum.
Preserve one Library listing by retiring the older Masking catalog entry after the
replacement is ready, retaining immutable release assets and installed participant data.

The user additionally requested easier participant-answer access, group summaries,
and improved participant question presentation. The recommended sequence was stated:
complete the trigger release first, then the GUI work. Those changes are outside this
release candidate unless the user redirects that sequence before publication.

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
