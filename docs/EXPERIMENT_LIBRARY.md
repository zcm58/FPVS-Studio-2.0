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
Each opening or Refresh fetches current availability. The service matches catalog
entries to uploaded assets on live, published GitHub releases using asset ID,
filename, size and SHA-256. Deleted releases/assets, drafts and incomplete or changed
uploads are excluded even if their catalog metadata remains. GitHub failures show
an error; they never masquerade as an empty library. Downloads recheck availability
in case the selected asset was deleted after browsing. Existing local copies remain
unchanged. Available versions are not collapsed into a latest-only listing.
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
Newly prepared Library bundles explicitly use `COM3` until a serial-port editor is
added. This temporary publishing policy replaces the source port even when it is
blank, unset or customized; it does not change ordinary local bundle exports or
previously downloaded projects.

Cancel or Escape during a download waits for the active read to stop; no import starts
after cancellation. During Library project extraction, **Cancel setup** requests cleanup
and keeps progress alive until the worker finishes. An import that has already committed
is retained and reported as a successful local project even if Cancel arrives too late.
Closing Studio cancels app-owned work and defers teardown until the worker threads exit.

**Disconnect this computer** revokes its device access, removes the local credential,
and clears recognized Library cache files. Network failure retains retryable connection
state; an already-revoked credential can still be removed. Previously installed projects
remain editable and usable offline. Disconnecting cannot remove copies on other machines.

## Project version checks

Opening a linked project checks the Library once in an app-owned worker. There is no
periodic polling or automatic installation. A newer release adds a passive Home notice;
**Review update...** and **File > Update Project Version...** open the same nonmodal
dialog. Checks never take focus or open a dialog during presentation. Offline, revoked
or unavailable service states do not block project opening or claim the project is current.

The dialog shows the installed and latest versions, release description and minimum
Studio version. **Open new version separately** uses the existing verified download,
bundle review, Save/Discard/Cancel guards and display-settings review. The current
project's setup, local edits, logs and participant data stay in its existing folder;
the imported project gets its own collision-safe folder and version record. A newer
release requiring a newer Studio build remains visible with installation disabled.

New Library imports atomically include `.fpvs-library/project-origin.json`, storing
the service origin, stable item identity, installed version, verified bundle SHA-256,
local project ID and automatic-check preference. `core/library_origin.py` owns this
bounded local receipt; `core/project_bundle.py` writes it before the import commit.
It contains no credentials and is excluded from ordinary bundles and clean publication.
Moving the entire local project retains it; exporting/importing a general bundle does not.

Earlier downloads and manually created projects have no trustworthy Library identity.
Use the version dialog to link one explicitly; enter its installed version only when
known, otherwise leave it unknown. Studio never guesses from a title or folder name.
**Change library link...** can correct an association. The project-local checkbox
controls checks on open; the manual Check action still works when automatic checks are off.

`library/project_updates.py` compares semantic versions by item identity, so removal of
the installed release does not prevent discovery of a newer one. Changed bytes under the
same version and ambiguous equivalent versions are reported explicitly. The saved
service origin cannot redirect credentials or requests away from the configured client.
`gui/project_update_controller.py` owns jobs, cancellation, stale-window suppression,
passive notices and explicit import handoff. The dialog minimum/default is `760x680` /
`820x720`; Home notice acceptance includes `760x520` and `1120x720` with long content.

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

## Developer publishing in Studio

Developer tools ship in both source and installed builds and default to disabled.
Open **Settings > Advanced**, select **Enable developer mode**, enter `developer`,
and select **Enable**. Close and reopen FPVS Studio before the publishing action
appears under **File > Export**. Disabling also requires a restart. The Advanced tab
shows the saved preference and whether a restart is pending; incorrect passwords or
canceling an unlock never enable it. No automatic restart interrupts unsaved work.

`developer/enabled` is a per-user app preference in the existing QSettings store. The
controller captures it once at startup, so project switches cannot activate a pending
change. It persists through normal updates without becoming project/bundle data.
No developer launcher, source checkout, external publisher script, or Python install
is needed by the packaged GUI. The old environment-variable opt-in is no longer used.

The requested password is a convenience gate, not GitHub authorization. Before uploading,
the bundled publisher verifies GitHub user `zcm58`, the fixed private repository,
and write permission. It obtains a credential from the maintainer's existing
noninteractive Git credential helper (Git must be installed and signed in on a publishing
machine), or an explicitly configured `GH_TOKEN`. No GitHub credential is bundled,
saved in settings, collected by the developer-password field or written into projects.
The download service's read-only App and researcher invitation/device credentials
cannot publish. A different account knowing the developer password gains the interface,
not repository write permission.

1. Open the experiment and select **Publish to Experiment Library...**. Wait for the
   account check, then enter its Library title, stable study ID, version, description
   and minimum Studio version.
2. Prepare the bundle. Pending editor changes must save successfully first. Preparation
   copies through the existing clean publishing exporter, without uploading. Review the
   file counts, archive size, checksum, included/excluded paths and sanitized settings.
3. Select **Publish** after reviewing that exact bundle. The worker uploads/verifies
   its immutable Release asset, then commits the merged `catalog.json` directly to
   GitHub `main`. No manual metadata editing, Git commit or push is needed in this flow.
4. Success is shown only after catalog publication is confirmed. Researchers can then
   refresh the Library. A newer publication never changes an already installed copy.

Keep the same study ID and increase the version for a revised experiment. Fields lock
after preparation so Publish cannot send different metadata from the reviewed bundle.
Failed publications retain their prepared files and can retry the same payload.
Cancellation checks run between requests and during hashing/upload reads. An active
network request may take its timeout (30 seconds, or 120 seconds for uploads) to return;
credential lookup has a 30-second timeout. App shutdown waits for the worker.
Stopping an upload does not guarantee GitHub rolled back requests already received;
Studio reports an uncertain outcome and preserves the bundle for recovery. Reopen the
publisher to retry an in-session prepared publication. Do not regenerate different
bytes under an already used version or release tag.

An interrupted GitHub upload can leave an incomplete `starter` asset without a
checksum. Retry can recover this placeholder after its last update is at least five
minutes old: Studio rehashes the retained bundle, rechecks the release and asset,
removes only the matching uncatalogued placeholder on an unpublished draft, and
uploads the same bytes. Recent uploads, published releases, catalogued assets, and
completed assets with missing or mismatched hashes are never replaced automatically.
The replacement must pass the normal size/SHA-256 checks before release or catalog
publication. See [GitHub's failed-upload behavior](https://docs.github.com/en/rest/releases/assets#upload-a-release-asset).

The bundled publisher fetches the current online catalog, merges existing experiments, and updates
it using GitHub's file SHA. A concurrent change causes a bounded refetch/merge retry;
conflicting changes to the same published version are refused. GUI publication does
not modify the service checkout's working files. Run `git pull --ff-only origin main`
there before subsequent manual repository work. The Contents API requires repository
write access and the current file SHA for replacement; see
[GitHub's Contents API](https://docs.github.com/en/rest/repos/contents?apiVersion=2026-03-10#create-or-update-file-contents).

## Preparing complete projects for publication from the command line

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
authored word lists, task media and the complete project's tasks/modifiers.
Modifier-owned base, target, mask, backdrop and fixation images use the same contained
asset ownership as ordinary bundle exports. A canonical
`stimuli/manifest.json` is still required, including an empty one for native-only projects.
The exporter omits unrelated media and files outside the declared asset closure, including logs, runs,
caches, receipt folders and credentials. It clears participant electrode selections,
the source monitor name and app-local condition-profile identity. Every Library
bundle sets `settings.triggers.serial_port` to `COM3`, including preparation from an
existing bundle. Serial-port editing in the GUI is deferred; the source project or
archive remains unchanged.
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

For command-line publishing, use the Studio Python environment; the private repository
script delegates to `fpvs_studio.developer.catalog_publisher`. The GUI does not need
this checkout. The maintainer needs write access to the private
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
does not infer compatibility from the study's features. Preparation reports may be up
to 16 MiB; the published catalog retains its separate 1 MiB bound.

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
| Developer publisher | 860×680 | 940×760 |
| Settings with Library access | 700×604 | Minimum |
| Settings with local Test Mode | 700×694 | Minimum |
| Settings with AB Pilot Mode | 700×764 | Minimum |

In an approved visible session, check both themes, display scaling, long titles and
descriptions, empty/error/disconnected/busy states, keyboard navigation, and all controls
at these sizes. Exercise root-picker and Save cancellation, download Cancel/Close/Escape,
extraction cancellation, late commit, app quit and a revoked credential. Existing local
bundle import/export remains available independently of the Library.
Check **View > Experiment Library...**, both Create Project choices, and Back from
details to category to source choice. Confirm a Library selection does not create a
blank project and cancelling either path leaves existing projects unchanged.
In both source and installed builds, verify Advanced defaults off, wrong-password and
cancel handling, persistence across updates, and enable/disable requiring restart.
With developer mode active, check access denial, long descriptions/inventories, Prepare,
review, final Publish, immutable retry, cancellation and close/app quit while work is
active. Confirm normal launches and packaged builds omit the publishing surface. Tests
mock remote writes; a real new experiment is published only by an explicit Publish.

Release acceptance requires two separate machine/user profiles with different Studio
roots: enroll, list the same fixtures, install, inspect/edit Setup, disconnect networking,
reopen and compile, then test revocation on a fresh request. Verify an installed build,
an unlocked Linux keyring when supported, and a representative large archive. Source
tests do not establish visible acceptance, cross-machine access, physical timing or EEG
trigger delivery. Record unperformed checks in the active plan before release.
