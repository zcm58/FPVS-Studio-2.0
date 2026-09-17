# Private Experiment And Condition Library

Status: Active

Date: 2026-09-16

## Phase 1 implementation authorization

The user authorized Phase 1 implementation, private GitHub/service setup, two test
bundles, and commit/push on `codex/experiment-library`. Phase 2 remains deferred.
The user selected a temporary reusable test enrollment code, replacing
single-use invitations for this test deployment only. Devices still receive separate
revocable credentials; the shared code is configured server-side and can be disabled.
Old worktrees are archived before removal. Installed cross-machine and visible GUI
acceptance must be reported separately from source/service verification.

## Purpose And Confirmed Decisions

Provide an Experiment Library inside FPVS Studio. A researcher can browse complete
experiments or reusable conditions, download the selected version, and have Studio
install its editable settings and stimuli in the appropriate local project.

During planning, the user confirmed:

- Library content lives in a private GitHub repository.
- Researchers must not need GitHub accounts.
- Access uses a lab-issued invitation code entered once per machine.
- Phase 1 delivers complete-project browsing, download, and setup in the GUI.
- Phase 2 adds individual conditions after Phase 1 is usable and accepted.
- Phase 2 may require manual setup so users can choose their desired condition trigger
  code and other relevant settings before adding a condition to their experiment.

Phase 1 implementation and remote provisioning are now authorized. The private
`zcm58/FPVS-Studio-Library` repository has been created. Phase 2 technical choices remain
planning context until separately approved; track Phase 1 verification below.

## Phase Boundaries

| Phase | Deliverable | Completion boundary |
| --- | --- | --- |
| 1: Whole projects | Private content repository, clean whole-project publishing, invitation enrollment, authenticated catalog/downloads, and GUI setup through the existing project importer. | A researcher on another machine can enroll, download a complete experiment, review its local setup, and reopen it offline. Ship and accept this independently of condition work. |
| 2: Individual conditions | Selected-condition packaging/publishing, condition browsing, editable import setup, compatibility checks, and safe merge into an existing project. | A researcher chooses the condition name, trigger code, and supported local settings, reviews remaining project-wide requirements, and adds a validated independent copy. |

Phase 1 must not depend on condition dependency closure, merge transactions, condition
export, or a condition setup dialog. Keep those contracts below as Phase 2 context.
The Phase 1 GUI shows experiments only; add the Conditions view and Setup entry point
when Phase 2 is implemented. Preserve Phase 1 clients when extending the service/catalog.

## Recommended Design

Use GitHub Release assets for bundles and a small authenticated download service for
access. Phase 1 introduces one native Library dialog for experiments; Phase 2 extends it
with conditions. Downloaded experiments become new projects; Phase 2 conditions become
independent editable copies in the current project. Imported content remains usable offline, with no runtime service
dependency and no automatic replacement when the publisher releases a newer version.

```text
Lab maintainer -> clean export + validation -> private GitHub content repository
                                                   |
                                         catalog + Release assets
                                                   |
                                     Library service (Cloudflare)
                                      /                       \
                              invitation/device state    read-only GitHub App
                                      |
                         FPVS Studio native Library dialog
                                      |
                         download -> verify -> import review
                              /                       \
                  Phase 1: new project       Phase 2: condition setup + merge
```

The service is necessary to satisfy private GitHub storage without researcher GitHub
accounts. Never distribute a shared GitHub personal access token or App private key in
the desktop application. The service grants access only to published catalog content.

Phase 1 uses the existing whole-project `.fpvsbundle` format. Phase 2 reuses that transport:
a condition item is a minimal,
valid, one-condition project bundle containing that condition's complete dependencies.
The catalog identifies its kind and selected condition ID. This avoids introducing a
second ZIP format and lets the existing bundle importer still open it as a new project.
Adding it to an existing project requires a new core merge service; the current project
importer does not do that.

## Current Repository Evidence

Investigated checkout: `codex/cognitive-load-fpvs`, commit `2e69209`.

| Existing owner | Current behavior and implication |
| --- | --- |
| [Project bundles](../../../src/fpvs_studio/core/project_bundle.py) | ZIP-backed envelope `1.0.0`, per-file sizes/hashes, path and resource checks, compile validation, staging, and collision-safe new-project import. Reuse this owner for archive validation and extraction. |
| [GUI controller](../../../src/fpvs_studio/gui/controller.py) and [bundle review](../../../src/fpvs_studio/gui/bundle_import_dialog.py) | Welcome, dropped files, and File import converge on review, background import, and local display confirmation. Preserve this workflow for downloaded experiments. |
| [Editable models](../../../src/fpvs_studio/core/models.py) and [presentation resolution](../../../src/fpvs_studio/core/presentation.py) | Conditions reference stimulus sets, task bindings, and inherited project presentation. Protocol, fixation, trigger hardware, and session defaults are project-level. A standalone condition JSON is insufficient. |
| [Condition modifiers](../../../src/fpvs_studio/core/condition_modifiers.py), [modifier presets](../../../src/fpvs_studio/core/modifier_presets.py), and [task compilation](../../../src/fpvs_studio/core/compiler_tasks.py) | Shared definitions, typed link IDs, task media, and session baseline dependencies need transitive inclusion and remapping. Reuse existing validators and asset-reference helpers. |
| [Condition templates](../../../src/fpvs_studio/core/condition_template_profiles.py) | Local profiles contain reusable defaults, not a ready condition and its image library. Keep this feature distinct from the online Library. |
| [Project configs](../../../src/fpvs_studio/core/project_config.py) | Config interchange can carry task media but omits the main FPVS image libraries. It cannot provide the requested complete condition download. |
| [GitHub updater](../../../src/fpvs_studio/updates/github_releases.py) | Discovery is deliberately restricted to the Studio releases endpoint. Installer/cache assumptions are application-specific. Do not broaden that trust boundary to download experiment content. |
| [App-owned job lifecycle](../../../src/fpvs_studio/gui/update_lifecycle.py) | Already supports cancelable work and deferred shutdown, and is also used by reporting. Reuse it without moving library networking into widgets or the updater helper. |
| [Document persistence](../../../src/fpvs_studio/gui/document.py) and [serialization](../../../src/fpvs_studio/core/serialization.py) | Normal saving writes project JSON; it is not a transaction across project JSON, stimulus manifest, and new assets. Condition import must define its own bounded commit/recovery behavior. |

Important findings:

- Whole-project import always creates a new folder. Do not treat it as a merge API.
- Bundle export excludes `runs/`, `logs/`, and `cache/`, but serializes project state,
  including `manual_removed_electrodes`, and collects all files beneath `stimuli/`.
  Published examples therefore need a clean export path; ordinary bundle portability
  is not equivalent to removal of participant information or unused assets.
- Current import has stage progress but no cancellation parameter. A Library Cancel
  button needs backend checkpoints, not just a dismissed dialog.
- Existing machine display review must remain. Imported COM-port and display settings
  are not evidence that another machine is ready to record.
- Existing category guards prohibit incompatible designs and retired AB image pairs.
  Preserve them; reuse across compatible oddball/Cognitive Load categories should be
  decided by the existing model/compiler rules, not a blanket category-string match.

The active updater plan retains separate installed-system acceptance work. The active
feedback plan documents a separate Cloudflare/GitHub App service. Neither plan authorizes
changing those services or reusing their credentials. The planned
[lab-independent recording setup](../planned/lab-independent-recording-setup.md) remains separate;
this feature must work with today's recording checks.

## Researcher Workflow

### Phase 1: Whole projects

1. Open **Experiment Library...** from Welcome or File.
2. On first use, enter the invitation code and an optional friendly computer label.
   Later opens use the locally protected device credential. Settings offers connection
   status and **Disconnect this computer**. No Git, CLI, or GitHub login is required.
3. Browse/search experiments. Show title, description, category/modality,
   content version, required Studio version, download size, included tasks, and relevant
   protocol requirements. Incompatible entries remain explainable with import disabled.
4. Choose **Download & Set Up Experiment**. Reuse the configured
   Studio root, collision-safe folder naming, and existing import/display review. End
   with the new project open in Setup, or a clear saved location if opening is canceled.
5. Show Downloading, Verifying, and Setting up progress. Report success only after
   persistence succeeds, then open the imported experiment in Setup for user review.
   Provide actionable connection, revoked-access, disk, compatibility, and import errors.

Preserve packaged experiment settings initially. Users review the display and recording
configuration and can edit condition trigger codes and other settings through existing
Setup controls. Do not auto-run the experiment or equate successful installation with
recording readiness. This phase needs no new individual-condition import form.

### Phase 2: Individual conditions

1. Add a Conditions view to the Library and **Add from Library...** in Setup > Conditions,
   opening that same view with the current experiment as the destination.
2. Choose **Set Up & Add Condition**. After download/verification, show an editable draft
   with target experiment, local condition name, desired trigger code, instructions,
   and supported condition-level presentation/timing fields. Start from packaged values;
   offer a valid unused trigger suggestion but let the user choose another valid code,
   even when the packaged code is available.
3. Show dependencies and source-versus-target requirements alongside the draft. Clearly
   distinguish editable condition fields from project-wide settings. Revalidate every
   edit before enabling **Add Condition**; block invalid/reserved/duplicate trigger codes
   and unresolved model/compiler conflicts with actionable field-level messages.
4. Review the final changes and add the condition. Then select it in Setup. Additional
   manual configuration in existing Setup screens is an expected part of this phase,
   not a failed automatic setup. Preserve unrelated conditions and project defaults.
5. With no project open, **Create Experiment from This Condition** opens the ordinary
   project import/setup path for its minimal bundle; it still requires local setup review.

Browsing and downloading do not require saving the open experiment. Immediately before
changing or replacing its context, resolve unsaved document/editor drafts through the
existing save/discard/cancel flow. In Phase 2, recompute the condition preview against
that resulting document. Cancellation before import commitment leaves the destination
unchanged, and Cancel in the condition setup draft applies none of its edits.

Use shared GUI components. Proposed Library minimum/default sizes are `900x640` and
`1040x760`; connect/review dialogs must establish their own budgets before implementation.
Keep actions visible with long names, paths, descriptions, revoked-code messages, and
download progress. Setup must still fit all eight steps at `1120x820`.

## GitHub Repository And Publishing

Proposed private repository: `zcm58/FPVS-Studio-Library` (name to confirm at provisioning).
Keep service source and content metadata together initially; use separate Cloudflare
resources from feedback. Suggested repository structure:

```text
AGENTS.md / ARCHITECTURE.md / README.md
catalog/library.json
service/                 # Worker, invitation/device storage, tests, operations
scripts/                 # catalog validation, publish, invitation/revocation tools
docs/                    # publisher and access-management instructions
GitHub Releases          # versioned .fpvsbundle assets; binary payloads stay out of Git
```

Each catalog item version has a stable item ID, `kind` (`experiment` in Phase 1;
`condition` added in Phase 2), content version, title/description, category and modality
summary, minimum Studio version, envelope/project schema versions, requirements,
release/asset IDs, filename, compressed bytes, uncompressed bytes, file count, and SHA-256.
Content versions are independent of Studio releases. Display metadata never substitutes
for validation of the downloaded models. Reject unsupported catalog/schema versions.
Phase 2 condition items also identify the selected condition ID. Phase 1 catalog requests
explicitly select experiment entries, and the service keeps that response compatible
after condition publishing begins. Test an older project-only client against the extended
service; unsupported item kinds must never route through an unintended import action.

Use one immutable item/version release, such as `faces-oddball-v1.0.0`. Never replace an
asset under the same content version. Publish the validated asset first, verify the
uploaded identity/digest, then commit the catalog entry. Use repository commit conflict
checks for competing publishers. A failed upload cannot leave a downloadable catalog
entry; withdrawal removes availability while preserving historical metadata and local
copies. Automatic refresh of previously imported projects is outside both phases.

The maintainer exports from a saved project, reviews the package inventory, and publishes
with a documented script. Phase 1 supports clean whole-project bundles only. Phase 2 adds
**Export > Selected Condition Bundle...** to Studio so maintainers do not hand-edit JSON.
Uploading from the researcher GUI is out of scope.

Publishing must construct a clean copy of either package type, remove participant-specific
project fields (including `manual_removed_electrodes`), include only declared source,
derivative, and task-media dependencies, and exclude run output, unrelated stimuli,
credentials, and machine-local paths. Revalidate and rehash that copy. Never modify the
source experiment or silently redefine existing ordinary bundle exports. Existing bundles
must pass the same publishing preparation rather than being uploaded unquestioningly.
Phase 1 preparation retains all conditions and their declared content in the complete
project. Extracting a selected condition and computing its smaller closure belongs to
Phase 2 and is not required to publish whole experiments.

GitHub currently requires each release asset to be **under 2 GiB**. Enforce this in the
publisher and catalog client, independently of the larger local bundle extraction limits.
Oversized experiments get a clear error; multipart downloads or alternative storage are
future work, not an implicit fallback.
[GitHub release limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

## Invitation And Download Service

Propose a small Cloudflare Worker, D1 for invitation/device records, and a separate
GitHub App installed only on the library repository with Contents read permission.
The App private key remains in Worker secrets; installation tokens are generated and
renewed server-side. The desktop receives neither GitHub credentials nor repository
administration access. GitHub supports App installation tokens for reading release
assets; its binary endpoint may return data or an HTTP redirect.
[Release asset API](https://docs.github.com/en/rest/releases/assets) and
[installation authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation).

Access contract:

- Maintainer tooling issues high-entropy, expiring, single-use invitations and can list
  or revoke enrolled computers. Start with one curated library and one reader role.
  Keep administration outside the researcher app; no admin dashboard is needed in v1.
- Exchange an invitation for a random, revocable device credential through HTTPS.
  Store only credential/invitation hashes server-side. Consume invitations atomically
  and make retries safe after a lost response: persist a locally generated credential
  before redemption, and allow only the identical redemption to retry successfully.
- Store the credential in Windows Credential Manager or a supported Linux Secret
  Service backend, scoped to the local OS user and service origin. Verify storage works
  before consuming the invitation. No plaintext QSettings, project JSON, environment,
  or file fallback. Missing secure storage produces a clear setup error.
- Enrollment represents an installation/user profile, not hardware attestation. Do not
  collect MAC addresses or hardware fingerprints. A new machine/profile needs its own
  invitation. Deleting local credentials or reinstalling without them requires reenrollment.
- Authenticate catalog and download requests, check device revocation on each request,
  and rate-limit enrollment attempts and transfers. Codes/secrets never appear in URLs,
  diagnostics, access logs, exports, or error messages. Disconnect revokes when online
  and clears local credentials; offline disconnect explains that remote revocation is
  still available through maintainer tooling.
- Revocation blocks future requests. Already downloaded editable projects keep working
  offline; it cannot recall local copies or bytes already delivered in a transfer.

Proposed endpoints: `POST /v1/enroll`, `GET /v1/catalog`,
`GET /v1/items/{item_id}/versions/{version}/download`, and `DELETE /v1/device`.
Choose and contract-test exact field limits, invitation lifetime, quotas, and error codes
before connecting the desktop. Requests select catalog identities, never arbitrary
repositories, URLs, filesystem paths, or GitHub asset IDs supplied by the client.

The service resolves the item to a fixed repository asset and streams it to Studio.
Follow only validated GitHub asset redirects server-side; do not forward authorization
headers to another origin or return GitHub credentials/temporary download URLs to the
desktop. Handle both GitHub binary response forms. Stream with backpressure and bounded
reads; do not buffer entire bundles in Worker memory or place private payloads in a
public CDN cache. Use `Cache-Control: private, no-store` on authenticated payloads.
Catalog caching may use ETags and a short explicit server TTL after authorization;
revocation and quota decisions must not depend on a stale public cache.

Cloudflare documents streaming large responses without whole-body buffering. Validate a
representative large experiment, GitHub App token generation, cancellation, and concurrent
readers in staging before choosing the production plan; do not promise zero hosting cost.
[Streaming](https://developers.cloudflare.com/workers/runtime-apis/streams/),
[limits](https://developers.cloudflare.com/workers/platform/limits/), and
[secret storage](https://developers.cloudflare.com/workers/configuration/secrets/).

## Phase 2: Portable Condition And Merge Contract

This section is deferred until Phase 1 acceptance. Manual condition setup is part of the
import contract: the user edits a draft, reviews the resulting effective settings, and
commits it explicitly. Package settings provide starting values, not immutable choices.

### Package closure

Create a minimal ProjectFile and StimulusManifest from the selected condition. Include
every referenced stimulus role, original image, declared derivative, authored word list,
native AB stream configuration, bound task, task image, associated modifier, and indirect
dependency such as a counting baseline. Prune unrelated conditions, sets, modules, and
files. Remain inside current project/category/schema validators. If closure cannot form
a valid one-condition experiment, explain the dependency and require a whole experiment
package; never strip a required task to make export succeed.

Resolve inherited presentation through `core/presentation.py` and materialize equivalent
condition overrides as the initial editable draft where the model supports them. Keep project-wide requirements in
the carrier project and derive compatibility from those values on import. Include
selected generated variants so importing does not silently regenerate different images.
Do not reuse the GUI's Duplicate Condition operation: its image path creates empty sets.

### Preview and compatibility

Build a pure merge preview from the verified source, the user's setup draft, and the
current target snapshot. Keep source values available beside the chosen values, and
record deliberate adaptations in the import receipt:

| Setting/dependency | Import rule |
| --- | --- |
| Condition names and IDs | Let the user choose a unique local name; generate new condition/set/task/modifier/link identities and rewrite all references. Never overwrite based on a matching name. |
| Source media | Copy into new project-owned namespaces; preserve bytes, hashes, provenance records, and project-relative POSIX paths. Do not link to the download cache or source machine. |
| Instructions, presentation, and condition timing | Initialize from effective packaged values and allow supported edits through existing model-backed controls, including instructions, presentation/lead-in, repetitions, and timing mode where applicable. Validate the chosen values against the destination's display and shared timing rules; summarize deliberate changes. |
| Protocol, fixation, shared repeat-cycle constraints, event semantics | Compare fields actually used by the compiler. Show field-level source/target differences. Permit an explicit adaptation only when existing condition fields can express it and validators pass; otherwise direct the user to resolve project-wide settings through normal Setup or use a separate experiment. Never silently update global settings or invent per-condition overrides. |
| Condition triggers | Make the desired code editable, with the packaged code or a valid unused code as the initial suggestion. Validate current event-code rules, collisions, and reserved values before Add Condition. Confirm the chosen mapping; do not change existing condition codes or the locked oddball policy. |
| Session ordering, blocks, seeds, participant settings, hardware | Destination owns these values. Show that imported conditions participate in its session. Do not import source participant history, COM-port selection, or machine settings into an existing project. |
| Tasks/modifiers | Preserve binding order and all indirect requirements, remap typed references, and use existing baseline/link validators. Surface any added session baseline in review; conflicting baselines block import. |
| Category and schema | Preserve the target category. Run existing category/model validators and migrations; reject unsupported features. Do not convert retired AB designs. |

If the user leaves the import flow to change project-wide Setup settings, rebuild the
preview from the saved/current destination before continuing. Such edits are a separate
explicit project action; the importer cannot use consent to add a condition as consent
to change every existing condition. A manual setup choice never bypasses validation.

Same-name assets or matching hashes do not justify shared mutable references between
projects. No cross-project deduplication, dependency registry, or live subscription is
needed. Repeated imports offer **Already added** with a deliberate **Add another copy**
path; intentional copies get new identities and never silently upgrade the earlier one.

New experiment construction must work before every condition is launchable. Validate
the imported condition in a complete carrier project, then merged structural/category/
dependency/shared-setting rules. Dry-run the full merged session when the target is
otherwise ready; preserve unrelated incomplete-condition diagnostics without claiming
the experiment is ready to run. A newly introduced incompatibility always blocks commit.

### Persistence and recovery

Expose a small public verified-staging operation from `core/project_bundle.py`, shared
by ordinary project import and condition import. Preserve its existing archive checks;
do not copy private ZIP extraction code into the GUI or network package. Add cooperative
cancellation during download, hashing, extraction, and validation, up to commitment.

Condition import stages new assets and both JSON documents on the destination filesystem.
Use the existing Windows path helpers, absolute document root, containment checks, and
no-follow checks for symlinks/reparse points. Before commit, prevent concurrent Studio
edits/imports and recheck the project/manifest snapshot against disk. A changed destination
invalidates the preview. Never block the GUI waiting on a worker.

Use a narrowly scoped transaction marker and backups for this multi-file operation:
publish only newly owned asset paths, replace the manifest and project JSON through
temporary-file replacement, and record completion. Test failure between every step.
On exception restore original JSON and remove only this operation's new files. On restart,
resolve an unfinished marker before allowing project editing or launch. Preserve ambiguous
backups for recovery rather than guessing. Do not claim that two file replacements form
one atomic filesystem transaction. Once the short commit begins, defer cancellation until
commit or rollback finishes, with a visible **Finishing setup** state.

Record a local receipt under `<project>/.fpvs-library/` with item/version, SHA-256, time,
local IDs, and any reviewed mapping. It contains no access credentials and is informational,
not a live dependency. Include receipt persistence in the commit. Existing bundle export
excludes this local metadata directory; portable provenance is deferred so Phase 2 does not
need a new ProjectFile schema or a change to the existing bundle envelope.

## Ownership And Implementation Boundaries

- Phase 1 `src/fpvs_studio/library/`: GUI-neutral service/catalog contracts, credential
  adapter, HTTPS client, bounded download cache, and transfer validation. It must not
  import Qt, runtime, engines, or installer code. Add its own concise `AGENTS.md`.
- `core/project_bundle.py`: the one archive owner; Phase 1 adds the optional cancellation
  needed for project downloads/imports. Phase 2 exposes shared verified staging for merge.
  Neither phase weakens local import/export compatibility.
- Phase 2 `core/condition_bundle.py` (proposed): dependency closure, editable compatibility preview,
  identity remapping, project merge, and scoped transaction/recovery. Reuse core models,
  presentation, paths, task assets, and preprocessing manifest services.
- `gui/library_dialog.py` and `gui/library_controller.py`: view state and
  orchestration through the existing app-owned job coordinator. Register only small
  entry-point hooks in Welcome, File, and Settings in Phase 1; add Conditions in Phase 2.
- Network staging belongs in a bounded OS-local Library cache, separate from updater
  cache, install folders, and editable projects. Start with one transfer at a time,
  discard partials on failure/cancel, and verify hash/size before import. Keep at most one
  verified payload plus one bounded partial; delete only recognized owned files.
- Use fixed HTTPS service origin, bounded catalog/response parsing, explicit connect/
  read/total timeouts, declared size limits, and streaming SHA-256. Recheck retained bytes
  before import. No installed helper subprocess, administrator rights, app restart,
  package execution, or downloaded scripts are involved.
- Update the architecture map, agent index, GUI workflow, nearest package guides, and
  verification routing when implementation adds these owners. Put detailed contracts in
  one `docs/EXPERIMENT_LIBRARY.md` and link to it. Do not add hypothetical current behavior
  to `ARCHITECTURE.md` during planning.

## Delivery Sequence And Verification Gates

### Phase 1: Deliver whole-project support

1. **Project contracts and clean publishing.** Finalize experiment catalog/enrollment
   contracts, secure credential storage, and complete-project publishing preparation.
   Use representative whole-project fixtures, including projects with tasks/modifiers.
   Gate: source projects remain unchanged; published bundles contain the intended
   experiment and no participant fields, output, credentials, or unrelated media.
2. **Private repository and service.** Create the proposed repo and isolated service when
   implementation is authorized. Add publishing and invitation/revocation scripts with
   dry-run modes. Gate: a device credential can list/download a published whole project;
   invalid/reused/revoked credentials fail, and GitHub credentials remain server-side.
3. **Desktop project library.** Connect enrollment, protected credentials, experiment-only
   browsing, verified transfer, cancellation, and existing whole-project import/review.
   Gate: a clean installed client can set up a complete experiment without GitHub or Git,
   preserving collision-safe new folders and the ordinary Setup/production preflight.
4. **Release and accept Phase 1.** Complete the project-only regression and two-machine
   checks below. Record results and outstanding platform limits. Phase 1 is a usable
   delivery even if Phase 2 never starts; condition work cannot hold up this release.

### Phase 2: Add individual conditions and manual setup

Start after Phase 1 acceptance and selection of Phase 2 for implementation.

1. **Condition contracts and local portability.** Finalize dependency closure, editable
   setup fields, shared-setting compatibility, ID remapping, and merge/recovery states.
   Add selected-condition export and local verified import with image/word, native AB,
   counting-baseline, and image-memory fixtures. Gate: source defaults survive unchanged
   when accepted, deliberate edits are recorded, and rejected/canceled imports change
   nothing in the target; injected commit failures recover correctly.
2. **Extend publishing and catalog.** Publish self-contained condition items through the
   existing service. Gate: the same enrollment works and Phase 1 clients still browse
   and install experiments correctly after condition entries appear.
3. **Condition browsing and setup.** Add the Conditions view, Add from Library, and the
   editable setup/review step. Gate: the user can select a desired valid trigger code,
   name, and supported condition settings; invalid choices and shared-setting conflicts
   block Add Condition, while Cancel preserves the target and original draft state.
4. **Release and accept Phase 2.** Build an experiment from multiple library conditions,
   add conditions to an existing experiment, and test repeated copies, drafts, recovery,
   and shutdown. Gate: save/reopen/compile succeeds after cache deletion, the chosen
   settings persist, and unrelated conditions/global settings/history remain unchanged.

### Phase 1 regression coverage

- Tampered hash/size, truncated archive, unknown schemas, ZIP traversal, absolute and
  drive paths, duplicate/case-colliding members, symlinks/reparse points, compression
  limits, long Windows paths, disk-full, read-only destination, cancellation, and retry.
- Whole projects retain image/word content, declared variants, AB settings, task/modifier
  media, and experiment settings. Source projects stay unchanged by clean publishing;
  project import creates a new folder and preserves every existing experiment.
- Enrollment retry after lost response, code expiry/reuse, device revocation, credential
  store failure, disconnect, rate limits, GitHub errors, invalid redirects, stale catalog,
  withdrawn/replaced assets, network loss, oversized transfers, and bounded cache cleanup.
- GUI states, realistic long content, keyboard use, root-picker/save cancellation,
  target switching during download, close/Escape/app quit in every worker phase, and
  completion after cancel arrives too late. No worker may touch a widget.

### Phase 2 additional regression coverage

- Selected-condition closure across image/word content, all declared variants, AB settings,
  modifier media/baselines, inherited presentation, shared sets, and typed link remapping.
- Editable desired trigger codes, names, instructions, and supported presentation/timing
  fields: defaults, valid changes, collisions/reserved codes, cancel, and persistence.
  Test category/protocol/fixation/repeat conflicts and unfinished destination projects.
- Existing conditions/assets/history/global settings stay unchanged by import. Compare
  compiled semantics at fixed seeds/rates against the reviewed draft, allowing deliberate
  identity, session-context, and user-selected setting/trigger differences.
- Multi-file commit/recovery, changed destination snapshots, repeated copies, manual
  Setup handoff and revalidation, and Phase 1 client compatibility with the extended service.

Register new GUI modules in `tests/qt_test_files.txt`. Follow the project-path-audit,
PySide6-cleanup, and pytest-qt-smoke skills when implementing their scopes. Use project-io,
GUI, and a narrowly added Library verification route for Phase 1; add core/compiler
coverage for Phase 2's condition changes. Run repo precommit for shared changes in either
phase. Test service code in its owning repository. Run harness
`-CheckConfig` after routing changes. Qt execution remains opt-in in an approved visible
environment; do not use offscreen Qt.

Phase 1 manual release acceptance uses two machine/user profiles with different Studio
roots: enroll, install a whole experiment, review/edit local settings through Setup,
disconnect the network, reopen/compile, and test revocation on a fresh request. Test the
installed build, supported display scaling, and a representative large bundle. Phase 2
repeats that baseline and adds multiple conditions with user-chosen codes/settings,
conflict correction, cancellation, and preservation of the receiving experiment.
Compile validation does not establish physical timing or EEG-trigger delivery;
ordinary production preflight remains mandatory. Report unperformed checks explicitly.

## Open Operational Choices

- Resolved for the test deployment: private `zcm58/FPVS-Studio-Library`, service
  `fpvs-studio-library.fpvs-studio-zcm58.workers.dev`, and two synthetic demo projects.
  GitHub App access is restricted to Contents read on that repository; deployment
  credentials and the App key remain outside source and client builds.
- Representative archive sizes and expected simultaneous readers; these determine whether
  GitHub's per-asset limit and the chosen Cloudflare plan suit the actual experiments.
- Invitation lifetime, quotas, admin credential rotation, and service backup/recovery owner.
- Linux native keyring and supported installed-environment acceptance (packaging
  explicitly includes the Secret Service backend and its required metadata).

Resolve remaining operational choices before wider lab rollout and packaged acceptance.
No automatic content updates, arbitrary repository
selector, public marketplace, Git LFS client, upload GUI, or cross-project asset sharing
is included in the first delivery.

## Planning Verification And Progress

- [x] Inspect current bundles, configs, templates, conditions/modifiers, updater trust
  boundaries, GUI entry points, app-owned jobs, and active plans.
- [x] Record no-GitHub-account access and one-time machine invitation decisions.
- [x] Revise delivery order at the user's request: whole projects in Phase 1, individual
  conditions with editable trigger/settings setup in Phase 2. Phase 1 has no condition
  implementation dependency.
- [x] Baseline docs focused: passed, including 9 harness-doc tests.
- [x] Baseline project-io focused: default long temporary paths produced 8 failures
  (`WinError 206` and related staging/cleanup errors), with 138 passing tests. Re-running
  with `PYTEST_ADDOPTS=--basetemp=build/plib16` passed all 146 tests in 18.10 seconds.
  This establishes the short-path baseline, not a fix for long-path import behavior.
- [x] Final docs focused passed (9 harness-doc tests); diff and plan links reviewed.
- [x] Phase 1 source implementation: experiment-only Library in Welcome/File/Settings,
  OS-protected device credentials, verified bounded download cache, asynchronous manifest
  review, existing new-project setup, cooperative cancellation, and clean publishing.
- [x] Cleanup: archived six detached/unused worktrees with verified history bundles and
  their complete working files under `build/worktree-recovery-20260917`; only the main
  checkout remains registered. Existing stash retained. Created `codex/experiment-library`.
- [x] Private GitHub repository, read-only App, Cloudflare Worker/D1, encrypted service
  secrets, and the two synthetic Release assets deployed. The failed browser-download
  key was revoked; only the supplied active App key remains.
- [x] Live service acceptance on September 17, 2026: two separate native Windows
  credential targets enrolled, reloaded credentials, each listed and downloaded both
  bundles, imported independent projects, disconnected/revoked, and reopened/compiled
  the local projects without further network requests. Invalid code, absent/invalid
  credentials and revoked credentials were rejected. Test credentials were removed.
  Local evidence: `build/lsm-2110eb/acceptance.json` (ignored verification artifact).
- [x] Local checks: valid 13-scope harness; focused docs/Library/GUI/packaging routes;
  changed-file Ruff/compilation, full source mypy, GC and docs audits. Safe unit suite:
  1,795 passed, 8 environment skips, and one sandbox-denied Windows named-pipe test;
  the named-pipe test passed on its isolated unsandboxed rerun (1,796 passing total).
  Service: 15 Node tests, 12 publisher tests, and Wrangler dry-build passed.
- [ ] Visible Qt/manual GUI acceptance: 28 Library cases registered, execution unrun.
- [ ] New installer, second physical machine, Linux native keyring, display scaling,
  representative large archive, and physical recording acceptance remain unrun.
- [ ] Phase 2 individual-condition implementation remains deferred.

The plan follows the repository's compact-map and explicit-owner approach described in
[harness engineering](https://openai.com/index/harness-engineering/): keep boundaries,
decisions, and measurable verification close to the implementation rather than expanding
always-read instructions with a second copy of this design.
