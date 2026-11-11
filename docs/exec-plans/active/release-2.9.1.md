# Studio 2.9.1 release

Status: Active

Publish the pulled source as a Windows maintenance release. User-facing changes
include Windows scaling and fullscreen task layout fixes, plus access to recording
settings from the Home screen's recording device.

Use the isolated release checkout and the pinned environment from 2.9.0. Build the
full installer and updater manifest. Verify packaged Studio and updater smoke checks
in the approved visible desktop, audit DLL origins, and compare GitHub draft asset
sizes and digests to local files before publishing. Verify the published tag,
release attestation and asset integrity. Record results after publication.
