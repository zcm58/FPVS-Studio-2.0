# Published Legacy Installer Inventory

`published-legacy-inventory.json` records the union of application files shipped by
the public Windows installers through FPVS Studio 1.3.0. These older installers did
not write an owned-file manifest. An installation that has passed through several
releases can retain files from any of them, not just the most recent version.

The inventory contains installed `{app}`-relative paths and the SHA-256 content hashes
actually extracted from the authenticated published installers. It is not a list of
everything found in a developer's installation, nor a reconstruction from source.
The `releases` records retain each GitHub tag, asset identity, size, and installer
SHA-256. Project bundles and Inno uninstaller bookkeeping are not ownership evidence.
The frozen inventory covers 17 published installers, 13,286 paths, and 13,658
distinct path/hash records.

Only a known path with matching known content can authorize legacy cleanup. Unknown
or modified files must survive. Current and future releases use their generated
owned-file manifests; this frozen legacy inventory is the compatibility bridge, not
a reason to download historic installers on an end user's machine.

## Reproduce Without Installing Anything

The developer-only `scripts/refresh_legacy_installer_inventory.py` utility requires
the repository's Python 3.10 environment, the GitHub CLI, and a separately verified
portable `innounp.exe`. It lists the archive before extraction, rejects unsafe or
aliased Windows paths, extracts only `{app}` files into a temporary tree, verifies
the extracted file set, and emits deterministic sorted JSON. It never runs a
published setup program. Temporary extracted trees are removed; downloaded setup
archives remain in the explicitly selected work directory for review/reuse.

The 2026-08-30 generation used the author's
[portable innounp release](https://github.com/jrathlev/InnoUnpacker-Windows-GUI/releases/tag/oi_2_2_11),
version 2.67.11:

- `innounp-2.zip` SHA-256:
  `851772538a041229102ad9964542d49dc00c74002e3091a70469c079ae368f52`
- extracted `innounp.exe` SHA-256:
  `1c8453c198dd3fe7947f3705e59d2294ddce3dfa9f96a737e94449b119f44181`

Obtain the ZIP from that release and verify it before extracting/running the portable
utility. No third-party binary is committed to this repository. Use an absolute,
dedicated work directory under ignored `build/`, not an installed-app or project-data
directory. For example, after substituting the actual absolute paths:

```powershell
.\.venv\Scripts\python.exe scripts/refresh_legacy_installer_inventory.py `
  --extractor "C:\path\to\inventory-work\extractor\innounp.exe" `
  --extractor-sha256 1c8453c198dd3fe7947f3705e59d2294ddce3dfa9f96a737e94449b119f44181 `
  --work-dir "C:\path\to\inventory-work" `
  --through-version 1.3.0 `
  --output "C:\path\to\reviewed-legacy-inventory.json"
```

Compare the generated file with the committed JSON before replacing it. An existing
output requires explicit `--replace`. The generator authenticates each installer
against its [GitHub release asset digest](https://docs.github.com/en/rest/releases/assets).
The historical tag `v0.9.9.10` intentionally retains its published installer filename
`FPVS-Studio-Setup-0.9.10.exe`; it is not silently retagged.

Archive extraction and manifest tests are not installation tests. Fresh install,
chained upgrade, interrupted/locked-file cleanup, and uninstall acceptance still
require a disposable Windows environment; see `docs/PACKAGING.md`.
