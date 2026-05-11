param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv3.10\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string]$File,
        [string[]]$Arguments
    )

    & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $File $($Arguments -join ' ')"
    }
}

function Remove-RepoOutput {
    param([string]$RelativePath)

    $target = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $target)) {
        return
    }

    $resolvedRepo = (Resolve-Path -LiteralPath $RepoRoot).Path
    $resolvedTarget = (Resolve-Path -LiteralPath $target).Path
    if (-not $resolvedTarget.StartsWith($resolvedRepo, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside repo: $resolvedTarget"
    }

    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
}

function Get-AppVersion {
    $pyprojectPath = Join-Path $RepoRoot "pyproject.toml"
    $versionLine = Select-String -Path $pyprojectPath -Pattern '^version = "([^"]+)"$' |
        Select-Object -First 1
    if ($null -eq $versionLine) {
        throw "Could not find [project] version in pyproject.toml."
    }
    return $versionLine.Matches[0].Groups[1].Value
}

function Assert-PackageMetadataVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExpectedVersion
    )

    $versionOutput = & $Python -c "import importlib.metadata as m, sys, fpvs_studio; sys.stdout.write(fpvs_studio.__version__ + '\n' + m.version('fpvs-studio') + '\n')"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not verify installed fpvs-studio package metadata."
    }
    $versions = @($versionOutput)
    if ($versions.Count -lt 2) {
        throw "Package metadata verification did not return both source and installed versions."
    }
    $sourceVersion = $versions[0].Trim()
    $metadataVersion = $versions[1].Trim()
    if ($sourceVersion -ne $ExpectedVersion -or $metadataVersion -ne $ExpectedVersion) {
        throw (
            "Package version drift before PyInstaller build. " +
            "pyproject.toml=$ExpectedVersion, fpvs_studio.__version__=$sourceVersion, " +
            "installed metadata=$metadataVersion. Re-run without -SkipInstall or refresh the environment."
        )
    }
}

function Assert-BundledPackageMetadataVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExpectedVersion
    )

    $bundleRoot = Join-Path $RepoRoot "dist\FPVS Studio"
    $metadataDirs = @(
        Get-ChildItem -Path $bundleRoot -Recurse -Directory -Filter "fpvs_studio-*.dist-info"
    )
    if ($metadataDirs.Count -ne 1) {
        throw "Expected exactly one bundled fpvs-studio dist-info directory; found $($metadataDirs.Count)."
    }
    $metadataPath = Join-Path $metadataDirs[0].FullName "METADATA"
    $versionLine = Select-String -Path $metadataPath -Pattern '^Version: (.+)$' |
        Select-Object -First 1
    if ($null -eq $versionLine) {
        throw "Bundled fpvs-studio metadata has no Version field: $metadataPath"
    }
    $metadataVersion = $versionLine.Matches[0].Groups[1].Value.Trim()
    if ($metadataVersion -ne $ExpectedVersion) {
        throw (
            "Bundled fpvs-studio metadata version drift. " +
            "pyproject.toml=$ExpectedVersion, bundled metadata=$metadataVersion."
        )
    }
}

Push-Location $RepoRoot
try {
    $pythonVersion = & $Python -c "import sys; sys.stdout.write(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not run Python executable: $Python"
    }
    if ($pythonVersion.Trim() -ne "3.10") {
        throw "FPVS Studio packaging requires Python 3.10; found $pythonVersion at $Python"
    }

    if (-not $SkipInstall) {
        Invoke-Native -File $Python -Arguments @(
            "-m",
            "pip",
            "install",
            "-e",
            ".[engine,packaging]"
        )
    }

    $appVersion = Get-AppVersion
    Assert-PackageMetadataVersion -ExpectedVersion $appVersion

    Remove-RepoOutput "build\pyinstaller"
    Remove-RepoOutput "dist\FPVS Studio"

    Invoke-Native -File $Python -Arguments @(
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--workpath",
        "build\pyinstaller",
        "--distpath",
        "dist",
        "packaging\pyinstaller\fpvs_studio.spec"
    )

    $exePath = Join-Path $RepoRoot "dist\FPVS Studio\FPVS Studio.exe"
    if (-not (Test-Path -LiteralPath $exePath)) {
        throw "Expected packaged executable was not created: $exePath"
    }
    Assert-BundledPackageMetadataVersion -ExpectedVersion $appVersion

    Write-Output ""
    Write-Output "FPVS Studio executable built successfully:"
    Write-Output "  $exePath"
}
finally {
    Pop-Location
}
