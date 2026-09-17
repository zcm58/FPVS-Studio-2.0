# COM3 trigger fix release 1.8.1

Status: Active

## Authorized scope

Merge `codex/experiment-library` into `master`, release version 1.8.1, and publish
the full Windows installer plus one direct patch from the authenticated published
1.8.0 installer. Do not build or advertise patches from any other baseline.

Release notes must be exactly:

> Fixed a critical bug that caused trigger codes to silently fail when sending via COM3 serial port

The release includes the merged Experiment Library work and trigger fixes
`ae405b3` and `7eb1878`. Ordinary recording launches require serial output;
unset/blank ports resolve to COM3. Experiment Test Mode and AB Pilot Study Mode
remain explicit hardware-free exceptions. No hardware fallback is permitted.

## Delivery

1. Commit version metadata on master and push the release source.
2. Refresh app metadata without upgrading dependencies; build in
   `build/release-1.8.1/` and `dist/release-1.8.1/` with the retained 1.8.0 baseline.
3. Check packaged inventories, patch reconstruction, and asset SHA-256/size;
   upload a draft, then publish with the exact requested release notes.
4. Record the source commit, public release, artifact identities and unrun checks.

## Verification boundary

The user explicitly requested no tests and immediate publication. Automated tests,
packaged Studio GUI smoke, installed upgrade, physical display and BioSemi trigger
checks are deferred. Build-time metadata checks and artifact/hash verification
remain enabled; they do not establish physical trigger delivery.
