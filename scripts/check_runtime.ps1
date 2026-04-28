$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv3.10\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

Push-Location $RepoRoot
try {
    & $Python -m pytest -q `
        tests\unit\test_runtime_launcher_flow.py `
        tests\unit\test_runtime_launcher_feedback_abort.py `
        tests\unit\test_runtime_launcher_export.py `
        tests\unit\test_runtime_launch_settings.py `
        tests\unit\test_runtime_preflight.py `
        tests\unit\test_runtime_participant_history.py `
        tests\unit\test_runtime_fixation.py
}
finally {
    Pop-Location
}
