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
        "tests\unit\test_compiler.py",
        "tests\unit\test_session_plan.py"
    )
}
finally {
    Pop-Location
}
