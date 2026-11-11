# Studio 3.0.0 release

Status: Active

Publish a stable Windows x64 release highlighting BrainVision Recorder 2 support.
The user verified the Trigger Tester and marker sending on a 2026 actiCHamp
system using Recorder 2. Include named-device detection, BioSemi reconnect
guidance, and actionable connection errors in the notes.

- Audit agent entry points against current code and verify documentation budgets.
- Build from the exact 3.0.0 source commit with the pinned 2.9.1 environment.
- Run the approved visible Trigger Tester, packaged Studio, and updater checks.
- Audit DLL origins, installer inventory, and release asset hashes. Stage the
  four Windows assets in a draft and verify their sizes and digests.
- Publish as the latest immutable release and verify the tag, attestation, and
  public downloads. Record evidence after publication.
