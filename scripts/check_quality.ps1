param(
    [switch]$FullCi
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "script_helpers.ps1")
$Python = Resolve-RepoPython -RepoRoot $RepoRoot

Push-Location $RepoRoot
try {
    $Tier = if ($FullCi) { "full-ci" } else { "precommit" }
    Invoke-NativeChecked -File $Python -Arguments @(
        ".agents\scripts\verify.py",
        "--scope",
        "repo",
        "--tier",
        $Tier
    )
}
finally {
    Pop-Location
}
