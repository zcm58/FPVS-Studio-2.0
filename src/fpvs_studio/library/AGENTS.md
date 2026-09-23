# Experiment Library

This package owns GUI-neutral catalog contracts, HTTPS service access, OS-protected
device credentials, and a bounded OS-local download cache. It never imports Qt,
runtime, engines, or updater/installer code. Core project bundles own archive
validation and extraction; this package only transfers and verifies bytes.

- No GitHub credentials, enrollment codes, or downloaded executable code live here.
- Persist a random device token in the secure OS store before enrollment. Preserve
  pending tokens after network errors so retry is idempotent.
- Windows uses Credential Manager; Linux requires Secret Service. Fail closed when
  secure storage is unavailable; never write secrets to project files or the cache.
- Keep HTTP requests on the configured HTTPS service origin, reject redirects, bound
  responses/transfers, and honor cooperative cancellation between bounded reads.
- Serialize cache/credential mutations with the interprocess cache lock. Reject
  symlinks/reparse points; remove only recognized cache files. At most one verified
  payload and one bounded partial are retained; rehash cached bytes before reuse.
- Imported projects are independent copies and work offline. Network access never
  replaces an existing project or edits settings.
- `project_updates.py` discovers newer versions from an explicit local origin receipt.
  Compare semantic versions by item identity even if the installed release disappeared;
  never infer origins from names or follow a receipt to a different service endpoint.
  Checking does not install. GUI-owned review imports a separate project explicitly.

See `docs/EXPERIMENT_LIBRARY.md` and the active library execution plan. Run the
`library` focused verification route and repo precommit for shared changes.
