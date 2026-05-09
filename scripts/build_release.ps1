param(
    [switch]$SkipInstall,
    [string]$InnoCompiler
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BuildExeScript = Join-Path $PSScriptRoot "build_exe.ps1"
$BuildInstallerScript = Join-Path $PSScriptRoot "build_installer.ps1"
$SmokePackagedAppScript = Join-Path $PSScriptRoot "smoke_packaged_app.ps1"

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
    Write-Output "Running packaged app smoke check..."
    Invoke-RepoScript -ScriptPath $SmokePackagedAppScript

    $installerArguments = @()
    if ($InnoCompiler) {
        $installerArguments += @("-InnoCompiler", $InnoCompiler)
    }

    Write-Output ""
    Write-Output "Building FPVS Studio installer..."
    Invoke-RepoScript -ScriptPath $BuildInstallerScript -ScriptArguments $installerArguments

    Write-Output ""
    Write-Output "FPVS Studio release build completed successfully."
}
finally {
    Pop-Location
}
