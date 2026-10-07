# Results service architecture

This describes the undeployed standalone reference. Current OpenFPVS project
authorization, intake and private dashboards belong in sibling `../OpenFPVS`,
documented by its `PROJECT_REPORTING.md`. Shared synthetic wire fixtures remain here.

Studio captures opted-in successful production fixation summaries locally, then sends
immutable JSON bytes over HTTPS. This standalone Worker authenticates a credential scoped
to one registered experiment/version/protocol and writes the bytes and digest to its own
D1 database before returning a receipt. `(experiment_id, report_id)` is unique.

- `src/http.js`: bounded body reads, safe errors and response headers.
- `src/contracts.js`: strict v1 envelopes and fixation count/RT consistency.
- `src/auth.js`: invitation/token hashes, enrollment scope, revocation and fixed quotas.
- `src/reports.js`: report insertion, device-owned receipts and compatible aggregates.
- `src/index.js`: fixed HTTPS origin and route/method boundary; no outbound network calls.
- `migrations/`: independent D1 schema, including registered immutable protocol identities.
- `scripts/register.mjs`: local SQL generation for reviewed registration/invitations.
- `tests/`: synthetic local SQLite tests of transactions, scopes and privacy suppression.
- `fixtures/`: synthetic v1 envelopes shared with desktop model validation tests.

Device credentials permit ingestion, their own receipts, revocation and cohort comparison.
Comparison omits the authenticated device's reports, returns per-condition totals only
after ten distinct report sessions and three devices contribute, and suppresses metrics
when scoring sources/response windows differ. Repeated occurrences are summed within a
report before counting sessions. Zero-target occurrences do not contribute. Devices and
sessions are not unique participants; this schema deliberately has no participant ID.

Maintainer access to private D1 data is outside the native API and must be governed by
the deployment's approved retention, access, backup and deletion policy. Neither a public
dataset nor a remote deployment is created by this source artifact. See `README.md`.
