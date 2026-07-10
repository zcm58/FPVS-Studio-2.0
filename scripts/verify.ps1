param(
    [string]$Scope,
    [ValidateSet("focused", "precommit", "full-ci")]
    [string]$Tier = "focused",
    [switch]$List,
    [switch]$CheckConfig
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "script_helpers.ps1")
$Python = Resolve-RepoPython -RepoRoot $RepoRoot
$VerifyArgs = @(".agents\scripts\verify.py")

if ($CheckConfig -and ($List -or -not [string]::IsNullOrWhiteSpace($Scope))) {
    throw "-CheckConfig cannot be combined with -List or -Scope."
}
if ($CheckConfig) {
    $VerifyArgs += "--check-config"
}
elseif ($List -and [string]::IsNullOrWhiteSpace($Scope)) {
    $VerifyArgs += "--list"
}
else {
    if ([string]::IsNullOrWhiteSpace($Scope)) {
        throw "-Scope is required unless -CheckConfig is used."
    }
    $VerifyArgs += @("--scope", $Scope, "--tier", $Tier)
}
if ($List -and -not [string]::IsNullOrWhiteSpace($Scope)) {
    $VerifyArgs += "--list"
}

Push-Location $RepoRoot
try {
    Invoke-NativeChecked -File $Python -Arguments $VerifyArgs
}
finally {
    Pop-Location
}
