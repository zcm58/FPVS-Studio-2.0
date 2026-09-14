# Release 1.6.1

Status: Completed

The user authorized packaging and GitHub publication of 1.6.1, including the native
Windows patch eligibility change and diagnostic logging. Preserve the published
1.5.3 and 1.6.0 releases. Build a full installer and direct patches from both versions
using authenticated published inventories, isolated release-1.6.1 output directories,
and the retained sanitized dependency PATH. The default branch is master.

Run packaging focused checks and repo precommit, the previously approved bounded
visible packaged smoke, isolated synthetic installer lifecycle checks, and exact
archive/delta verification. Do not replace the user's installed application. Verify
all draft GitHub asset sizes/digests before publication, then check public updater
metadata. Existing installed 1.5.3 may still offer the full installer; its original
eligibility failure remains unconfirmed. Report that limitation in release notes.

## Release result

Published https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v1.6.1 as the latest
stable release from commit `a8cccac` on `master`. All four uploaded assets match
their local sizes and SHA-256 digests:

- Full installer: 254,748,228 bytes;
  `5442bc90b2b06f8506ad41ce53a915695ae1afdc9d39156e4e5520fd770e88a9`.
- Patch from 1.5.3: 27,897,080 bytes;
  `611ef17d036176b5c483fc4d3a85022b9fee13b28557ee030da9a18144359706`.
- Patch from 1.6.0: 27,869,430 bytes;
  `8da8cb3a56d3ee3b6b1aebdf9612a9111bc3ac21cb6b918c9ad09c9c8de4d2ef`.
- Update JSON: 760 bytes;
  `377a30f3454fbed7fc4ecadeb510236de1f2d184a91a0658bd2dffc3803d722a`.

Packaging focused: 168 passed. Updater focused before version bump: 238 passed,
four symlink-permission skips. Final repo precommit: 1,452 passed, seven permission
skips; Ruff, compilation, mypy, and repo/doc audits passed. The approved bounded
visible packaged smoke passed with version 1.6.1. All 15 isolated native lifecycle
steps passed, with production registration unchanged and six user-data sentinels
preserved. No dependencies upgraded; all 486 native source paths match 1.6.0.

Archive verification matches all 7,058 target files. The exact patches contain 13
files from 1.5.3 and 10 from 1.6.0, and each reconstructs the full target after
owned-file reconciliation. Authenticated public metadata fetch passes; 1.5.3 and
1.6.0 see the update, while 1.6.1 is current. Evidence is retained under ignored
`build/release-1.6.1-baseline/`; native fixtures are under
`build/patch-installer-lifecycle/native-rqthd_97/`.

The user's installed application and user-owned output were preserved. No real
installed end-to-end upgrade, clean-PC/no-Python test, or experiment playback was
performed. Release notes disclose these limits and the old updater's possible full
installer selection. The separate historical updater acceptance plan stays active.
