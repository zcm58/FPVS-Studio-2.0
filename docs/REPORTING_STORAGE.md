# Reporting storage measurements

Measured 2026-10-08 with synthetic reports and the sibling OpenFPVS migration
schema, including UUID/digest/receipt metadata and all report indexes. The current
summary-only schema 1.0 uses compact JSON and stores each report once. Retries reuse
its exact bytes and UUID. Local captures and archives are never uploaded.
See [Data sharing](DATA_SHARING.md) for the allowlist.

## Reproduce

```powershell
./.venv3.10/Scripts/python.exe scripts/measure_reporting_storage.py --backend ../OpenFPVS
```

The script uses temporary SQLite files and makes no network requests. Sizes are
incremental physical SQLite growth above the migrated empty database, including
page allocation and indexes. They estimate D1 storage, not production D1 metering.
Project/lab/account/device tables and quota counters add shared overhead.

| Synthetic session | Wire bytes | Stored bytes/session at 1,500 | Growth at 100 | Growth at 500 | Growth at 1,500 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 occurrence | 556 | 1,092 | 106,496 | 544,768 | 1,638,400 |
| 12 occurrences, 6 repeated conditions | 3,375 | 4,377 | 434,176 | 2,183,168 | 6,565,888 |
| 120 occurrences, 6 repeated conditions | 31,152 | 33,049 | 3,301,376 | 16,519,168 | 49,573,888 |

The 12-occurrence example uses about 6.3 MiB for 1,500 sessions, including indexes.
Size varies with identifiers, counts, timestamps and occurrence count. No
compression, precision reduction or contract change is justified by these results.
The larger example's 500/1,500 rows are physical projections beyond its project
admission budget, not accepted production capacity.

## First limiting budgets

The deployed schema has project quota columns defaulting to 2,000 reports,
8,388,608 payload bytes and 100,000 occurrences. These include all machines enrolled
in that OpenFPVS project. At the fixture sizes, the first limit is 2,000 reports
for the 1/12-occurrence examples, or 269 reports for 120 occurrences (8 MiB payload
limit). Local archive cleanup changes none of these budgets.

Backend source also caps each lab at 20,000 reports / 64 MiB payloads / 1,000,000
occurrences, and the service at 50,000 reports / 128 MiB payloads. Intake has daily
limits of 240 new reports per device/project and 1,000 per lab. Other projects
consume shared budgets. These can precede Cloudflare storage limits.

Cloudflare publishes [D1 Free limits](https://developers.cloudflare.com/d1/platform/limits/)
of 500 MB per database and 5 GB total, plus [daily pricing allowances](https://developers.cloudflare.com/d1/platform/pricing/)
of 5 million rows read and 100,000 rows written. Tables and indexes consume storage;
indexed writes count toward rows written. These are reference limits, not a
confirmation of this account's billing tier.

## Read-only production snapshot

`wrangler d1 info fpvs-studio-library --json` reported 376,832 bytes (368 KiB),
29 tables, and last-24-hour usage of 1,217 rows read / 87 rows written (65 read
queries / 33 write queries). Aggregate-only SELECTs confirmed zero results
projects, reports, payload bytes and occurrences, writing zero rows. A read-only
schema query confirmed the deployed project defaults: 2,000 / 8,388,608 / 100,000.
`wrangler d1 list --json` reported three visible databases totaling 581,632 bytes
(568 KiB). There are no live project-specific quotas to inspect yet. Billing tier
was not exposed by these checks; remaining included capacity is conditional on that
tier, not an established Free entitlement. No live reports, credentials, quotas,
schema or paid resources changed.

## Read/write work

An accepted report adds one report row plus its three indexes. Admission also
updates existing request/intake quota buckets; these bounded counters do not copy
the report. An identical retry performs authenticated receipt lookup and request-rate
bookkeeping, without a new report or intake totals. Exact billed row counts depend
on D1's query plan and must be read from response `meta` in synthetic service
qualification; SQLite byte measurements cannot establish those counts.

Admission checks project/lab/service history against budgets. Comparison additionally
scans eligible occurrence history. Startup now submits pending reports without
fetching comparisons for every unopened project, and skips HTTP for projects without
deliverable captures. This removes avoidable requests and aggregate-history reads.
Admission scans remain an existing backend cost; replacing them with maintained
counters would add consistency obligations outside this lifecycle change.
