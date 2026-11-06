# Support reporting

This package owns GUI-neutral report contracts, local diagnostics/drafts, and the
report-service HTTP client. It must not import Qt, PsychoPy, or project models.
`error_explanations.py` owns plain-language popup and inline failure explanations.
State the problem, a supported possible cause and a short recovery step. Preserve
useful field instructions; keep code syntax in caller-owned diagnostics. Match
device/local failures before generic network/file rules and never invent an owner
or root cause. Keep shared explanation coverage in `tests/unit/test_error_explanations.py`.
Only app-owned support files may be collected or purged; never scan project output.
Network access requires an explicitly configured HTTPS reporting endpoint and an
explicit Submit/Check status action. Never ship service credentials. Preserve report
identity and receipt capability after ambiguous delivery; do not automatically resend.
The user-authorized automatic-crash feature is a separate exception: the reporting
preference defaults on with a persistent opt-out and permits background uploads of
structured sanitized source locations after installation registration. Preserve
preference generation, local opt-out before HTTP, bounded
outbox/retries, and idempotent report identity. Never upload raw logs or exception
messages automatically. Manual reporting retains its existing explicit actions.
See `docs/BUG_REPORTING.md` for the client/server contract and activation instructions.
Verify with the repo focused/precommit routes and `tests/unit/test_support_*.py`.
