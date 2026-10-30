# Local signing and current-project updates

Status: Completed

Date: 2026-10-30

## Delivered workflow

The user requests signing on this Windows PC and an **Update current project**
primary action instead of manually replacing a separately downloaded project.
Signing is installed and verified locally; the Studio interaction is implemented
and verified without Qt in source, awaiting a future application build.
The Website's canonical signer transferred the existing key through an authenticated
encrypted response and re-protected it for this PC's Windows account. No service or
client trust rotation was needed. Private keys never enter Git, project files, logs
or plaintext transfer files. Future validation, signing and registration run here.
The self-contained maintainer command lives under
`%LOCALAPPDATA%/OpenFPVS/signing/tools/Sign-Experiment.ps1`; a fresh full validation,
ClamAV scan and signature of the retained Dyslexia bundle passed both canonical
verification and Studio's unchanged public pin. The response was imported and the
one-time transport private state consumed; the subsequent CheckOnly integrity check
also passes. Website source is published on `main` at `bf84356`; no service deployment
was needed. The user authorized committing and pushing the Studio changes next.

The project-version dialog retains its 760x680 minimum / 820x720 default size.
Its primary action updates the linked current project; **Download separately**
remains secondary and **Keep current version** closes without changes. Unknown
installed versions require explicit linking/version review before in-place update.
The review explains that authored settings and stimuli change, while participant
data and local recording/display configuration stay with the current project.

Core owns a staged, validated transaction and recoverable backup. Preserve the
current folder and local project identity, private reporting/recovery data, runs,
logs and unrelated user files. Validate service/item/version identity, recheck
the source snapshot before commit, reject links/collisions, and roll back failed
Windows commits. Cancellation before commit leaves the old project usable;
successful commits remain successful if cancellation arrives late. GUI workers
perform transfer and filesystem work; unsaved-edit and presentation guards run
before the update, and the document reloads only after a successful commit.
Results outbox/capture readiness and runtime interruption/lifetime readiness are
checked before transfer and again through core's neutral precommit callback.
Existing reports and reviewed history stay untouched; old original-plan reruns
require restoring the prior authored backup. Close other Studio instances using
the project; checkpoint probes do not create a project-wide runtime lease.

Verification: Library, project-I/O, GUI, Results and runtime focused routes,
meaningful transaction and controller regressions, registered dialog/controller
Qt coverage, docs checks, then repo precommit. Qt execution requires an approved safe visible session and
will not run offscreen. Manual smoke covers both dialog sizes/themes, an edited
linked project with participant data, cancel/failure/rollback, and reopening the
same project at the new version with a retained backup.

Focused acceptance passes Library (488, three Windows symlink skips), project-I/O
(430, two skips), GUI without Qt (120), Results (329), runtime (772, three skips)
and docs (10). The initial baseline's intermittent bundle-import access-denied
failures passed on retry and the complete focused reruns; the ordinary importer
was not changed. New coordinator regressions cover stale drafts, late cancellation,
queued/direct launches, failed-adoption locks, Results readiness and installed-copy
eligibility. Repository precommit passes 4,057 non-Qt tests with 12 Windows
symlink-permission skips, Ruff/compilation, mypy over 251 source modules, repository
audits and documentation hygiene. Verification configuration validates all 14 scopes.
Qt and packaged/installed GUI acceptance remain unrun; no Studio release was built
or published. An interrupted test run's temporary directory was retained after
automatic approval review blocked its cleanup; source and test results are unaffected.

The same user request sets screen width to 60.96 cm in all 32 accessible editable
Studio project files on this PC: 15 current projects and 17 archival/migration copies.
Thirty-one files changed and one already matched. Exact original project files and a verification receipt are retained
outside Git. The open project was updated and saved through Studio; the other edits
atomically changed only the screen-width field and retained all other JSON values.
All 32 reload through the canonical project serializer at 60.96 cm. Run/log records
and generated staging are outside the editable-project scope; other Windows profiles
were inaccessible. These local calibration edits do not change the application-wide
monitor default or published experiment bundles.
