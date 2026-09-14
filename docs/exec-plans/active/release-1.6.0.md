# Release 1.6.0

Status: Active

User authorized a version bump, default-branch push, Windows installer and direct
patch build, and GitHub publication on 2026-09-14. The default branch is `master`.
Version 1.6.0 adds reviewed bug reports and feature requests through the File menu,
with verified automatic Cloudflare/GitHub/email delivery.

Build in isolated `build/release-1.6.0/` and `dist/release-1.6.0/` directories.
Authenticate the published 1.5.3 installer and extract its exact baseline inventory.
Preserve native dependency provenance using the previous sanitized build PATH.
Run packaging checks, the approved visible packaged smoke, sparse payload verification,
and isolated native installer lifecycle coverage. Do not install over the user's app.
Create a draft release, compare uploaded asset sizes/digests, then publish.
Include the existing tracked updater repair note; retain user-owned `output/` locally.
