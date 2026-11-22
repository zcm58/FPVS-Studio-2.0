# Studio 3.1.5 release

Status: Active

## Scope

Ship the November 22 efficiency work as the next Windows x64 patch release.
The next patch version is 3.1.5. Build the full installer from the exact tagged
source and prepare direct patches from published stable versions 3.1.0 through
3.1.4 using authenticated installed ownership inventories. Offer each patch
only when its compiled download is smaller than the full installer.

## Verification

- Run Windows and macOS source verification and bidirectional project transfer
  checks for the exact release commit.
- Audit both frozen packages' DLL origins and compare the full installer with
  a reference that adds back only the excluded Windows Builder examples.
- Authenticate the draft tag, inventory and assets and run the standard hosted
  installer verification. Check fresh install, full upgrade, each direct patch,
  preservation of projects and settings, and uninstall.
- Publish the verified draft separately from acceptance. Check the immutable
  public release and each asset attestation, download hashes, and production
  updater selection for direct patches, full fallback, repair, and current users.

Release acceptance uses disposable hosted Windows. Synthetic playback and
physical presentation or timing evidence are recorded separately.
