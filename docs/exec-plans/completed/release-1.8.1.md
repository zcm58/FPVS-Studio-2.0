# COM3 trigger fix release 1.8.1

Status: Completed

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

The final source review additionally found that direct engine callers could pass an
explicit null backend without test/pilot options, and ordinary FPVS preflight accepted
an empty trigger schedule. Both entry points now reject those states. Backend hardware
capability is explicit and preserved by logging wrappers; undeclared adapters default
to log-only. The initial candidate is superseded before publication and rebuilt.

Git history locates saved project flag selection and the null runtime default in
`2f4fd77` (v0.9.5). Library commit `bfbcd46` cleared only the serial port, leaving
enabled/backend flags unchanged; that separate blank-port problem was changed to COM3
in `42a3216`. The affected machine's project/settings were not available, so the exact
source of its disabled flag is not proven by the screenshot alone.

The user explicitly requested no tests and immediate publication. Automated tests,
packaged Studio GUI smoke, installed upgrade, physical display and BioSemi trigger
checks are deferred. Build-time metadata checks and artifact/hash verification
remain enabled; they do not establish physical trigger delivery.

## Published result

- `codex/experiment-library` was fast-forwarded into master. Final release source and
  annotated tag `v1.8.1` identify `abca7afa483c5f98a5584c957df6854260e12879`.
- [Release v1.8.1](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v1.8.1)
  (ID 391099788) is the latest stable release. Its body exactly matches the requested
  sentence. Public GitHub metadata verifies all six asset sizes and digests.
- Final outputs are in `dist/release-1.8.1-final/`; build metadata is in
  `build/release-1.8.1-final/`, with retained evidence and release helpers in
  `build/release-1.8.1/`. The initial `dist/release-1.8.1/` candidate was superseded
  before publication and is not the released binary.
- The extracted full installer contains 7,985 owned files. The only patch, from
  1.8.0, replaces/adds 18 files, removes eight obsolete files, and retains 7,967;
  reconstruction matches every full-installer target hash.
- All 59 changed packaged application modules match compiled committed source.
  All 493 native-library input entries match the authenticated published 1.8.0
  baseline. No dependency upgrades were introduced.
- Source syntax compilation and the build's updater metadata diagnostic passed.
  The anonymously downloaded live update manifest has the expected SHA-256 and
  advertises exactly the 1.8.0 baseline. Tests, GUI smoke, installed updater selection,
  installed upgrade, and physical BioSemi/ActiView verification remain unrun.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-1.8.1.exe` | 300899031 | `02ad389e5726e047ff1e619795591f1bf3bdfde3d82d78c89f2343ff3de411be` |
| `FPVS-Studio-Patch-1.8.0-to-1.8.1.exe` | 72274282 | `65aca110899e0a92d8a5cf8050ae1904ed7138e7e30144a781d294fe84efbd0d` |
| `FPVS-Studio-Update-1.8.1.json` | 435 | `12144ee3c50cc71656e85c93f68fc768e5d6ff760ee1a4b481a637199a51d94e` |

Each artifact also has a published `.sha256` companion file. No other patch
baseline was built or advertised for this release.
