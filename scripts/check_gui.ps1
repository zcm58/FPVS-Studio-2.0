$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "script_helpers.ps1")
$Python = Resolve-RepoPython -RepoRoot $RepoRoot

if ($env:FPVS_ALLOW_QT_TESTS -notin @("1", "true", "yes", "on")) {
    throw (
        "GUI tests require explicit opt-in. Set FPVS_ALLOW_QT_TESTS=1 only in CI " +
        "or a user-approved safe visible Qt environment."
    )
}

Push-Location $RepoRoot
try {
    Invoke-NativeChecked -File $Python -Arguments @(
        ".agents\scripts\verify.py",
        "--scope",
        "gui",
        "--tier",
        "full-ci"
    )
}
finally {
    Pop-Location
}
