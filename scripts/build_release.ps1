param(
    [switch]$SkipInstall,
    [string]$InnoCompiler
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BuildExeScript = Join-Path $PSScriptRoot "build_exe.ps1"
$BuildInstallerScript = Join-Path $PSScriptRoot "build_installer.ps1"

function Invoke-RepoScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,
        [string[]]$ScriptArguments = @()
    )

    & $ScriptPath @ScriptArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $ScriptPath $($ScriptArguments -join ' ')"
    }
}

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
        & $BuildExeScript -SkipInstall
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code ${LASTEXITCODE}: $BuildExeScript -SkipInstall"
        }
    }
    else {
        Invoke-RepoScript -ScriptPath $BuildExeScript
    }

    Write-Output ""
    Write-Output "Building FPVS Studio installer..."
    if ($InnoCompiler) {
        & $BuildInstallerScript -InnoCompiler $InnoCompiler
    }
    else {
        & $BuildInstallerScript
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
