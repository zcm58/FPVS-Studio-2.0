# Support reporting

This package owns GUI-neutral report contracts, local diagnostics/drafts, and the
report-service HTTP client. It must not import Qt, PsychoPy, or project models.
Only app-owned support files may be collected or purged; never scan project output.
Network access requires an explicitly configured HTTPS reporting endpoint and an
explicit Submit/Check status action. Never ship service credentials. Preserve report
identity and receipt capability after ambiguous delivery; do not automatically resend.
See `docs/BUG_REPORTING.md` for the client/server contract and activation instructions.
Verify with the repo focused/precommit routes and `tests/unit/test_support_*.py`.
