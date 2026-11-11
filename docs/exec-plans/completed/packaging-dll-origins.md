# Packaging DLL origin checks

Status: Completed

The first Studio 2.8.1 build inherited Codex and Meta Horizon directories
through the host PATH. The published rebuild used a restricted process PATH.
Make that restriction the default for Windows Studio and updater bundling.

Audit the final PyInstaller collection and embedded updater tables. Reject
native sources outside the selected Python environment and its base
installation. Require the audit before installer compilation and record
its input hashes and installer asset hashes after a successful build.
The pre-upload command verifies both origins and exact assets by build label.

Verify PATH restoration, valid and foreign native sources, missing evidence,
and changed assets with focused packaging tests. Check the existing clean
and unfiltered 2.8.1 build tables as real examples.

## Verification

- The packaging scope passed 212 tests, including PATH restoration after
  success and failure, canonical native paths, and receipt validation.
- The audit accepted the clean 2.8.1 tables and rejected the first build's
  52 foreign Studio entries and 45 foreign updater entries.
- An isolated headless build through `build_release.ps1` audited 491
  Studio and 69 updater native files, generated the installer receipt,
  restored the caller's PATH, and passed the pre-upload command.
- A pre-upload rehearsal with copied release assets rejected a missing
  receipt, a changed checksum file, and the foreign Studio origin table.
- Repository precommit passed 5,806 tests and recorded two Windows
  access-denied errors while moving bundle-import staging directories.
  Both affected tests passed on focused retry.
