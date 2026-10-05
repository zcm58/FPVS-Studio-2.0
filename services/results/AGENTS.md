# Results service

Read `ARCHITECTURE.md`, then the module implicated by the task. This is an independent
Cloudflare Worker/D1 deployment artifact; it does not import desktop packages or mutate
the Library/Feedback services. Never deploy, provision resources, query received private
reports, or retrieve credentials as part of local verification.

Run `npm test` and `npm run check` with Node 24. Tests use built-in `node:sqlite`, synthetic
reports and an in-memory D1 adapter. No package installation or network access is needed.
Keep invitation codes, device tokens, private reports, `.dev.vars`, database exports and
Cloudflare credentials out of source control and logs. Only stable error codes leave the
Worker. Registration scripts emit reviewable SQL; they do not execute it.

`src/contracts.js` owns wire validation, `auth.js` enrollment/authentication and quotas,
`reports.js` durable ingestion/receipts and aggregate comparison, and `index.js` routes.
The requesting device is always excluded from comparison. Preserve minimum report/device
thresholds and suppression of incompatible scoring sources/windows. Preserve received
valid mixed-source reports; their incompatible condition aggregates remain suppressed.
No raw-result read
route or individual-result comparison belongs in the native API.
