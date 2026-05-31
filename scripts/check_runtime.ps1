$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "script_helpers.ps1")
$Python = Resolve-RepoPython -RepoRoot $RepoRoot

Push-Location $RepoRoot
try {
    Invoke-NativeChecked -File $Python -Arguments @(
        "-m",
        "pytest",
        "-q",
        "tests\unit\test_runtime_launcher_flow.py",
        "tests\unit\test_runtime_launcher_feedback_abort.py",
        "tests\unit\test_runtime_launcher_export.py",
        "tests\unit\test_runtime_launch_settings.py",
        "tests\unit\test_runtime_preflight.py",
        "tests\unit\test_runtime_participant_history.py",
        "tests\unit\test_runtime_fixation.py"
    )
}
finally {
    Pop-Location
}
