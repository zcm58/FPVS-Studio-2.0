# FPVS PsychoPy Migration Guide

## Source Discovery

Use a read-only inventory before writing anything:

- `Get-ChildItem -Recurse -File -Include *.psyexp,*.py,*.lnk,*.xlsx,*.xls,*.csv,*.tsv,*.txt`
- Resolve `.lnk` files on Windows:

```powershell
$shell = New-Object -ComObject WScript.Shell
Get-ChildItem -LiteralPath $source -Filter *.lnk | ForEach-Object {
  $shortcut = $shell.CreateShortcut($_.FullName)
  [pscustomobject]@{
    Name = $_.Name
    TargetPath = $shortcut.TargetPath
    WorkingDirectory = $shortcut.WorkingDirectory
    TargetExists = Test-Path -LiteralPath $shortcut.TargetPath
  }
}
```

Search `.psyexp` and generated Python for list-loading calls and trigger writes:

```powershell
rg -n "(?i)read_excel|read_csv|conditionsFile|port\.write|chr\(|trigger|\.png|\.jpg|\.jpeg|random\.choice" <paths>
```

Open list files with `pandas.read_excel` / `pandas.read_csv`, then resolve relative
stimulus references from the PsychoPy experiment's working directory.

## Project Layout

Create the project under the configured FPVS Studio Root Folder:

```text
<FPVSRoot>/<ProjectName>/
  project.json
  stimuli/
    original-images/<set_id>/
    normalized-images/<set_id>/        # active copies when normalization is needed
    generated-variants/
    original-word-lists/<set_id>/      # provenance only
    manifest.json                      # image sets only
  migration/
    source_image_mapping.csv
    skipped_source_rows.csv
    stimulus_set_summary.csv
    source_experiments.json
    source-lists/
  runs/
  cache/
  logs/
```

Do not write migrated data into the repository. A one-off script in `.codex-tmp/` is
fine; remove it after the migration unless the user asks to keep it.

## Current Project Schema

Image stimulus set:

```json
{
  "set_id": "condition-2-base",
  "name": "Condition 2 Base Images",
  "modality": "image",
  "source_dir": "stimuli/normalized-images/condition-2-base",
  "resolution": {"width_px": 512, "height_px": 512},
  "image_count": 2228,
  "available_variants": ["original"],
  "words": []
}
```

Word stimulus set:

```json
{
  "set_id": "condition-1-base-words",
  "name": "Condition 1 Base Words",
  "modality": "word",
  "source_dir": null,
  "resolution": null,
  "image_count": 0,
  "available_variants": ["original"],
  "manifest_tag": "word-list-v1",
  "words": ["Houston", "Miami"]
}
```

Condition:

```json
{
  "condition_id": "condition-1",
  "name": "Word Semantic Categorization Condition",
  "instructions": "Your task is to press the space bar...",
  "base_stimulus_set_id": "condition-1-base-words",
  "oddball_stimulus_set_id": "condition-1-oddball-words",
  "stimulus_variant": "original",
  "sequence_count": 1,
  "oddball_cycle_repeats_per_sequence": 146,
  "trigger_code": 15,
  "duty_cycle_mode": "blank_50",
  "order_index": 0
}
```

Set `settings.session.block_count` from the requested condition repeats. Keep
`settings.session.randomize_conditions_per_block=true` unless the user explicitly asks
for a legacy fixed order.

## Image Copy And Manifest

For image sets:

- copy only supported source image formats (`.jpg`, `.jpeg`, `.png` for compiler-ready
  originals; normalization can also read `.bmp`, `.tif`, `.tiff`)
- preserve source basenames when there are no collisions
- reject or deterministic-rename basename collisions, and report the policy
- compute SHA-256 for copied files
- write `stimuli/manifest.json` only for image-backed sets
- sort manifest assets by relative path for stable compilation

If validation reports non-square or mixed-size images, run Studio normalization helpers
or reproduce their center-crop PNG behavior. Keep `original-images` untouched and point
the active image sets at `normalized-images`.

## Word Lists

For word sets:

- trim surrounding whitespace
- reject blank entries before writing project data
- preserve duplicate words as distinct authored entries
- do not create fake image files
- copy original workbook/CSV files into `stimuli/original-word-lists/<set_id>/` only
  for provenance
- optionally write a `words.csv` beside the copied workbook for auditability

## Provenance Reports

Write at least:

- `source_image_mapping.csv`: set id, source list path, source row, source reference,
  resolved source path, destination relative path, SHA-256, width, height
- `skipped_source_rows.csv`: set id, source list path, source row, reference, reason
- `stimulus_set_summary.csv`: set id, name, source dir, count, resolution, modality
- `source_experiments.json`: condition id, linked `.psyexp`, target exists

Include copied source list files under `migration/source-lists/`, excluding protected
participant/IRB data unless explicitly requested.

## Verification Commands

Use the repo environment when possible:

```powershell
$env:PYTHONPATH = "<repo>\src"
.\.venv\Scripts\python.exe -c "from pathlib import Path; from fpvs_studio.core.serialization import load_project_file; from fpvs_studio.core.validation import validate_project; root=Path(r'<project>'); project=load_project_file(root/'project.json'); report=validate_project(project, refresh_hz=60.0); print(sum(1 for i in report.issues if i.severity.value == 'error')); print(sum(1 for i in report.issues if i.severity.value == 'warning'))"
```

Compile and preflight a mixed project:

```powershell
$env:PYTHONPATH = "<repo>\src"
.\.venv\Scripts\python.exe -c "from pathlib import Path; from fpvs_studio.core.serialization import load_project_file; from fpvs_studio.core.compiler import compile_session_plan; from fpvs_studio.core.validation import validate_display_refresh; from fpvs_studio.runtime.preflight import preflight_session_plan; root=Path(r'<project>'); project=load_project_file(root/'project.json'); plan=compile_session_plan(project, project_root=root, refresh_hz=60.0); entries=plan.ordered_entries(); class Engine: pass; Engine.validate_run_spec=lambda self, run_spec: validate_display_refresh(run_spec.display.refresh_hz); preflight_session_plan(root, plan, engine=Engine(), runtime_options={'strict_timing': False}); print(len(entries), sorted({entry.run_spec.condition.stimulus_modality.value for entry in entries}))"
```

Verify copied hashes:

```python
from pathlib import Path
import csv, hashlib

project = Path(r"<project>")
def h(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

bad = []
with (project / "migration" / "source_image_mapping.csv").open(encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        if h(Path(row["source_path"])) != h(project / Path(row["destination_relative_path"])):
            bad.append(row["destination_relative_path"])
print(len(bad), bad[:5])
```

## Common Findings

- A PsychoPy source list may contain non-image rows such as `run.bat`; skip and report
  those rows, do not copy them as stimuli.
- Legacy image dimensions often differ by condition. Studio launch readiness may require
  normalized square active copies even when the exact original images were copied.
- Word-list conditions may produce repeat-balance warnings because the authored list is
  small relative to 146 oddball cycles. These are warnings unless the user wants list
  expansion or timing changes.
