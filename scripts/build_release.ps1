param(
    [switch]$SkipInstall,
    [string]$InnoCompiler,
    [string]$BuildLabel
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BuildExeScript = Join-Path $PSScriptRoot "build_exe.ps1"
$BuildInstallerScript = Join-Path $PSScriptRoot "build_installer.ps1"

Push-Location $RepoRoot
try {
    Write-Output "Building FPVS Studio executable bundle..."
    if (-not $SkipInstall) {
        Write-Output (
            "Network access is required for this release build because the executable " +
            "stage refreshes editable package dependencies with pip. In Codex or another " +
            "sandboxed runner, run this script with elevated network permissions."
        )
    }
    if ($SkipInstall) {
        & $BuildExeScript -SkipInstall -BuildLabel $BuildLabel
    }
    else {
        & $BuildExeScript -BuildLabel $BuildLabel
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $BuildExeScript"
    }

    Write-Output ""
    Write-Output "Building FPVS Studio installer..."
    if ($InnoCompiler) {
        & $BuildInstallerScript -InnoCompiler $InnoCompiler -BuildLabel $BuildLabel
    }
    else {
        & $BuildInstallerScript -BuildLabel $BuildLabel
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $BuildInstallerScript"
    }

    Write-Output ""
    Write-Output "FPVS Studio release build completed successfully."
}
finally {
    Pop-Location
}
