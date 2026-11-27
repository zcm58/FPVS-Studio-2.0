# Scientific output comparison on Windows

The subsequent workflow trial fixed the two equalization differences measured
below and added checksum-verified recovery from study checkpoints. Fresh PNG
compression differences remain. [Final workflow verification](../exec-plans/completed/python311-user-workflows.md)

On November 26, 2026, Python 3.11.18 reproduced the measured scientific outputs with
the reference library versions. Fresh Pillow 13 generation changed the file identity
of four stimulus derivatives used by the synthetic study, despite identical pixels.

| Environment | Python | Pillow | NumPy | Pydantic | openpyxl |
| --- | --- | --- | --- | --- | --- |
| Reference, run twice | 3.10.11 | 11.3.0 | 2.2.6 | 2.12.5 | 3.1.5 |
| Interpreter control | 3.11.18 | 11.3.0 | 2.2.6 | 2.12.5 | 3.1.5 |
| Pillow-only control | 3.11.18 | 13.0.0 | 2.2.6 | 2.12.5 | 3.1.5 |
| Candidate | 3.11.18 | 13.0.0 | 2.4.6 | 2.14.4 | 3.1.5 |

## Measured outputs

- All **24 serialized contracts** matched byte for byte across all environments. These
  cover RunSpec and SessionPlan at 60, 60.02 and 120 Hz, seeds 11 and 83, with either
  original assets or four conditions using original, grayscale, rotated and phase-scrambled
  assets. Each plan contains eight runs. The comparison includes stimulus order, frame
  schedules, fixation timing and trigger events.
- All **54 image comparisons** matched dimensions, mode and pixel bytes. The interpreter
  control matched all encoded bytes. On the candidate, nine PNGs changed on disk. Four were
  rotated study stimuli and five were 512-pixel standalone resizes. All six 256-pixel
  normalization outputs, six equalized outputs and the original source copies retained
  their bytes. Changing only Pillow reproduced all nine encoded differences, the
  four changed Library media checksums and the new Results fingerprint. The two 3.11
  controls shared the same other 29 installed package versions. The inputs included
  PNG, JPEG with and without EXIF orientation, BMP and TIFF.
- In the nine changed PNGs, decompressing their IDAT chunks produced identical filtered
  scanlines. The difference is in DEFLATE encoding. The installed Pillow wheels report
  zlib-ng 2.2.4 and 2.3.3 respectively. Upstream describes the compressor's byte-output
  compatibility limits. [zlib-ng maintainer explanation](https://github.com/zlib-ng/zlib-ng/discussions/905)
- Equalization used the same target standard deviation, 49.05184198692878. Two reported
  standard deviations differed by one binary64 spacing (about 7.1 × 10⁻¹⁵). All other
  recorded before/after statistics matched. The Pillow-only control matched every
  reference statistic. Passing identical raw grayscale pixels to NumPy alone reproduced
  both differences on 2.4.6. For alpha.png the reported value went from
  49.10137365221236 to 49.10137365221235. For gradient.png it went from
  49.2214309038054 to 49.221430903805405. Keeping NumPy 2.2.6 preserves these
  measured values, while fresh Pillow 13 output still changes the affected file hashes.
- Participant result JSON matched byte for byte. The history CSV matched in column order
  and every value except its write timestamp. All seven workbook sheets matched
  cell-for-cell, including task responses and fixation results. All 15 XLSX member
  contents matched after normalizing the creation and modification timestamps in
  document properties. Raw CSV and XLSX file hashes also varied between reference repeats.

## Project identity

The original-only Results protocol fingerprint remained `8fc8ef48…` in each run.
For a newly generated study selecting the rotated images, four of 24 selected media
checksums differed. The Results fingerprint changed from `83337598…` to `5172a378…`.
The locally prepared Library bundle recorded the same four changed media checksums.
Production Library provenance binds a reviewed bundle's exact hash and size.
[Library artifact provenance](../LIBRARY_ARTIFACT_PROVENANCE.md)

Opening a copy of the baseline study under the candidate and materializing its already
present derivatives preserved its Results fingerprint, all selected media hashes and all
Library media checksums. Setup reported zero changes. Replacing those four files and
their manifest with the freshly generated candidate outputs made Setup report four
stimulus replacements. The supported reuse path therefore preserves existing studies
with intact artifacts. The stock candidate cannot guarantee identical legacy files
when an asset is missing, a new derivative is built, or a resize is repeated. Pinning
the reference Pillow as a compatibility solution would retain upstream security
advisories. [Pillow 13 security fixes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html#security)

## Reproduce

Run these commands from the trial checkout. Set `$referenceRepo` to the original
source checkout with its 3.10 environment. The control and candidate paths below use
the layout of the trial environment. Each output directory must be new. Inputs are
generated once with the reference environment from synthetic patterns and local test
fixtures. The check needs no experiment data, hardware, Qt session or online service.
Clock values, ZIP timestamps and whole Library container hashes can vary across runs.
The script compares the selected study assets and Library media member hashes directly.

```powershell
$script = (Resolve-Path scripts/compare_scientific_environments.py).Path
$ref = Join-Path $referenceRepo '.venv3.10/Scripts/python.exe'
$control = '.tmp/trial/control-311/Scripts/python.exe'
$candidate = '.venv/Scripts/python.exe'
$pillowOnly = '.tmp/trial/pillow13-only-311/Scripts/python.exe'
$out = Join-Path ([IO.Path]::GetTempPath()) ("fpvs-science-" + [Guid]::NewGuid().ToString('N'))
& $ref $script --repo $referenceRepo prepare "$out/inputs"
& $ref $script --repo $referenceRepo measure "$out/inputs" "$out/reference"
& $ref $script --repo $referenceRepo measure "$out/inputs" "$out/repeat"
& $control $script measure "$out/inputs" "$out/control"
& $pillowOnly $script measure "$out/inputs" "$out/pillow-only"
& $candidate $script measure "$out/inputs" "$out/candidate"
foreach ($run in 'repeat', 'control', 'pillow-only', 'candidate') {
    & $candidate $script compare "$out/reference" "$out/$run"
}
& $candidate $script reuse "$out/reference" "$out/candidate" "$out/reuse"
```

To construct the separate Pillow-only environment on a fresh trial checkout, first
provision the control and candidate from the [trial report](../exec-plans/completed/python311-pillow13-trial.md).
Run the following once before the measurements. It copies the control's package
versions and changes Pillow to 13.0.0.

```powershell
$trialArea = (Resolve-Path .tmp/trial).Path
$control = Join-Path $trialArea 'control-311/Scripts/python.exe'
$destination = Join-Path $trialArea 'pillow13-only-311'
& $control -m venv $destination
$requirements = Join-Path $trialArea 'pillow13-only.txt'
(& $control -m pip freeze) -replace '(?i)^pillow==.*$', 'pillow==13.0.0' |
    Set-Content -LiteralPath $requirements -Encoding ascii
$pillowOnly = Join-Path $destination 'Scripts/python.exe'
& $pillowOnly -m pip install --only-binary=:all: -r $requirements
& $pillowOnly -m pip check
```

Each measurement keeps its exact compiled plans, generated images, workbook, local
Library bundle and `evidence.json`. The reuse check writes `reuse.json`. The experiment
covers software outputs on this Windows host. Physical display timing, EEG timing,
packaged installations and service delivery need separate acceptance.
