$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv3.10\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

Push-Location $RepoRoot
try {
    & $Python -m ruff check src tests
    & $Python -m mypy src
    & $Python -m pytest -q tests\unit\test_harness_docs.py
    & $Python -m pytest -q tests\unit\test_import_boundaries.py

    $env:QT_QPA_PLATFORM = "offscreen"
    $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
    & $Python -m pytest `
        --disable-plugin-autoload `
        -p pytestqt.plugin `
        -p pytest_timeout `
        --basetemp=build\pytest_tmp_quality_gui `
        --maxfail=1 `
        --timeout=60 `
        -q `
        tests\gui\test_assets_run_launch.py::test_assets_preprocessing_import_and_materialize_updates_status `
        tests\gui\test_assets_run_launch.py::test_launch_action_wires_runtime_launcher_with_serial_settings `
        tests\gui\test_assets_run_launch.py::test_launch_action_closes_progress_dialog_when_runtime_launch_raises
}
finally {
    Pop-Location
}
