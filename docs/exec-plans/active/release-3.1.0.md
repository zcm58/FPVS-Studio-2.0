# Studio 3.1.0 release

Status: Active

Publish Studio 3.1.0 as the stable Windows x64 release. Build the full installer
and updater manifest from the exact versioned source. Use the existing build
environment and the published 3.0.1 installer as the authenticated baseline.

1. Commit the menu changes and version bump. Verify the exact source with the
   packaging, updater, and GUI scopes and the repository precommit route.
2. Build the labeled bundle and installer. Verify DLL origins, compare native
   files with 3.0.1, and test Studio, Update & Repair, and the installer lifecycle
   in an isolated Windows environment.
3. Upload the installer, updater manifest, and checksums to an immutable-release
   draft. Verify GitHub asset sizes and digests before publication. Verify the
   published attestation, public downloads, and the 3.0.1 updater's selection.
