# Patch Update Workflow

Status: Planned

## Summary

Add an optional small-patch update path on top of the existing full-installer release
workflow. The full Inno Setup installer remains the canonical release artifact for every
version. Patch packages become an additional GitHub Release asset for exact source-to-target
version pairs when a release changes only files that can be replaced safely in the installed
PyInstaller `onedir` tree.

The goal is to let installed users update small FPVS Studio patches without downloading the
entire installer again, while preserving the current fail-fast packaging model:

```text
current installed app
  -> check GitHub Releases
  -> prefer exact patch package when available
  -> verify manifest, hashes, and installed files
  -> close app and run updater helper
  -> apply file replacements
  -> restart FPVS Studio
```

If any patch precondition fails, the patch path stops with a clear reason. The app may then
offer the full installer as a separate user choice, but it must not silently continue with a
partial update or guess how to repair an unexpected install tree.

## Current Baseline

FPVS Studio currently supports:

- version source in `pyproject.toml`
- PyInstaller `onedir` executable bundle under `dist\FPVS Studio\`
- Inno Setup installer wrapping the whole bundle under `dist\installer\`
- GitHub Release updater that selects `FPVS-Studio-Setup-<version>.exe`
- user-approved download of the full installer into an update cache
- `Install and Restart` handoff to the downloaded Inno installer

The existing flow is robust because the installer owns application-file replacement and
because user data lives outside the install directory. The patch workflow must preserve
those same boundaries.

## Professional Recommendation

The recommended shipping model is a conservative hybrid:

- keep the full installer as the only required release artifact
- add patch ZIPs only for releases that meet explicit patch-eligibility rules
- make every patch exact-version, hash-verified, and reversible before cleanup
- keep update discovery in the app, but keep file replacement in a separate helper path
- fail closed on every mismatch and direct the user to the full installer
- never publish a patch without first testing the matching full installer

This is intentionally closer to a miniature installer than a loose file overlay. A patch
system is responsible for replacing executable code on user machines, so it needs release
discipline: deterministic inputs, immutable artifacts, auditable manifests, code signing,
clear rollback behavior, and a boring fallback path.

Recommended first implementation:

1. Build and test the full installer.
2. Compare the previous released PyInstaller bundle against the new bundle.
3. Generate a patch ZIP plus a standalone manifest sidecar.
4. Validate that patch against an installed copy of the previous release.
5. Publish the full installer and optional patch assets to one GitHub Release.
6. Let the app recommend the patch only when the installed version matches exactly.

Do not try to support patch chains in the first version. A user on `0.9.0b8` should not
apply `0.9.0b8 -> 0.9.0b9 -> 0.9.0b10` automatically unless that chain has its own
explicit design, tests, and recovery rules. A direct `0.9.0b8 -> 0.9.0b10` patch is fine
if it is generated and tested as its own artifact.

## Packaging Strategy Tradeoff

Windows already has packaging systems that handle differential updates, signing, and repair
at the platform level. MSIX, for example, uses package block metadata for differential
downloads and App Installer can manage update checks outside the Microsoft Store. That is
the professionally clean long-term option if FPVS Studio later wants platform-managed
updates, enterprise deployment, or stronger tamper repair.

For the current repo, the pragmatic recommendation is to stay with PyInstaller `onedir` plus
Inno Setup and add the custom patch path described here because:

- the current installer and update flow already exist
- the app is per-user installed under `%LOCALAPPDATA%`
- project data is already outside the install tree
- patch releases are expected to be small Python/application changes
- moving to MSIX would be a packaging migration, not a small updater extension

This plan should not block a future MSIX evaluation. It should, however, avoid creating
custom patch machinery that makes a future migration harder. Keep patch manifests,
bundle-diffing, version comparison, and signing concepts isolated under `updates/` and
packaging scripts.

## Patch Eligibility Policy

A release may ship a patch only when all of these are true:

- source and target builds are produced by the standard release scripts
- the target release also has a full installer
- the patch source bundle is the exact bundle used for the previous public release
- the target bundle is the exact bundle wrapped by the target full installer
- no dependency group changed in `pyproject.toml`
- no Python version changed
- no PyInstaller spec behavior changed in a way that reshapes the bundle broadly
- no Inno Setup behavior changed in a way that must run installer logic
- no install location, shortcut, registry, file association, or uninstall metadata changed
- no app data migration requires installer-owned setup or repair behavior
- the changed-file count and patch size are both reviewable
- patch apply smoke tests pass on a clean installed source version

Use the full installer only when any of these are true:

- PySide6, PsychoPy, Python, or large native dependency files changed
- packaging metadata, install scope, shortcuts, icons, or uninstall behavior changed
- the bundle diff is unexpectedly large
- the update includes a migration that must be handled before normal app startup
- the source release bundle cannot be proven identical to the published release
- the patch applicator itself changed and cannot be trusted on the source version
- source-file hashes from a real installed copy do not match the candidate patch manifest
- the release is security-sensitive and should force the most conservative replacement path

Suggested numeric gates for the first implementation:

- warn when the patch ZIP is larger than 25 percent of the full installer
- warn when more than 10 percent of bundle files changed
- require explicit maintainer approval when any `.pyd`, `.dll`, `.exe`, or `.ico` changes
- reject patch generation when the target bundle contains multiple package metadata dirs

These numbers are policy defaults, not architecture rules. They should be easy to adjust in
the build script.

## User Workflow

Manual update check:

```text
File > Check for Updates
```

Startup update check:

```text
Welcome window appears
silent update check runs
dialog appears only when a newer release is available
```

When a patch is available for the installed version:

```text
A new FPVS Studio version is available.
Current version: 0.9.0b9
Latest version: 0.9.0b10

Recommended update: Patch update
Download size: 8.4 MB

[View Full Release Notes] [Download Patch] [Download Full Installer] [Later]
```

When no exact patch is available:

```text
A new FPVS Studio version is available.
Current version: 0.9.0b8
Latest version: 0.9.0b10

This version requires the full installer.

[View Full Release Notes] [Download Installer] [Later]
```

During patch download:

```text
Downloading patch...
<progress bar>
```

Before applying a patch:

```text
FPVS Studio needs to close to apply this patch.

[Apply Patch and Restart] [Later]
```

If patch validation fails before app shutdown:

```text
This patch cannot be applied.
Reason: installed file hash does not match version 0.9.0b9.

Use the full installer for this update.

[Download Full Installer] [Cancel]
```

## Release Artifact Contract

Every release must continue to include the full installer:

```text
FPVS-Studio-Setup-<target-version>.exe
```

Patch releases may also include one or more exact-version patch packages:

```text
FPVS-Studio-Patch-<source-version>-to-<target-version>.zip
```

Examples:

```text
FPVS-Studio-Setup-0.9.0b10.exe
FPVS-Studio-Patch-0.9.0b9-to-0.9.0b10.zip
FPVS-Studio-Patch-0.9.0b8-to-0.9.0b10.zip
```

Only exact source-to-target patches are supported. Do not apply a patch across a version
range unless the package name and manifest explicitly name the installed source version.

## Artifact Immutability

Treat release assets as immutable once a GitHub Release is public.

Rules:

- do not overwrite a published full installer
- do not overwrite a published patch ZIP
- do not overwrite a published manifest sidecar
- do not re-tag a release to point at different source code
- do not rebuild an artifact with the same version after users may have downloaded it
- do not reuse a failed patch filename for a repaired patch

If a published patch is wrong:

1. Mark the GitHub Release notes with a clear warning.
2. Remove or rename the broken patch asset if possible.
3. Publish a new patch target version or require the full installer.
4. Keep the full installer available for repair.

If the full installer is wrong, cut a new app version. The updater should rely on versions
and immutable hashes, so replacing assets in place creates a supply-chain and support risk.

## Release Channel Policy

The patch system should preserve the existing prerelease behavior:

- stable users see stable releases by default
- prerelease users may see newer prereleases
- draft releases are ignored
- patches must not move a stable installation onto a prerelease target
- patches must not move a prerelease installation onto an older stable target

Recommended channel fields in the manifest:

```json
{
  "channel": "prerelease",
  "allow_prerelease_source": true,
  "allow_stable_source": false
}
```

The updater can infer most of this from GitHub Release metadata and PEP 440 versions, but
having explicit manifest fields makes release review easier.

## Source Bundle Preservation

Patch generation needs a trustworthy previous bundle. Do not generate a patch by comparing
the current source tree against Git history. Compare built release artifacts.

Recommended archive layout outside the repo:

```text
C:\FPVS-Studio-Releases\
  0.9.0b9\
    bundle\
      FPVS Studio.exe
      _internal\
    installer\
      FPVS-Studio-Setup-0.9.0b9.exe
    manifest\
      bundle-fingerprint.json
      release-metadata.json
  0.9.0b10\
    bundle\
    installer\
    patches\
```

The archive should include:

- exact PyInstaller bundle tree
- full installer EXE
- bundle fingerprint
- package version
- git commit SHA
- build timestamp
- Python version
- PyInstaller version
- Inno Setup version
- OS build used for release

This archive is not committed to the repo. It is a local release-engineering input. The
docs should say where a maintainer stores it, but not hard-code one user's machine path into
scripts or source.

## Manifest Sidecar Assets

Publish a standalone manifest sidecar beside the patch ZIP:

```text
FPVS-Studio-Patch-0.9.0b9-to-0.9.0b10.zip
FPVS-Studio-Patch-0.9.0b9-to-0.9.0b10.manifest.json
```

Professional recommendation: use the sidecar for update selection and early validation,
then validate the embedded manifest after downloading the ZIP. The sidecar improves user
experience because the app can know whether a patch applies before downloading the patch.
The embedded manifest remains authoritative for the payload that is actually applied.

The updater should require both manifests to match byte-for-byte or match by a manifest
SHA-256 declared in the release metadata. If they disagree, reject the patch and offer the
full installer.

## Release Notes Contract

Release notes should include a short update-artifact section:

```text
Update artifacts
- Full installer: FPVS-Studio-Setup-0.9.0b10.exe
- Patch: FPVS-Studio-Patch-0.9.0b9-to-0.9.0b10.zip
- Patch source: 0.9.0b9
- Patch target: 0.9.0b10
- Recommended path: patch for 0.9.0b9 users, full installer otherwise
```

Do not ask users to manually apply the patch. The release notes can explain that the app's
update dialog will select the right artifact.

## Patch Package Layout

Each patch ZIP should contain a manifest and payload rooted below a single directory:

```text
FPVS-Studio-Patch-0.9.0b9-to-0.9.0b10/
  patch-manifest.json
  files/
    FPVS Studio.exe
    _internal/
      fpvs_studio/
        gui/
          update_dialog.pyc
      fpvs_studio-0.9.0b10.dist-info/
        METADATA
```

The exact internal file list depends on PyInstaller output. The build script should not
assume Python source paths map cleanly to bundled paths; it should compare two completed
`dist\FPVS Studio\` bundle trees and copy changed bundle files from the target tree.

Keep deletions in the JSON manifest for schema validation and release review. Do not add a
second plain-text delete list in schema version 1; duplicate sources of truth make patch
review and application failures harder to diagnose.

## Patch Manifest Contract

`patch-manifest.json` should be machine-readable, deterministic, and small enough to review
in release artifacts. Use JSON rather than ad hoc text parsing.

Proposed fields:

```json
{
  "schema_version": 1,
  "app_name": "FPVS Studio",
  "package_name": "fpvs-studio",
  "source_version": "0.9.0b9",
  "target_version": "0.9.0b10",
  "created_utc": "2026-05-11T00:00:00Z",
  "source_bundle_fingerprint": {
    "file_count": 1234,
    "sha256": "..."
  },
  "target_bundle_fingerprint": {
    "file_count": 1235,
    "sha256": "..."
  },
  "files": [
    {
      "path": "FPVS Studio.exe",
      "action": "replace",
      "source_sha256": "...",
      "target_sha256": "...",
      "target_size_bytes": 123456
    }
  ],
  "deletions": [
    {
      "path": "_internal/old_file.pyd",
      "source_sha256": "..."
    }
  ],
  "installer_asset_name": "FPVS-Studio-Setup-0.9.0b10.exe"
}
```

Recommended additional fields:

```json
{
  "git_commit": "abcdef1234567890",
  "build_id": "2026-05-11T021500Z-abcdef1",
  "source_installer_asset_name": "FPVS-Studio-Setup-0.9.0b9.exe",
  "patch_asset_name": "FPVS-Studio-Patch-0.9.0b9-to-0.9.0b10.zip",
  "minimum_updater_schema": 1,
  "requires_full_installer_when_patch_fails": true,
  "signing": {
    "manifest_signature": null,
    "signing_certificate_subject": null,
    "timestamp_utc": null
  },
  "toolchain": {
    "python": "3.10.x",
    "pyinstaller": "6.x",
    "inno_setup": "6.x"
  }
}
```

For the first implementation, `signing` can be null while the app relies on GitHub HTTPS,
asset hashes, and source-file verification. The field should still exist so future signing
can be added without changing the whole manifest shape.

Do not put the patch ZIP's own SHA-256 inside the embedded manifest. The ZIP hash is
self-referential because the ZIP contains the manifest. Store the patch ZIP size and hash in
GitHub asset metadata, a release checksum sidecar, or the standalone manifest sidecar that
is uploaded beside the ZIP.

Path rules:

- paths are relative to the installed app directory
- paths use `/` in manifest JSON for deterministic cross-tool handling
- paths must not be absolute
- paths must not contain `..`
- paths must not target user project roots, QSettings, templates, `runs/`, or `logs/`
- patch application must resolve every path under the installed app directory before
  reading or writing

Hash rules:

- use SHA-256
- verify current installed files against `source_sha256` before applying changes
- verify payload files against `target_sha256` before replacing installed files
- verify installed target files against `target_sha256` after applying changes
- fail fast on missing, extra, mismatched, locked, or inaccessible files

Manifest validation rules:

- reject unknown `schema_version`
- reject source versions greater than or equal to target versions
- reject package names other than `fpvs-studio`
- reject app names other than `FPVS Studio`
- reject patch asset names that do not match source and target versions
- reject manifests with duplicate paths
- reject a path appearing in both `files` and `deletions`
- reject empty patches unless an explicit `metadata_only` patch type is later designed
- reject file actions other than the supported action set
- reject missing `target_size_bytes`
- reject target sizes that do not match the payload file
- reject manifests whose installer asset does not match the target version

Action set for version 1:

- `replace`: source file must exist and hash-match; target file replaces it
- `add`: source file must not exist; target file is created
- `delete`: source file must exist and hash-match; file is removed

Do not support `patch`, `append`, `script`, or `command` actions in schema version 1.
Those actions increase complexity and create a larger attack surface.

## Bundle Fingerprint

The patch manifest may include a whole-bundle fingerprint to detect unexpected install
trees before file-level checks. This fingerprint should be deterministic and independent of
local absolute paths.

Proposed algorithm:

1. Enumerate all files under the bundle root.
2. Normalize relative paths with `/`.
3. Sort paths ordinally.
4. For each file, append:

   ```text
   <relative-path>\0<size>\0<sha256>\n
   ```

5. Hash the resulting UTF-8 byte stream with SHA-256.

Use the bundle fingerprint as an early diagnostic. File-level source hashes remain the
authoritative safety check before mutation.

## Determinism And Diff Quality

The patch builder should make changed-file summaries useful for release review. PyInstaller
outputs may contain timestamps, caches, or metadata that change between builds even when app
behavior did not change. The patch plan should distinguish expected version churn from
unexpected bundle churn.

Recommended changed-file classifications:

- `application_code`: bundled `fpvs_studio` modules and metadata
- `application_assets`: icons, images, and static GUI assets
- `package_metadata`: `fpvs_studio-*.dist-info`
- `launcher`: `FPVS Studio.exe` and helper executables
- `native_runtime`: `.dll`, `.pyd`, `.so`, or other native dependency files
- `third_party_python`: bundled site-package files outside `fpvs_studio`
- `packaging_noise`: files known to change from build metadata only
- `deleted`: files present in source but absent in target

The patch summary should group files by classification and show:

- changed-file count
- deleted-file count
- added-file count
- total changed bytes
- patch ZIP size
- full installer size when available
- patch size as a percent of full installer size
- largest changed files
- native files changed
- executable files changed

Example summary:

```text
Patch: 0.9.0b9 -> 0.9.0b10
Changed files: 18
Added files: 2
Deleted files: 0
Patch size: 8.4 MB
Full installer size: 245 MB
Patch ratio: 3.4%

Risk flags:
- FPVS Studio.exe changed
- no native dependency files changed
- no installer metadata changes detected
```

The release reviewer should read this summary before uploading the patch. A surprising
summary is a reason to ship only the full installer.

## Dependency And Layout Diff Checks

The patch build script should fail or warn based on high-risk file categories.

Fail by default:

- changed Python runtime files
- changed `PySide6` native files
- changed PsychoPy or engine dependency native files
- missing or duplicated package metadata directories
- changed install-root executable count
- deleted file extensions that Windows may keep locked during runtime

Warn by default:

- changed `FPVS Studio.exe`
- changed `.ico` or branding assets
- changed more than one package metadata directory
- changed large files above a configured threshold
- changed third-party package files
- deleted files under `_internal`

The maintainer can override warnings with an explicit `-AllowHighRiskChanges` style flag,
but the generated summary must record that the override was used. Do not allow overrides
for path-safety or version-integrity failures.

## Developer Release Workflow

Normal full release remains:

1. Update `[project] version` in `pyproject.toml`.
2. Run `.\scripts\build_release.ps1`.
3. Smoke test the bundle and installer.
4. Upload `FPVS-Studio-Setup-<version>.exe` to GitHub Releases.

Patch-capable release flow:

1. Preserve the previous released bundle tree as a patch source input.
2. Update `[project] version` in `pyproject.toml`.
3. Run `.\scripts\build_release.ps1` to produce the target full installer.
4. Run a patch-build script with explicit source and target bundle paths.
5. Review the generated patch manifest and changed-file summary.
6. Run patch-apply smoke tests against an installed copy of the source version.
7. Upload both the full installer and approved patch ZIP to the same GitHub Release.

Example script shape:

```powershell
.\scripts\build_release.ps1
.\scripts\build_patch.ps1 `
  -SourceBundle "C:\Releases\FPVS Studio 0.9.0b9" `
  -TargetBundle "dist\FPVS Studio" `
  -OutputDirectory "dist\patches"
```

Expected output:

```text
dist\patches\FPVS-Studio-Patch-0.9.0b9-to-0.9.0b10.zip
dist\patches\FPVS-Studio-Patch-0.9.0b9-to-0.9.0b10.manifest.json
dist\patches\FPVS-Studio-Patch-0.9.0b9-to-0.9.0b10.summary.txt
```

The standalone manifest copy is for release review. The ZIP remains the artifact consumed
by the updater.

## Release Candidate Workflow

Patch releases should have a short release-candidate loop before public upload:

1. Build the target full installer.
2. Install the previous public version on a clean Windows test profile.
3. Confirm the previous version launches and can check for updates.
4. Generate the patch from the archived previous bundle and new target bundle.
5. Apply the patch locally through the same helper path the GUI will use.
6. Launch the app and confirm `fpvs_studio.__version__` reports the target version.
7. Run packaged smoke diagnostics against the patched install.
8. Run a manual project open/create smoke test.
9. Run `File > Check for Updates` and confirm the app is now current.
10. Uninstall and confirm user data remains untouched.

Only after this loop passes should the patch ZIP be uploaded to the public release.

## Upload Order

Use a release draft until all artifacts are present.

Recommended order:

1. Create GitHub Release as a draft.
2. Upload full installer.
3. Upload full installer checksum if checksums are adopted.
4. Upload patch ZIPs.
5. Upload patch manifest sidecars.
6. Review release notes.
7. From a test machine, query the draft or staged metadata if possible.
8. Publish the release.
9. Run a manual update check from the previous installed version.

Do not publish a release where a patch asset exists but the full installer is missing. The
full installer is the repair path for every patch failure.

## Release Checklist

Before publishing:

- version in `pyproject.toml` matches target release tag
- release tag is PEP 440 parseable after removing leading `v`
- full installer filename matches target version
- patch ZIP filenames match source and target versions
- patch sidecar manifests match embedded manifests
- patch source bundle fingerprint matches archived source release
- target bundle fingerprint matches the installer input bundle
- patch summary was reviewed
- high-risk change warnings were either absent or explicitly approved
- full installer smoke passed
- patch apply smoke passed
- update dialog smoke passed
- release notes describe which users can use the patch
- no local machine paths appear in release artifacts or docs

After publishing:

- install previous release on a clean profile
- use `File > Check for Updates`
- confirm patch is recommended
- apply patch and restart
- verify app version
- verify a second update check reports current
- test full installer download path remains available

## Patch Build Script Contract

Add a developer script:

```text
scripts/build_patch.ps1
```

Responsibilities:

- read source and target package versions from bundled `fpvs_studio-*.dist-info`
  metadata
- fail if source and target versions are equal
- fail if the target version does not match `pyproject.toml` when run from the release
  repository
- compare source and target bundle trees
- produce a deterministic changed-file list
- copy changed target files into the patch payload
- include deletions for files present in source and absent in target
- write `patch-manifest.json`
- write a human-readable summary
- create the versioned patch ZIP

Non-goals:

- do not infer versions from folder names
- do not build the PyInstaller bundle itself
- do not upload to GitHub Releases
- do not mutate source or target bundle trees
- do not generate binary deltas
- do not try to repair partial or dirty bundle inputs

Fail-fast cases:

- source bundle path is missing
- target bundle path is missing
- either bundle lacks exactly one `fpvs_studio-*.dist-info` metadata directory
- either bundle lacks `FPVS Studio.exe`
- source or target version is not PEP 440 parseable
- target version is not newer than source version
- no files changed
- source/target bundle comparison finds paths that cannot be hashed
- output ZIP already exists unless `-Force` is passed

Suggested parameters:

```powershell
.\scripts\build_patch.ps1 `
  -SourceBundle "C:\FPVS-Studio-Releases\0.9.0b9\bundle" `
  -TargetBundle "dist\FPVS Studio" `
  -OutputDirectory "dist\patches" `
  -ReleaseCommit "<git-sha>" `
  -Force:$false
```

Optional parameters:

- `-FullInstallerPath`: records target installer size and hash in the summary
- `-SourceInstallerPath`: records source installer metadata for audit
- `-ManifestOnly`: emits manifest and summary without creating the ZIP
- `-AllowHighRiskChanges`: allows warned high-risk changes but records the override
- `-MaxPatchRatioPercent`: fails when the patch is too large relative to the installer
- `-MaxChangedFilePercent`: fails when too much of the bundle changed
- `-SignManifest`: future option for manifest signing

Implementation recommendation:

- keep PowerShell as the developer entry point
- put comparison and manifest logic in Python for testability
- keep file-copy and ZIP creation deterministic
- use compression level as an explicit option
- write the summary before ZIP creation so failed packaging can still be reviewed
- include generated artifacts under ignored `dist\patches\`

ZIP rules:

- use a single top-level directory
- use deterministic entry ordering
- use normalized `/` separators
- reject symlinks and reparse points
- reject absolute paths
- reject duplicate entries
- reject extra payload files not declared by the manifest
- prefer standard deflate compression for compatibility
- do not password-protect or encrypt ZIPs

Do not generate patch ZIPs by shelling out to arbitrary archive tools unless the command is
checked into the script and validated. Prefer Python `zipfile` with explicit checks so tests
can exercise unsafe archive cases.

## Patch Applicator Contract

Patch application should run outside the main FPVS Studio process because Windows may lock
files loaded by the running app. Use a small updater helper launched by the GUI, then exit
the GUI before mutation.

Potential implementation options:

- include a bundled helper executable built from `fpvs_studio.updates.patch_apply`
- reuse the installed `FPVS Studio.exe` with a hidden diagnostic/apply-patch CLI mode
- generate a small temporary PowerShell runner only if it is fully deterministic and
  reviewed by the main app before execution

Preferred first implementation: a bundled helper executable or app CLI mode, so patch
logic stays in typed Python code and unit tests.

Professional recommendation: use a separate helper executable if packaging cost is
reasonable. A helper can stay running after the GUI exits, can show focused progress or
failure UI later, and avoids overloading the main GUI executable with hidden operational
modes. If the helper would noticeably complicate PyInstaller, a hidden CLI mode is
acceptable for the first version, but it must be documented and covered by packaged smoke
tests.

Do not replace the executable that is currently applying the patch. If the patch helper
itself changes, either require the full installer or copy the source-version helper to a
temporary update-cache path and run that copy before mutating the install directory. The
first implementation should treat helper updates as full-installer-only unless the temporary
helper-copy flow is explicitly designed and tested.

Responsibilities:

- read a downloaded patch ZIP from the update cache
- extract to a fresh temporary directory
- validate the manifest schema
- validate source and target versions
- validate all manifest paths resolve under the installed app directory
- validate current installed files match source hashes
- validate payload files match target hashes
- stage replacements in a temporary directory
- apply deletes and replacements
- verify final installed files match target hashes
- remove temporary extraction files
- restart FPVS Studio after success when requested

The helper should emit structured logs to the existing diagnostic/log location if available,
or to a patch-specific log in the update cache. It should return non-zero on failure.

Recommended helper invocation:

```text
FPVS Studio Patch Helper.exe
  --apply-patch "<cache>\patches\FPVS-Studio-Patch-0.9.0b9-to-0.9.0b10.zip"
  --install-dir "%LOCALAPPDATA%\Programs\FPVS Studio"
  --expected-source-version "0.9.0b9"
  --expected-target-version "0.9.0b10"
  --restart
```

The GUI should write a small handoff file before launching the helper:

```json
{
  "operation": "apply_patch",
  "patch_zip": "...",
  "install_dir": "...",
  "source_version": "0.9.0b9",
  "target_version": "0.9.0b10",
  "restart": true,
  "created_utc": "2026-05-11T00:00:00Z"
}
```

The helper should validate command-line arguments against the handoff file. This gives a
diagnostic record of what the GUI intended and makes failed updates easier to support.

## Running Process And Lock Handling

The GUI must exit before mutation starts. The helper should wait for the original GUI
process ID to exit instead of sleeping for an arbitrary time.

Recommended handoff flow:

1. GUI downloads and validates patch metadata.
2. User chooses `Apply Patch and Restart`.
3. GUI writes handoff file.
4. GUI launches helper with patch path, install dir, versions, and current process ID.
5. GUI exits.
6. Helper waits for the process ID to exit with a bounded timeout.
7. Helper validates installed source files.
8. Helper applies the patch.
9. Helper restarts FPVS Studio on success.

Failure rules:

- if the GUI process does not exit before timeout, fail with a clear message
- if any installed file is locked, fail and direct the user to close FPVS Studio
- if another FPVS Studio process is running from the same install dir, fail
- if the helper is not running from the expected install dir, fail
- if the install dir does not look like FPVS Studio, fail
- if the patch would replace the running helper executable, fail unless the tested
  temporary helper-copy flow is active

Do not force-kill the app in the first implementation. Ask the user to close it and retry or
use the full installer.

## Atomicity And Recovery

True atomic replacement of a full Windows application directory is difficult without an
installer service. The first patch implementation should use a staged, fail-fast approach
with narrow recovery rules:

1. Validate everything before touching installed files.
2. Copy payload files into a staging directory.
3. For each replacement, rename the installed file to a backup path in the same directory.
4. Move the staged target file into place.
5. Verify the target hash.
6. Delete backups only after the full patch succeeds.

If replacement fails after mutation:

- stop immediately
- attempt to restore files already backed up in this patch transaction
- report the failure and restoration status
- direct the user to run the full installer if the install tree may be inconsistent

Do not keep applying remaining files after one replacement fails.

## Backup And Repair Policy

Patch backups should be transaction-scoped, not a general rollback feature.

Recommended backup layout:

```text
updates/
  backups/
    0.9.0b9-to-0.9.0b10-20260511T021500Z/
      manifest.json
      files/
        _internal/
          ...
```

Backup rules:

- create backups only for files changed or deleted by the current patch
- store backup paths relative to the install dir
- verify backup hashes immediately after copying or renaming
- keep backups until final target verification succeeds
- delete backups after success unless `--keep-backup` is used for diagnostics
- never back up user project data
- never restore files from a different source version

If a patch fails after mutation and restore succeeds, the helper should report:

```text
Patch failed and FPVS Studio was restored to 0.9.0b9.
Use the full installer if the problem repeats.
```

If restore fails, the helper should report:

```text
Patch failed and automatic restore did not complete.
Run the full FPVS Studio installer to repair the application.
User projects and settings are not stored in the install folder.
```

Do not present rollback as a normal user-facing downgrade feature. Downgrades should remain
out of scope unless a future release explicitly designs them.

## Resume And Partial State Policy

The helper should detect partial patch state on startup:

- active handoff file
- temporary extraction directory
- transaction backup directory
- files with `.patch-new` or `.patch-old` suffixes

For the first implementation, partial state should block patch application and present a
repair instruction instead of attempting complex automatic resume. A later version can add a
tested resume mechanism if real-world failures justify it.

The full installer remains the primary repair mechanism.

## Update Checker Selection Logic

Extend GitHub Release parsing to discover both installer and patch assets.

Current:

```text
release tag -> latest version
release asset -> FPVS-Studio-Setup-*.exe
```

Future:

```text
release tag -> latest version
release asset -> required full installer
release assets -> optional patch packages
installed version + latest version -> exact patch candidate
```

Selection rules:

1. Ignore draft releases.
2. Preserve current prerelease behavior:
   - prerelease users may see prerelease updates
   - stable users ignore prereleases by default
3. Require exactly one full installer matching the latest version.
4. Prefer a patch only when:
   - asset name matches `FPVS-Studio-Patch-<current>-to-<latest>.zip`
   - manifest inside the ZIP can be fetched or downloaded and parsed
   - manifest `source_version` equals installed version
   - manifest `target_version` equals latest version
   - manifest package/app identity matches FPVS Studio
5. If multiple patch assets match the same source/target version, fail the patch path and
   offer the full installer.
6. If no patch matches, use the full-installer workflow.

For the first implementation, manifest validation may occur after downloading the patch
ZIP. A future optimization can publish standalone `.manifest.json` sidecar assets so the
app can validate patch metadata before downloading the ZIP.

Recommended update result model:

```text
UpdateCheckResult
- current_version
- latest_version
- update_available
- release_url
- release_notes_summary
- full_installer_asset
- recommended_artifact_kind
- patch_asset
- patch_manifest
- patch_validation_status
- patch_rejection_reason
- is_prerelease
```

Recommended artifact kind values:

- `none`: app is current
- `patch`: exact patch is available and preferred
- `installer`: full installer is required or chosen
- `blocked`: release metadata is invalid and no safe update can be offered

Patch rejection should be explicit and testable:

- `no_exact_patch`
- `duplicate_patch_assets`
- `missing_manifest_sidecar`
- `manifest_version_mismatch`
- `manifest_package_mismatch`
- `manifest_schema_unsupported`
- `patch_asset_name_mismatch`
- `patch_too_large`
- `release_missing_full_installer`

The GUI can convert these into user-facing copy. The backend should not hide the reason.

## Download Cache Contract

The existing updater already stores installers in a user-writable update cache. Extend that
cache to support patch downloads.

Cache contents:

```text
updates/
  installers/
    FPVS-Studio-Setup-0.9.0b10.exe
  patches/
    FPVS-Studio-Patch-0.9.0b9-to-0.9.0b10.zip
  temp/
    patch-apply-<timestamp>/
```

Rules:

- never write downloads into the install directory
- reuse a cached patch only when asset name, expected size, and hash metadata match
- clean temporary extraction directories after success
- leave failed patch logs available for diagnostics
- do not delete full installer downloads when downloading a patch

Cache validation rules:

- check cached asset size before reuse
- check cached asset SHA-256 before reuse when known
- store download metadata beside each asset
- write downloads to a temporary filename first
- rename into final cache filename only after hash validation
- never apply a partially downloaded patch
- delete stale temporary downloads on next manual update check

Suggested metadata file:

```json
{
  "asset_name": "FPVS-Studio-Patch-0.9.0b9-to-0.9.0b10.zip",
  "download_url": "https://...",
  "size_bytes": 8800000,
  "sha256": "...",
  "downloaded_utc": "2026-05-11T00:00:00Z",
  "source_version": "0.9.0b9",
  "target_version": "0.9.0b10"
}
```

Cache cleanup should be conservative:

- keep the most recent installer
- keep the most recent patch for the installed version
- remove temp directories older than a short threshold
- keep failure logs longer than temp extraction files
- never clean user project directories

## GUI Requirements

Update dialog changes:

- show whether the recommended update is a patch or full installer
- show patch size and full installer size when both are available
- keep `Download Full Installer` available when a patch is recommended
- preserve release notes behavior
- preserve explicit final confirmation before closing the app
- show a clear validation failure reason if a patch cannot be applied
- avoid exposing PyInstaller/Inno details unless needed for actionable diagnostics

Startup silent checks:

- may silently discover patch availability
- must not auto-download or auto-apply patches
- must not show patch errors during startup unless the user starts the update flow

Manual checks:

- should expose patch validation/download failures clearly
- should offer the full installer after patch validation failure

Recommended dialog states:

- `checking`: querying release metadata
- `current`: no update available
- `update_patch_available`: patch recommended and full installer optional
- `update_installer_required`: no exact patch or patch rejected before download
- `downloading_patch`: patch download in progress
- `downloading_installer`: full installer download in progress
- `ready_to_apply_patch`: patch downloaded and basic validation passed
- `ready_to_install`: installer downloaded
- `patch_blocked`: patch cannot be used; full installer offered
- `handoff_failed`: helper could not be launched

Recommended copy principles:

- name the current and latest versions
- name whether the download is a patch or full installer
- show approximate download size
- keep the full installer as a visible alternative when practical
- avoid terms like "bundle fingerprint" in normal success UI
- show exact technical reason only in failure details
- never say a patch is safer than the installer

The app should not expose a "choose patch file" button. User-selected patch files create
trust and support problems. Patch files should come only from the configured update source.

## Security And Trust Boundaries

Patch updates increase the risk surface because they directly replace installed files.
Minimum guardrails:

- only discover patch assets from the configured GitHub Releases endpoint
- only download over HTTPS
- only accept exact package names and manifest identity fields
- verify all source and target hashes
- reject absolute paths and parent-directory traversal
- reject symlinks or reparse-point payload entries in ZIP files
- reject ZIP entries not declared in the manifest
- reject manifest entries not present in the ZIP payload
- never execute files from inside the patch ZIP
- do not apply patches to arbitrary user-selected folders
- do not patch user data directories

Future hardening:

- publish SHA-256 sidecar files for installer and patch assets
- sign patch manifests
- code-sign installer and helper executable
- verify Authenticode signatures before executing helpers or installers
- add a public release-signing key once the release process supports it

## Signing And Trust Policy

Professional recommendation: treat code signing as part of the release workflow before
making patch updates common. Hashes prove content consistency, but signing establishes
publisher identity and reduces OS/browser trust friction for downloaded executables.

Minimum signing direction:

- sign the full installer
- sign `FPVS Studio.exe`
- sign the patch helper executable if one is added
- timestamp signatures
- record signing certificate subject and thumbprint in release metadata
- verify helper signature before launching it when practical

Patch ZIPs cannot rely on Windows executable signing by themselves. The patch system should
therefore verify:

- GitHub Release asset identity
- manifest identity
- patch ZIP SHA-256
- embedded manifest consistency
- payload file SHA-256
- installed source-file SHA-256

Future signed-manifest design:

```text
patch-manifest.json
patch-manifest.sig
```

The signature should cover the canonical JSON bytes of the manifest. If this is added, the
public verification key or certificate trust rule must be bundled with FPVS Studio before
the first signed patch is required.

Do not block the first implementation on signed manifests if it would delay a practical
patch workflow, but do not skip Authenticode signing for helper executables once patches are
distributed to real users.

## Supply Chain Rules

- build patches only from local release artifacts produced by trusted scripts
- do not download a previous bundle from arbitrary URLs during patch generation
- do not use GitHub Release assets as the sole source of truth without verifying hashes
- do not allow patch manifests to run commands
- do not include post-apply scripts in patch ZIPs
- do not allow remote configuration to change install paths
- do not auto-apply patches in the background
- do not support unauthenticated alternate update feeds in the first implementation

If a future enterprise update feed is added, it should have its own explicit trust model and
tests.

## Packaging Documentation Changes

Update `docs/PACKAGING.md` to describe:

- when patch packages are allowed
- why every release still includes a full installer
- how to preserve the previous release bundle for patch comparison
- how to run `scripts/build_patch.ps1`
- patch artifact naming
- patch smoke tests
- upload order for GitHub Releases

Update `packaging/AGENTS.md` to document:

- patch scripts belong in `scripts/`
- patch artifacts remain ignored under `dist\patches\`
- patch logic must not mutate user data
- patch generation compares built bundles, not source files

Update `ARCHITECTURE.md` after implementation to mention:

- optional patch assets in the update flow
- patch applicator/helper ownership
- update backend still remains PySide6-free

## Proposed Files

New files:

- `scripts/build_patch.ps1`
- `src/fpvs_studio/updates/patch_manifest.py`
- `src/fpvs_studio/updates/patch_builder.py` if Python owns comparison logic behind the
  PowerShell entry point
- `src/fpvs_studio/updates/patch_apply.py`
- `tests/unit/test_patch_manifest.py`
- `tests/unit/test_patch_builder.py`
- `tests/unit/test_patch_apply.py`

Likely changed files:

- `src/fpvs_studio/updates/models.py`
- `src/fpvs_studio/updates/github_releases.py`
- `src/fpvs_studio/updates/downloader.py`
- `src/fpvs_studio/updates/installer.py`
- `src/fpvs_studio/gui/update_dialog.py`
- `src/fpvs_studio/gui/controller.py` only if action wiring needs new labels or state
- `scripts/build_release.ps1` only if it should optionally call the patch build script
- `scripts/smoke_packaged_app.ps1` if packaged diagnostics should validate patch support
- `docs/PACKAGING.md`
- `ARCHITECTURE.md`
- `packaging/AGENTS.md`

Avoid changing compiler, runtime, engine, preprocessing, or project-model code.

## Implementation Phases

### Phase 0: Release Policy And Fixtures

- document patch eligibility rules in packaging docs
- create miniature bundle fixtures for manifest and builder tests
- define release summary format
- define high-risk file categories
- decide whether sidecar manifests are required in version 1
- decide helper executable versus hidden CLI mode

Exit criteria:

- the plan has no unresolved decisions that block implementation
- test fixtures can model changed, added, and deleted bundle files
- packaging docs explain when not to ship a patch

### Phase 1: Manifest And Build Tool

- define patch manifest dataclasses and JSON schema validation
- implement deterministic bundle hashing
- implement source/target bundle diffing
- implement patch ZIP creation
- add unit tests with temporary miniature bundle trees
- document manual use of `scripts/build_patch.ps1`

Exit criteria:

- script builds a deterministic patch ZIP from two test bundle trees
- manifest rejects unsafe paths and invalid versions
- no GUI or updater behavior changes yet

### Phase 2: Patch Applicator

- implement manifest/payload validation
- implement installed-tree source-hash validation
- implement staged replacement and deletion
- implement post-apply target-hash verification
- implement structured failure result
- add unit tests for success, hash mismatch, path traversal, missing file, deletion, and
  rollback attempt

Exit criteria:

- applicator can patch a temporary installed tree
- applicator fails before mutation when preconditions are wrong
- applicator returns non-zero or typed failure for every tested invalid case

### Phase 3: Release Discovery And Download

- extend release models to include optional patch assets
- parse patch asset names
- choose exact current-to-latest patch when available
- keep full installer asset mandatory
- extend downloader cache paths for patch ZIPs
- add unit tests for stable/prerelease behavior, no patch, one patch, duplicate patches,
  malformed patch names, and missing full installer

Exit criteria:

- update check result can say `patch_recommended`
- existing full-installer update behavior remains unchanged when no patch is present

### Phase 4: GUI Update Flow

- update dialog copy and buttons for patch-vs-installer choices
- run patch download and validation on Qt worker threads
- launch helper/apply mode after final confirmation
- exit the GUI before mutation
- preserve explicit full-installer fallback choice
- add pytest-qt smoke coverage for dialog states

Exit criteria:

- GUI never blocks during patch checks/downloads
- manual update check clearly distinguishes patch and full installer
- startup check stays silent unless an update is available

### Phase 5: End-To-End Packaging Smoke

- build source and target bundles locally
- generate patch ZIP
- install source version
- apply patch through the app workflow
- confirm app restarts into target version
- confirm `File > Check for Updates` reports current afterward
- confirm project roots, templates, QSettings, `runs/`, and `logs/` are untouched

Exit criteria:

- patch update works on a clean Windows install
- full installer update still works
- full release documentation names both paths

### Phase 6: Signing And Release Hardening

- add signing metadata to manifests
- sign helper executable and installer in the packaging workflow
- add optional manifest signature verification
- add release checksum sidecars
- add tests for signature/checksum mismatch behavior where practical

Exit criteria:

- release artifacts have an auditable trust story
- unsigned or mismatched helper binaries are not launched silently
- patch releases remain optional if signing infrastructure is unavailable

## Test Plan

Unit tests:

```powershell
.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_patch_manifest.py
.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_patch_builder.py
.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_patch_apply.py
.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_update_check.py
.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_update_download.py
```

GUI tests:

```powershell
.\.venv3.10\Scripts\python -m pytest -q tests\gui\test_update_dialog.py
```

Packaging and metadata checks:

```powershell
.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_package_metadata.py
.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_harness_docs.py
.\scripts\smoke_packaged_app.ps1
```

Release-script checks:

```powershell
.\scripts\build_release.ps1
.\scripts\build_patch.ps1 `
  -SourceBundle "<previous bundle>" `
  -TargetBundle "dist\FPVS Studio" `
  -OutputDirectory "dist\patches"
```

Full gate:

```powershell
.\scripts\check_quality.ps1
```

Manual smoke tests:

- update from exact source version with patch available
- update from older version with no exact patch, full installer offered
- corrupted patch ZIP fails before mutation
- valid patch ZIP with modified installed source file fails before mutation
- locked installed file fails clearly and suggests the full installer
- user cancels before apply, app remains unchanged
- helper applies patch and restarts app
- app reports target version after patch
- uninstall still removes only installed app files, not user data

Patch-builder test matrix:

- identical bundles fail with `no files changed`
- source version newer than target fails
- missing source metadata fails
- duplicate metadata directories fail
- added file appears as `add`
- changed file appears as `replace`
- removed file appears as `delete`
- unsafe path is rejected
- symlink or reparse-point entry is rejected
- native dependency changes trigger warnings or failures
- patch ratio threshold is enforced
- generated ZIP entry ordering is deterministic

Patch-applicator test matrix:

- successful replace/add/delete transaction
- source hash mismatch fails before mutation
- payload hash mismatch fails before mutation
- missing installed source file fails before mutation
- existing target for `add` fails before mutation
- missing source for `delete` fails before mutation
- locked file returns a clear failure
- path traversal entry is rejected
- undeclared ZIP entry is rejected
- duplicate ZIP entry is rejected
- restore succeeds after simulated mid-transaction failure
- restore failure reports full-installer repair path

Update-checker test matrix:

- stable installed version ignores prerelease target
- prerelease installed version sees newer prerelease target
- missing full installer blocks update
- exact patch is recommended
- no exact patch selects full installer
- duplicate exact patch assets block patch path
- malformed patch asset name is ignored or rejected deterministically
- sidecar manifest mismatch blocks patch path
- unsupported schema blocks patch path
- patch too large selects full installer when policy requires it

GUI smoke matrix:

- patch recommended state
- full installer required state
- patch blocked with full installer alternative
- patch download progress
- installer download progress
- user cancels before helper handoff
- helper launch failure is shown clearly
- startup check does not auto-download
- manual check exposes technical failure details on demand

## Acceptance Criteria

- Every release can still be shipped with only the full installer.
- Patch packages are optional release assets.
- Patch packages are exact source-version to target-version artifacts.
- Patch generation compares completed bundle trees, not source files.
- Patch manifests include source/target versions, file actions, sizes, and SHA-256 hashes.
- Patch application validates all source files before replacing anything.
- Patch application rejects unsafe paths and undeclared ZIP entries.
- The GUI recommends a patch only when one exactly matches the installed version.
- The user can choose the full installer even when a patch is available.
- Patch downloads and validation do not block the GUI thread.
- The running app exits before installed files are replaced.
- Failed patch validation gives a concrete reason and does not mutate app files.
- User settings, projects, templates, run history, and logs remain outside the patch scope.
- Full installer update behavior remains supported and tested.
- Published patch assets are immutable; fixes use a new version or full installer path.
- Patch summaries classify changed files and flag high-risk categories.
- Release docs explain patch eligibility and when to avoid patch shipping.
- Patch sidecar manifests are validated before recommending a patch when implemented.
- Helper handoff waits for the GUI process to exit instead of sleeping blindly.
- Partial patch state blocks further patching until repaired or cleaned safely.
- The update dialog never asks users to manually choose patch files.

## Open Decisions

- Whether to publish standalone `.manifest.json` sidecar assets for patch metadata before
  downloading ZIP files.
- Whether the patch applicator should be a separate helper executable or a hidden CLI mode
  of the existing bundled app.
- Whether `build_release.ps1` should optionally invoke `build_patch.ps1`, or whether patch
  generation should remain an explicit second command.
- Whether patch ZIPs should be code-signed or only hash-verified for the first release.
- Whether to keep backups after successful patching for diagnostics, or delete them
  immediately to keep the install folder clean.
- Whether to require code signing before public patch releases, or allow an internal-only
  unsigned patch pilot.
- Whether to keep patch-generation thresholds as hard failures or warning gates requiring
  maintainer override.
- Whether to preserve previous release bundles manually, in a release archive folder, or in
  a private artifact store.
- Whether to publish direct patches from more than one previous version for important
  releases.
- Whether future enterprise deployments should use this updater or evaluate MSIX/App
  Installer instead.

## Assumptions

- Most patch releases change bundled Python/application files, not large binary
  dependencies.
- The PyInstaller `onedir` layout remains the install artifact wrapped by Inno Setup.
- The app continues to install per-user under `%LOCALAPPDATA%\Programs\FPVS Studio`.
- GitHub Releases remain the source of update truth.
- Every target release includes a full installer asset.
- Users should not be asked to manually unzip or apply patch files.
