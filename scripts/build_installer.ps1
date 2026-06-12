param(
    [string]$InnoCompiler,
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$SpecPath = Join-Path $RepoRoot "packaging\inno\fpvs_studio.iss"
$BundleExePath = Join-Path $RepoRoot "dist\FPVS Studio\FPVS Studio.exe"
$BundleInternalPath = Join-Path $RepoRoot "dist\FPVS Studio\_internal"
$InstallerOutputDir = Join-Path $RepoRoot "dist\installer"
$SmokePackagedAppScript = Join-Path $PSScriptRoot "smoke_packaged_app.ps1"

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

function Get-AppVersion {
    $pyprojectPath = Join-Path $RepoRoot "pyproject.toml"
    $versionLine = Select-String -Path $pyprojectPath -Pattern '^version = "([^"]+)"$' |
        Select-Object -First 1
    if ($null -eq $versionLine) {
        throw "Could not find [project] version in pyproject.toml."
    }
    return $versionLine.Matches[0].Groups[1].Value
}

function Assert-BundleInput {
    if (-not (Test-Path -LiteralPath $BundleExePath)) {
        throw "Expected PyInstaller bundle was not found. Run .\scripts\build_exe.ps1 first."
    }
    if (-not (Test-Path -LiteralPath $BundleInternalPath)) {
        throw "Expected PyInstaller bundle internals were not found: $BundleInternalPath"
    }

    $metadataDirs = @(
        Get-ChildItem -Path $BundleInternalPath -Directory -Filter "fpvs_studio-*.dist-info"
    )
    if ($metadataDirs.Count -ne 1) {
        throw "Expected exactly one bundled fpvs-studio dist-info directory; found $($metadataDirs.Count)."
    }

    $metadataPath = Join-Path $metadataDirs[0].FullName "METADATA"
    if (-not (Test-Path -LiteralPath $metadataPath)) {
        throw "Bundled fpvs-studio metadata was missing: $metadataPath"
    }
}

function Invoke-PackagedSmoke {
    if (-not (Test-Path -LiteralPath $SmokePackagedAppScript)) {
        throw "Packaged app smoke script was not found: $SmokePackagedAppScript"
    }
    & $SmokePackagedAppScript -ExePath $BundleExePath
}

function Resolve-InnoCompiler {
    param([string]$ConfiguredPath)

    if ($ConfiguredPath) {
        if (-not (Test-Path -LiteralPath $ConfiguredPath)) {
            throw "Inno Setup compiler was not found at: $ConfiguredPath"
        }
        return (Resolve-Path -LiteralPath $ConfiguredPath).Path
    }

    if ($env:ISCC_EXE) {
        if (-not (Test-Path -LiteralPath $env:ISCC_EXE)) {
            throw "ISCC_EXE points to a missing file: $env:ISCC_EXE"
        }
        return (Resolve-Path -LiteralPath $env:ISCC_EXE).Path
    }

    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    $candidatePaths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidatePath in $candidatePaths) {
        if ($candidatePath -and (Test-Path -LiteralPath $candidatePath)) {
            return (Resolve-Path -LiteralPath $candidatePath).Path
        }
    }

    throw (
        "Inno Setup compiler was not found. Install Inno Setup 6, add ISCC.exe to PATH, " +
        "set ISCC_EXE, or pass -InnoCompiler with the full ISCC.exe path."
    )
}

Push-Location $RepoRoot
try {
    if (-not (Test-Path -LiteralPath $SpecPath)) {
        throw "Inno Setup script was not found: $SpecPath"
    }
    Assert-BundleInput
    if (-not $SkipSmoke) {
        Write-Output "Running packaged app smoke check before installer build..."
        Invoke-PackagedSmoke
    }

    $appVersion = Get-AppVersion
    $isccPath = Resolve-InnoCompiler -ConfiguredPath $InnoCompiler
    Remove-RepoOutput "dist\installer"
    New-Item -ItemType Directory -Force -Path $InstallerOutputDir | Out-Null

    Invoke-Native -File $isccPath -Arguments @(
        "/DAppVersion=$appVersion",
        "/O$InstallerOutputDir",
        "/FFPVS-Studio-Setup-$appVersion",
        $SpecPath
    )

    $installerPath = Join-Path $InstallerOutputDir "FPVS-Studio-Setup-$appVersion.exe"
    if (-not (Test-Path -LiteralPath $installerPath)) {
        throw "Expected installer was not created: $installerPath"
    }

    Write-Output ""
    Write-Output "FPVS Studio installer built successfully:"
    Write-Output "  $installerPath"
}
finally {
    Pop-Location
}
