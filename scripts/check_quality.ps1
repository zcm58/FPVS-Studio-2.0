$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "script_helpers.ps1")
$Python = Resolve-RepoPython -RepoRoot $RepoRoot

Push-Location $RepoRoot
try {
    Invoke-NativeChecked -File $Python -Arguments @("-m", "ruff", "check", "src", "tests")
    Invoke-NativeChecked -File $Python -Arguments @("-m", "mypy", "src")
    Invoke-NativeChecked -File $Python -Arguments @(
        "-m",
        "pytest",
        "-q",
        "tests\unit\test_harness_docs.py"
    )
    Invoke-NativeChecked -File $Python -Arguments @(
        "-m",
        "pytest",
        "-q",
        "tests\unit\test_import_boundaries.py"
    )
    & (Join-Path $PSScriptRoot "check_gc.ps1") -SkipLineCounts

    $env:QT_QPA_PLATFORM = "offscreen"
    $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
    Invoke-NativeChecked -File $Python -Arguments @(
        "-m",
        "pytest",
        "--disable-plugin-autoload",
        "-p",
        "pytestqt.plugin",
        "-p",
        "pytest_timeout",
        "--basetemp=build\pytest_tmp_quality_gui",
        "--maxfail=1",
        "--timeout=60",
        "-q",
        "tests\gui\test_assets_run_launch.py::test_assets_preprocessing_import_and_materialize_updates_status",
        "tests\gui\test_assets_run_launch.py::test_launch_action_wires_runtime_launcher_with_backend_launch_settings",
        "tests\gui\test_assets_run_launch.py::test_launch_action_closes_progress_dialog_when_runtime_launch_raises"
    )
}
finally {
    Pop-Location
}
