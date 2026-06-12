param(
    [string]$SourcePng
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "script_helpers.ps1")
$Python = Resolve-RepoPython -RepoRoot $RepoRoot

$Arguments = @((Join-Path $PSScriptRoot "sync_branding_assets.py"))
if ($SourcePng) {
    $Arguments += @("--source", $SourcePng)
}

Invoke-NativeChecked -File $Python -Arguments $Arguments
