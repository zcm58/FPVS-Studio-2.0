$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv3.10\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

Push-Location $RepoRoot
try {
    & $Python -m pytest -q `
        tests\unit\test_preprocessing_assets.py `
        tests\unit\test_preprocessing_inspection.py
}
finally {
    Pop-Location
}
