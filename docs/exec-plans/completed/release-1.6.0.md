# Release 1.6.0

Status: Completed

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

## Release result

Published https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v1.6.0 from
commit `4ed84c9` on the default `master` branch. GitHub marks it as the latest
stable release. All three uploaded sizes and SHA-256 digests match local artifacts.

- Full installer: 254,733,710 bytes; SHA-256
  `ac1ec4db031e0140d32e04622bd73a0451d94040ed546b202bb5025c1c0e4332`.
- Direct 1.5.3 patch: 27,896,717 bytes; SHA-256
  `cd57d616017cfb630429dbbb3afc39c7b6f7c07eda5cad08c5c5bc7ab62ad649`.
- Update JSON: 435 bytes; SHA-256
  `54a800ef033dd54b0479431cf0ef4c741a82265f23b7475b5b52c53ec6e680a0`.

Packaging focused checks: 168 passed. Repo precommit: 1,440 passed, seven Windows
symlink-permission skips; mypy and repository audits passed. The user-approved
visible packaged smoke passed. Native synthetic lifecycle passed all 15 steps,
with production registration unchanged and all six user-data sentinels preserved.
Archive extraction verified all 7,058 target files and the exact 13-file sparse
payload; applying the delta and obsolete-file reconciliation reproduces the target.
The sanitized build excludes old DLLs collected from Codex's Poppler/libheif tools;
shared native dependency source paths remain unchanged. No dependencies upgraded.
Public updater checks confirm 1.5.3 sees 1.6.0, 1.6.0 is current, and the update
metadata downloads with its authenticated digest.

Evidence remains under ignored `build/release-1.6.0-baseline/`, with native fixtures
under `build/patch-installer-lifecycle/native-hkd7w7nq/`. Existing installation and
user-owned `output/` were preserved. No clean-PC/no-Python test or real experiment
playback was performed; release notes disclose those limits. This release does not
complete the separate historical installed-upgrader acceptance plan.
