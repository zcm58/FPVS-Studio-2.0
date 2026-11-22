# Studio 3.1.4 release

Status: Active

Release the Studio efficiency upgrades as a Windows x64 patch version. Include
the current Experiment Library preview for the FPVS Oddball Demo. Preserve
project and runtime formats and the pinned packaging dependencies.

Build the full installer and updater manifest from the versioned source. Verify
the native dependency inventory, then stage the assets and checksums on a GitHub
draft. Run exact-artifact Windows smoke and installer lifecycle checks in an
isolated hosted session. Compare the draft digests, publish the immutable release,
and verify public downloads, attestations, and updater selection.
