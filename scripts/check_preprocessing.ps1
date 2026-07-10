$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "script_helpers.ps1")
$Python = Resolve-RepoPython -RepoRoot $RepoRoot

Push-Location $RepoRoot
try {
    Invoke-NativeChecked -File $Python -Arguments @(
        ".agents\scripts\verify.py",
        "--scope",
        "preprocessing",
        "--tier",
        "focused"
    )
}
finally {
    Pop-Location
}
