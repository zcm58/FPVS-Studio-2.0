# Experiment Library

Phase 1 installs complete `.fpvsbundle` projects as independent, editable local copies.
Individual conditions, trigger-code remapping during a merge, and condition setup drafts
belong to Phase 2 of the [execution plan](exec-plans/active/private-experiment-library.md).
The Library never runs an experiment automatically or updates an existing experiment.

## Desktop workflow

Open **View > Experiment Library...** in the main window, or choose **Create Project >
Download from library** from Welcome or Home. Create Project also offers **Create
manually**, followed by the existing category, template, name and folder steps. Back
returns through those steps without discarding a manual draft. Selecting the Library
opens the browser without creating an empty project; cancelling leaves projects intact.
**Settings > Experiment Library / Manage Access...** opens the same connection controls.
Enter the lab invitation code and a friendly computer name, then select **Connect**.
No GitHub account, Git installation, installer, administrator rights, or application
restart is needed to browse and download experiments.

Enrollment is stored for the current OS user on that computer. Other user profiles
enroll separately. The code itself is not retained as the device credential. Search
by title, description, or category; select a result to see its complete description,
version, download size, file count, extracted size, and minimum Studio version.
Experiments requiring a newer Studio version remain visible with an explanation and
a disabled setup action. List titles may elide; a tooltip and the scrollable plain-text
details expose their complete values.

**Download and set up experiment** verifies the payload, then enters the ordinary
project-bundle review. Select the configured Studio Root Folder if necessary and confirm
the destination. Existing folders receive collision-safe new names. When a project is
open, the current Save/Discard/Cancel and launch-state guards run before the handoff.
The import reuses the normal display-settings review and opens the local project.
Review Setup, including display geometry, timing and desired triggers, before use.
Ordinary production preflight and hardware checks still apply.

Cancel or Escape during a download waits for the active read to stop; no import starts
after cancellation. During Library project extraction, **Cancel setup** requests cleanup
and keeps progress alive until the worker finishes. An import that has already committed
is retained and reported as a successful local project even if Cancel arrives too late.
Closing Studio cancels app-owned work and defers teardown until the worker threads exit.

**Disconnect this computer** revokes its device access, removes the local credential,
and clears recognized Library cache files. Network failure retains retryable connection
state; an already-revoked credential can still be removed. Previously installed projects
remain editable and usable offline. Disconnecting cannot remove copies on other machines.

## Service and access boundary

Private GitHub Releases in
[`zcm58/FPVS-Studio-Library`](https://github.com/zcm58/FPVS-Studio-Library)
hold versioned bundles. That repository owns the Cloudflare service, invitation/device
administration, catalog publishing and deployment. GitHub App credentials stay on the
service; desktop clients receive only authorized catalog metadata and streamed bytes.
See its operational README for live service configuration and maintainer commands.

The deployed service origin is
`https://fpvs-studio-library.fpvs-studio-zcm58.workers.dev`, declared in
`library/client.py` as `DEFAULT_LIBRARY_SERVICE_URL`. It is not a GUI preference or a
project setting. `LibraryClient(service_url=...)` is the explicit constructor seam for
isolated deployments and tests. The September 17, 2026 deployment was verified using
two independent credentials on one Windows computer: enrollment, native credential
reload, both catalog entries/downloads, import, revocation, and local reopen/compile
after disconnect. These checks do not substitute for visible or second-machine tests.

The private release `library-test-v1` contains **Library Demo - Words** and
**Library Demo - Cognitive Load**. The user-provided reusable enrollment code is a
temporary test configuration held only as a server secret hash. Each enrollment still
receives its own revocable credential. A current source checkout of
`codex/experiment-library` contains this GUI; previously published installers do not
gain it from a catalog update. No new installer or application release was published.

The current client contract uses schema version `1.0`:

| Request | Contract |
| --- | --- |
| `POST /v1/enroll` | JSON `schema_version`, `code`, `device_token`, `device_name`; response `schema_version`, `device_id`, `library_name`. |
| `GET /v1/catalog?kind=experiment` | Device bearer credential; response `schema_version`, `library_name`, `items`. |
| `GET /v1/items/{item_id}/versions/{version}/download` | Device bearer credential; exact selected item/version bytes. |
| `DELETE /v1/device` | Device bearer credential; revoke this enrollment and return JSON. |

Each catalog item contains `item_id`, `kind: experiment`, `version`, `title`,
`description`, `experiment_category`, `filename`, `size_bytes`,
`uncompressed_size_bytes`, `file_count`, `sha256`, and `min_studio_version`.
Unknown metadata fields, unsupported schemas, duplicate identities, invalid filenames,
unsupported categories and malformed versions are rejected. Phase 1 requests only
experiments; service-side filtering preserves compatibility when Phase 2 adds conditions.

Before enrollment, Studio generates a random device token and saves a pending credential
in the OS store. A lost response retries the same device identity instead of consuming a
new invitation. Windows uses Credential Manager through the native API. Linux explicitly
uses the Secret Service backend and requires an unlocked desktop keyring; unavailable
secure storage is an actionable error. There is no plaintext credential fallback in
QSettings, project files, logs, bundles or caches. Invitation lifetime, reuse limits and
revocation policy belong to the service, including any temporary test invitation.

The client rejects redirects and sends credentials only to the configured HTTPS origin.
Catalog parsing is limited to 1 MiB and 500 items; each archive must be smaller than
2 GiB, declare no more than 20 GiB extracted content and 50,000 files. The catalog's
minimum Studio version gates downloading. Current network bounds are a 10-second socket
timeout, a 30-second metadata deadline and a 30-minute transfer deadline. Reads and
hashing are chunked and cooperatively cancelable; a blocked socket may take its timeout
to return. Size and SHA-256 must match before import. Core still applies its independent
archive/member/manifest/compile validation; network metadata cannot bypass it.

## Ownership and local storage

| Owner | Responsibility |
| --- | --- |
| `library/models.py`, `errors.py` | Bounded catalog/enrollment contracts and safe user-facing errors. |
| `library/client.py` | Enrollment, authorized requests, timeouts and verified transfer. |
| `library/credentials.py` | Windows Credential Manager and Linux Secret Service adapters. |
| `library/cache.py` | Private per-user cache, no-follow checks and cross-process lease. |
| `core/project_bundle.py` | Existing whole-project archive validation, extraction and optional cancellation. |
| `core/library_publish.py` | Explicit clean publishing preparation without modifying source projects. |
| `gui/library_dialog.py`, `library_controller.py` | View state and orchestration through app-owned `update_lifecycle.py` jobs. |
| `gui/controller.py` | Existing root/review/display/document handoff and cancellable Library import. |

On Windows, downloads live under
`%LOCALAPPDATA%/FPVS Studio/experiment-library/<origin-hash>/`.
Linux uses `$XDG_CACHE_HOME/fpvs-studio/experiment-library/<origin-hash>/`, or
`~/.cache/fpvs-studio/experiment-library/<origin-hash>/` when XDG is unset.
Cache permissions restrict access to the owning user; Windows permits SYSTEM as well.
Cache paths reject links, reparse points and unsafe files. Cleanup removes only
recognized Library files. The bounded cache retains at most one verified payload plus
one partial; cached payloads are rehashed and reauthorized before reuse.

`download()` returns a verified `Path` with an interprocess cache lease. The caller must
invoke `release_download()` after review rejection, failure, cancellation or import
completion, not merely when network transfer ends. The Library controller holds that
lease while the existing importer reads the archive, preventing another Studio process
from replacing the payload. The imported project refers only to its own copied files.
No updater staging directory, installed program file or downloaded script participates.

## Preparing complete projects for publication

Use the explicit preparation tool rather than uploading an ordinary export without
review. It accepts a saved project directory or existing `.fpvsbundle`, creates a staged
copy, validates the clean export by importing it, and reports SHA-256 and inventory.
The source remains unchanged; existing outputs are never overwritten.

```powershell
# Run from the FPVS Studio source checkout. Replace the source and study values.
$studioRepo = (Get-Location).Path
$python = Join-Path $studioRepo '.venv3.10\Scripts\python.exe'
$sourceProject = 'X:\Studies\Example'
$itemId = 'example-study'
$version = '1.0.0'
$tag = "$itemId-v$version"
$bundleDir = Join-Path $studioRepo "build\library-publications\$itemId-$version"
$bundle = Join-Path $bundleDir "$itemId-$version.fpvsbundle"
$metadata = Join-Path $bundleDir "$itemId-$version.json"

& $python scripts\prepare_library_bundle.py $sourceProject $bundle --dry-run
if ($LASTEXITCODE -ne 0) { throw 'Bundle review failed.' }

# Review the inventory above before creating the publication files.
& $python scripts\prepare_library_bundle.py $sourceProject $bundle --metadata $metadata
if ($LASTEXITCODE -ne 0) { throw 'Bundle preparation failed.' }
```

`--minimum-studio-version X.Y.Z` overrides the current Studio version in review metadata.
`--dry-run` still compiles, imports and hashes a temporary bundle, then removes it; it
does not write the output bundle. The destination's parent may be created, and an
explicit `--metadata` path writes the review JSON even with `--dry-run`.
Use a new output directory for each publication. Do not save dry-run JSON there: the
publisher reads every `*.json` in the selected directory and rejects dry-run reports.

Preparation includes referenced stimulus sets, original and declared derived images,
authored word lists, task media and the complete project's tasks/modifiers. It omits
unrelated media and files outside the declared asset closure, including logs, runs,
caches, receipt folders and credentials. It clears participant electrode selections,
the source monitor name, serial-port selection and app-local condition-profile identity.
Untyped derivative provenance containing credential keys or machine-local paths is
rejected. Review authored instructions, descriptions and images before publishing a real
study: automatic field sanitation cannot determine whether free text or pixels identify
a participant. The review JSON lists included/excluded paths and sanitized fields; keep
that local inventory out of the public-facing catalog.

Generate two artificial transfer fixtures without reading real studies:

```powershell
.\.venv3.10\Scripts\python scripts/create_library_test_bundles.py "build\library-test-bundles"
```

This produces a word-stream project and a Cognitive Load project with geometric
placeholders and backward-counting tasks, plus JSON review metadata. They test transfer
and setup, not a validated research protocol. Both preparation tools only write local
files. Upload and catalog publication are separate maintainer operations in the private
Library service repository.

### Uploading and making an experiment visible

The maintainer needs write access to the private
[`FPVS-Studio-Library` repository](https://github.com/zcm58/FPVS-Studio-Library).
On this development computer its checkout is `build/experiment-library-service` inside
the Studio checkout. On another computer, clone that private repository and adjust
`$libraryRepo` below. The publisher uses `GH_TOKEN` or Git's configured credential helper;
the deployed service's read-only GitHub App key is not a publishing credential.

The preparation report already contains the title, category, minimum Studio version,
SHA-256, compressed size, counts and inventory. Add these four publishing fields while
preserving the generated values:

```powershell
$report = Get-Content -LiteralPath $metadata -Raw | ConvertFrom-Json
$report | Add-Member -NotePropertyMembers @{
    item_id = $itemId
    version = $version
    asset_name = Split-Path $bundle -Leaf
    summary = 'Describe the experiment, included stimuli, and setup the user should review.'
}
$report | ConvertTo-Json -Depth 20 |
    Set-Content -LiteralPath $metadata -Encoding UTF8
```

Use a stable lowercase, hyphenated `item_id` for one study. Use a new version, filename
and release tag when its content changes. Published item/version pairs are immutable.
The minimum Studio version defaults to the exporting checkout's version; preparation
does not infer compatibility from the study's features. The current publisher also
limits each preparation report to 1 MiB, which can constrain large asset inventories.

In a clean Library checkout, update `main`, preview the release, then publish:

```powershell
$libraryRepo = Join-Path $studioRepo 'build\experiment-library-service'
Set-Location $libraryRepo
git switch main
if ($LASTEXITCODE -ne 0) { throw 'Switch the Library checkout to main before publishing.' }
git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw 'Update the Library checkout before publishing.' }

& $python scripts\publish-catalog.py --tag $tag --bundle-directory $bundleDir --dry-run
if ($LASTEXITCODE -ne 0) { throw 'Publication review failed.' }

& $python scripts\publish-catalog.py --tag $tag --bundle-directory $bundleDir
if ($LASTEXITCODE -ne 0) { throw 'Publishing failed; do not commit the catalog.' }

git diff -- catalog.json
git add -- catalog.json
git commit -m "Publish $itemId $version"
git push origin main
```

The publisher uploads a draft release, checks GitHub's asset digests and sizes, publishes
the release, and updates the local `catalog.json` while retaining existing experiments.
Review that diff before committing. Uploading an asset alone does not list it: users
see the experiment after the catalog reaches `main` and they refresh or reopen the
Library. All authorized devices see the same catalog. New machines enroll with the
lab's current invitation code; already enrolled machines keep their device credential.
Publishing compatible content requires no Worker redeployment or Studio update.
Previously downloaded projects remain independent copies and are not changed by later
publications.

## Verification and visible acceptance

```powershell
./scripts/verify.ps1 -Scope library -Tier focused
./scripts/verify.ps1 -Scope project-io -Tier focused
./scripts/verify.ps1 -Scope gui -Tier focused
./scripts/verify.ps1 -CheckConfig
./scripts/verify.ps1 -Scope repo -Tier precommit
```

Windows archive tests may need a short explicit temporary root, for example
`PYTEST_ADDOPTS=--basetemp=build/t1`, when the host lacks long-path support.
This workaround is not proof that arbitrary long paths work. Backend tests cover
credentials, enrollment retry, cache safety, bounds, corrupt transfers and publishing;
service tests run in their owning repository. Ordinary verification excludes Qt before
import. The registered `tests/gui/test_library_dialog.py` covers the view and lifecycle
with controlled clients/importers; it does not access the live service.

| Surface | Minimum | Default |
| --- | --- | --- |
| Experiment Library | 900×640 | 1040×760 |
| Welcome with four project actions | 760×520 | 1120×720 |
| Create Project, all three pages | 760×500 | 800×500 |
| Settings with Library access | 700×564 | Minimum |
| Settings with local Test Mode | 700×654 | Minimum |
| Settings with AB Pilot Mode | 700×724 | Minimum |

In an approved visible session, check both themes, display scaling, long titles and
descriptions, empty/error/disconnected/busy states, keyboard navigation, and all controls
at these sizes. Exercise root-picker and Save cancellation, download Cancel/Close/Escape,
extraction cancellation, late commit, app quit and a revoked credential. Existing local
bundle import/export remains available independently of the Library.
Check **View > Experiment Library...**, both Create Project choices, and Back from
details to category to source choice. Confirm a Library selection does not create a
blank project and cancelling either path leaves existing projects unchanged.

Release acceptance requires two separate machine/user profiles with different Studio
roots: enroll, list the same fixtures, install, inspect/edit Setup, disconnect networking,
reopen and compile, then test revocation on a fresh request. Verify an installed build,
an unlocked Linux keyring when supported, and a representative large archive. Source
tests do not establish visible acceptance, cross-machine access, physical timing or EEG
trigger delivery. Record unperformed checks in the active plan before release.
