# Experiment Library

This package owns GUI-neutral catalog contracts, HTTPS service access, OS-protected
device credentials, and a bounded OS-local download cache. It never imports Qt,
runtime, engines, or updater/installer code. Core project bundles own archive
validation and extraction; this package only transfers and verifies bytes.

- No GitHub credentials, enrollment codes, or downloaded executable code live here.
- Persist a random device token in the secure OS store before enrollment. Preserve
  pending tokens after network errors so retry is idempotent.
- Native access uses `/v2` with JSON schema `1.0`. Clear previous-protocol secure
  credentials under the cache lock before startup/enrollment; reconnect with a fresh
  token and the existing lab code. Never reuse old or revoked machine access.
- Native Studio connects directly to `https://openfpvs.com`. Canonicalize only the
  two previous managed origins through core's `library_origin.py` policy; preserve
  custom service origins. New-origin enrollment uses its own secure store/cache;
  never copy old credentials or rewrite installed receipts. Receipt comparisons use
  the same policy without sending requests to the saved origin.
- Windows uses Credential Manager; Linux requires Secret Service. Fail closed when
  secure storage is unavailable; never write secrets to project files or the cache.
- Keep HTTP requests on the configured HTTPS service origin, reject redirects, bound
  responses/transfers, and honor cooperative cancellation between bounded reads.
- Serialize cache/credential mutations with the interprocess cache lock. Reject
  symlinks/reparse points; remove only recognized cache files. At most one verified
  payload and one bounded partial are retained; rehash cached bytes before reuse.
- Imported projects are independent copies and work offline. Network access never
  replaces an existing project or edits settings.
- `provenance.py` verifies signed bundle evidence with the locally pinned managed
  service key before cache creation/reuse. Response keys cannot establish trust;
  see `docs/LIBRARY_ARTIFACT_PROVENANCE.md` for the bounded proof contract.
- `submissions.py` transfers an explicitly confirmed whole-project bundle through
  `/submissions/v1`, using a separate OS-protected upload identity without enrollment
  or Library privileges. Retain the enrolled `/v2/submissions` condition API for older
  clients. Bind retries to the UUID/digest; preparation uses
  core's clean exporter through the existing prepared-file owner. No GitHub write
  credential enters the desktop client. Approval covers exact bytes only.
- `project_updates.py` discovers newer versions from an explicit local origin receipt.
  Compare semantic versions by item identity even if the installed release disappeared;
  never infer origins from names or follow a receipt to a different service endpoint.
  Checking does not install. GUI-owned review imports a separate project explicitly.
- `installations.py` checks the configured Studio Root before and after payload transfer.
  Same/newer installed versions cannot download again, including through project updates.
  Older or unlinked review candidates require the explicit project-version workflow.

See `docs/EXPERIMENT_LIBRARY.md` and the active library execution plan. Run the
`library` focused verification route and repo precommit for shared changes.
