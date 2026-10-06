# Private fixation Results Worker

This directory is a standalone Cloudflare Worker/D1 source artifact. It is tracked with
the desktop feature for review but is deployed independently. Nothing is provisioned or
published; the desktop results endpoint remains unconfigured until an approved deployment.
The existing Library and Feedback services and their credentials are separate.
The planned OpenFPVS bridge would reuse a Library lab code only with an administrator's
explicit experiment/version/protocol contribution grant and separate desktop opt-in.
That bridge, its administrator Contributions section and any dashboard are not implemented.
The current Library `/v1` namespace returns 426 and cannot host these routes unchanged;
a distinct Results namespace, scoped grant mapping, separate Results device credentials
and immediate grant-revocation checks are required. See the canonical
[integration target](../../docs/DATA_SHARING.md#planned-openfpvs-authorization-bridge).

## Local verification

Node 24 provides all test dependencies, including `node:sqlite`:

```powershell
npm test
npm run check
```

Tests use synthetic reports in an in-memory SQLite database. They never contact an account,
experiment server, GitHub or email service. Cloudflare runtime/staging and account capacity
remain unverified until explicit deployment acceptance. A maintainer may use an installed
Wrangler to perform an offline dry build separately; no runtime package is needed here.

## Registration and enrollment

Before authorizing a deployment, decide private-data retention, owner access, backup,
deletion and applicable research approval. Review current account/request/storage capacity;
these source files do not establish a free or paid account allowance. Use a new D1 database
and hostname. Replace `wrangler.toml`'s invalid origin/zero database placeholders, review the
migration and bind this database as `DB`. Keep deployment/provisioning explicit.

Register each immutable `(experiment_id, experiment_version, protocol_sha256)` using a
reviewed protocol fingerprint from Studio and a high-entropy lab-issued invitation code.
Only the SHA-256 code hash belongs in SQL. `scripts/register.mjs` writes SQL to stdout; it
does not execute SQL, fetch credentials or contact Cloudflare:

```powershell
node scripts/register.mjs --experiment-id demo --experiment-version 1.0.0 --protocol-sha256 <64-lowercase-hex> --title "Fixation study" --invitation-code-sha256 <64-lowercase-hex>
```

Review and apply both emitted statements together through the separately authorized D1
execution/batch workflow. Do not add explicit `BEGIN`/`COMMIT`; D1 owns its transaction
boundary. See [D1 import guidance](https://developers.cloudflare.com/d1/best-practices/import-export-data/).
Existing identities cannot be overwritten by this script. A changed protocol needs a new
registered version and scoped invitation. Store issued codes outside the checkout. Rotate
or disable invitations with `invitations.revoked_at`; this stops new enrollments. Revoke
existing access with `devices.revoked_at` or the version's `revoked_at`. Invitation hashes,
token hashes and private data must also have restricted maintainer access.

For a native Library-linked project, register its exact Library item ID and installed
version with the reviewed protocol hash. Studio checks that receipt before enrollment,
capture, sending and comparison; unknown installed versions require review. Standalone
authored projects retain their separately registered scope. The current
`invitations.code_hash` primary key allows one scope per invitation hash, so it is not a
multi-experiment Library lab-code grant map. Library credentials or download grants do
not authorize this independent Results API.

Enrollment uses a client-generated 256-bit token (64 lowercase hex characters), retained
in the operating system credential store. The server stores its hash. A retry with the same
token/code returns the same profile; a revoked token cannot enroll again. The token is scoped
to exactly one experiment/version/protocol. Enrollment never turns desktop sharing on.
The device insert atomically rechecks invitation expiry and invitation/version revocation,
so an authorization change after the initial lookup cannot create a new enrollment.

## Native v1 API

All requests require the exact configured HTTPS origin. Redirect/proxy routes, browser
`Origin` requests, query strings, unknown fields and unconfigured bindings fail closed.
All JSON responses are `no-store`; errors expose only `schema_version` and a stable `error`
code, never SQL messages, tokens, invitation codes, IP addresses or private payloads.

| Route | JSON body / access |
| --- | --- |
| `POST /v1/enroll` | `{schema_version:"1.0", code, device_token, protocol_sha256}` with optional paired `experiment_id`/`experiment_version` for linked Library scope; valid Results invitation and Cloudflare client IP required |
| `POST /v1/experiments/{id}/reports` | Exact report envelope below; scoped Bearer credential |
| `GET /v1/experiments/{id}/reports/{uuid}/receipt` | Only this device's receipt in its registered scope |
| `POST /v1/experiments/{id}/comparison` | `{schema_version:"1.0"}`; scoped Bearer credential, aggregate only |
| `DELETE /v1/device` | Revoke authenticated enrollment; does not delete already received research records |

Enrollment returns `{schema_version, experiment_id, experiment_version, protocol_sha256,
title, device_id}`. Enrollment attempts are limited to ten per hashed IP slot per ten minutes
and 1,000 globally per ten minutes; authenticated requests are limited to 60 per device per
minute. New reports are limited to 240 per device per UTC day. Existing identical report
retries do not consume the new-report quota. Expired quota buckets are deleted; IP slots are
bounded and collisions conservatively share the limit. No raw IP or device name is stored.

Reports contain exactly `schema_version:"1.0"`, `report_id` (canonical UUID), `experiment_id`,
`experiment_version`, `protocol_sha256`, `completed_at` (UTC), `studio_version`, and
`occurrences` (1–4,096). A complete request is at most 128 KiB, read incrementally even when
`Content-Length` is absent or misleading. Each occurrence has exactly:

```json
{
  "condition_id": "faces",
  "occurrence_index": 1,
  "total_targets": 10,
  "hit_count": 8,
  "miss_count": 2,
  "false_alarm_count": 1,
  "accuracy_percent": 80.0,
  "mean_rt_ms": 350.0,
  "rt_count": 8,
  "scoring_source": "timestamps",
  "refresh_hz": 60.0,
  "response_window_ms": 1000.0
}
```

Indices are unique and start at 1. Safe experiment/condition IDs have at most 80 ASCII
letters, digits, underscores or hyphens and start with a letter or digit. Versions have at
most 64 characters and also allow periods and plus signs. At most 512 distinct conditions
are accepted per report. Counts are integers from 0 to 1,000,000, hits plus
misses equal targets, and `rt_count` cannot exceed hits. Accuracy is null for zero targets,
otherwise `100*hits/targets` within `1e-6`. Mean RT is null exactly when `rt_count` is zero;
available RT and response windows range 0–600,000 ms, refresh rates 1–1,000 Hz. Unknown
fields, nonfinite numbers and malformed timestamps fail validation. No participant IDs,
demographics, stimulus paths, raw answers, EEG or free text enter this API.
Duplicate JSON object keys, including escaped-equivalent keys, are rejected before
validation and storage so D1 cannot aggregate a different value from the validated one.

Immutable request bytes and their SHA-256 digest are saved before the receipt is returned.
The insert atomically checks that the device and registered version remain unrevoked;
revoking either after authentication but before the insert prevents the new commit.
The receipt is `{schema_version:"1.0", report_id, experiment_id, experiment_version,
protocol_sha256, sha256, received_at}`. Resending identical bytes returns this receipt;
different bytes or another device reusing the same experiment/report ID returns HTTP 409.
Keep the same report UUID after a lost response. The service cannot establish actual run
completion independently; Studio's post-commit capture gate owns production eligibility.

## Cohort comparison and privacy

Comparison always excludes every report owned by the requesting device. The client cannot
choose report exclusions or request individual rows. Cohorts are limited to the exact
experiment/version/protocol. Repeated occurrences are summed within each report, then
distinct report sessions and contributing devices are counted per condition. Zero-target
occurrences are omitted. Valid reports with mixed scoring metadata are preserved, while
their incompatible condition aggregates remain suppressed.
The implementation uses D1's documented [JSON query functions](https://developers.cloudflare.com/d1/sql-api/query-json/)
to aggregate stored occurrence arrays in one query, avoiding one database operation per occurrence.

The response has `schema_version:"1.0"`, `experiment_id`, `experiment_version`,
`protocol_sha256`, `minimum_sessions:10`, `minimum_devices:3`, `conditions` and UTC
`generated_at`. Each condition contains `condition_id`, `session_count`, `device_count`,
`eligible`, `total_targets`, `hit_count`, `accuracy_percent`, `mean_rt_ms`, and `rt_count`.
It also carries `scoring_source` and `response_window_ms` for a compatible cohort so Studio
can check the latest local condition's actual scoring provenance before showing comparison.
All five metrics and both provenance fields are null unless ten report sessions and three devices contribute
and all contributing scoring sources/response windows agree. Counts are visible even when
metrics are suppressed. Accuracy uses pooled counts; RT uses observation weighting,
`sum(mean_rt_ms*rt_count)/sum(rt_count)`. No-hit cohorts have null mean RT.

Reports are sessions, not unique participants. Three credentials/devices are an access
diversity guard, not proof of three people. Private timestamps and credential linkage mean
these summaries are not anonymous data. Minimum cohort rules reduce small-group exposure;
the native response supports descriptive comparison only. Raw datasets, owner exports,
public publication, longitudinal joins and task-specific protocols need separate workflows.
