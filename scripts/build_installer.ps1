param(
    [string]$InnoCompiler,
    [switch]$SkipSmoke,
    [switch]$AllowVisibleGui,
    [string]$BuildLabel,
    [string[]]$BaselineInventory = @(),
    [string[]]$BaselineInventorySha256 = @()
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "script_helpers.ps1")
. (Join-Path $PSScriptRoot "build_paths.ps1")
$BuildPaths = Get-PackagingBuildPaths -RepoRoot $RepoRoot -BuildLabel $BuildLabel
$Python = Resolve-RepoPython -RepoRoot $RepoRoot
$SpecPath = Join-Path $RepoRoot "packaging\inno\fpvs_studio.iss"
$BundleRoot = $BuildPaths.BundleRoot
$BundleExePath = Join-Path $BundleRoot "FPVS Studio.exe"
$BundleInternalPath = Join-Path $BundleRoot "_internal"
$InstallerOutputDir = $BuildPaths.InstallerRoot
$SmokePackagedAppScript = Join-Path $PSScriptRoot "smoke_packaged_app.ps1"
$BuildUpdaterScript = Join-Path $PSScriptRoot "build_updater.ps1"
$InventoryScript = Join-Path $PSScriptRoot "build_installer_inventory.py"
$LegacyInventoryPath = Join-Path $RepoRoot "packaging\inventory\published-legacy-inventory.json"
$InventoryOutputDir = $BuildPaths.InventoryRoot

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
        throw "Expected PyInstaller bundle was not found: $BundleExePath. Run .\scripts\build_exe.ps1 with the same BuildLabel first."
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
    $metadataVersion = Select-String -LiteralPath $metadataPath -Pattern '^Version: (.+)$' |
        Select-Object -First 1
    if ($null -eq $metadataVersion -or
        $metadataVersion.Matches[0].Groups[1].Value.Trim() -ne (Get-AppVersion)) {
        throw "The Studio bundle version does not match pyproject.toml; rebuild it before adding the updater."
    }
}

function Invoke-PackagedSmoke {
    if (-not (Test-Path -LiteralPath $SmokePackagedAppScript)) {
        throw "Packaged app smoke script was not found: $SmokePackagedAppScript"
    }
    & $SmokePackagedAppScript -ExePath $BundleExePath -AllowVisibleGui:$AllowVisibleGui
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

    $registryPaths = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"
    )
    foreach ($registryPath in $registryPaths) {
        $registration = Get-ItemProperty -LiteralPath $registryPath -ErrorAction SilentlyContinue
        if ($registration -and $registration.InstallLocation) {
            $candidatePath = Join-Path $registration.InstallLocation "ISCC.exe"
            if (Test-Path -LiteralPath $candidatePath) {
                return (Resolve-Path -LiteralPath $candidatePath).Path
            }
        }
    }

    throw (
        "Inno Setup compiler was not found. Install Inno Setup 6, add ISCC.exe to PATH, " +
        "set ISCC_EXE, or pass -InnoCompiler with the full ISCC.exe path."
    )
}

Push-Location $RepoRoot
try {
    if ($BaselineInventory.Count -ne $BaselineInventorySha256.Count) {
        throw "Supply one authenticated BaselineInventorySha256 for every BaselineInventory."
    }
    if (-not (Test-Path -LiteralPath $SpecPath)) {
        throw "Inno Setup script was not found: $SpecPath"
    }
    Assert-BundleInput
    Write-Output "Building the independent FPVS Studio updater before final bundle inventory..."
    & $BuildUpdaterScript -BuildLabel $BuildLabel -AllowVisibleGui:$AllowVisibleGui
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $BuildUpdaterScript"
    }
    if (-not $SkipSmoke) {
        Write-Output "Running packaged app smoke check before installer build..."
        Invoke-PackagedSmoke
    }

    $appVersion = Get-AppVersion
    Invoke-Native -File $Python -Arguments @(
        $InventoryScript,
        "--bundle-root", $BundleRoot,
        "--app-version", $appVersion,
        "--legacy-inventory", $LegacyInventoryPath,
        "--output-dir", $InventoryOutputDir
    )
    $isccPath = Resolve-InnoCompiler -ConfiguredPath $InnoCompiler
    Remove-PackagingOutput -RepoRoot $RepoRoot -TargetPath $InstallerOutputDir
    New-Item -ItemType Directory -Force -Path $InstallerOutputDir | Out-Null

    Invoke-Native -File $isccPath -Arguments @(
        "/DAppVersion=$appVersion",
        "/DBundleRoot=$BundleRoot",
        "/DOwnedInventoryRoot=$InventoryOutputDir",
        "/O$InstallerOutputDir",
        "/FFPVS-Studio-Setup-$appVersion",
        $SpecPath
    )

    $installerPath = Join-Path $InstallerOutputDir "FPVS-Studio-Setup-$appVersion.exe"
    if (-not (Test-Path -LiteralPath $installerPath)) {
        throw "Expected installer was not created: $installerPath"
    }

    $patchScript = Join-Path $PSScriptRoot "build_patch.py"
    $patchBuilds = @()
    for ($index = 0; $index -lt $BaselineInventory.Count; $index++) {
        $patchRoot = Join-Path $InventoryOutputDir "patch-$index"
        Remove-PackagingOutput -RepoRoot $RepoRoot -TargetPath $patchRoot
        Invoke-Native -File $Python -Arguments @(
            $patchScript, "prepare",
            "--baseline-inventory", ([System.IO.Path]::GetFullPath($BaselineInventory[$index])),
            "--source-inventory-sha256", $BaselineInventorySha256[$index],
            "--bundle-root", $BundleRoot,
            "--target-inventory", (Join-Path $InventoryOutputDir "current-owned-files.txt"),
            "--target-version", $appVersion,
            "--output-dir", $patchRoot
        )
        $patchBuild = Join-Path $patchRoot "patch-build.json"
        $patch = Get-Content -LiteralPath $patchBuild -Raw | ConvertFrom-Json
        Invoke-Native -File $isccPath -Arguments @(
            "/DAppVersion=$appVersion",
            "/DBundleRoot=$BundleRoot",
            "/DOwnedInventoryRoot=$InventoryOutputDir",
            "/DPatchFromVersion=$($patch.from_version)",
            "/DPatchRoot=$patchRoot",
            "/DPatchSourceSHA256=$($patch.source_inventory_sha256)",
            "/DPatchTargetSHA256=$($patch.target_inventory_sha256)",
            "/DPatchTransactionSHA256=$($patch.transaction_sha256)",
            "/O$InstallerOutputDir",
            "/F$([System.IO.Path]::GetFileNameWithoutExtension($patch.asset_name))",
            $SpecPath
        )
        $patchBuilds += $patchBuild
    }
    $manifestArguments = @(
        $patchScript, "manifest", "--target-version", $appVersion,
        "--installer-dir", $InstallerOutputDir
    )
    foreach ($patchBuild in $patchBuilds) {
        $manifestArguments += @("--patch-build", $patchBuild)
    }
    Invoke-Native -File $Python -Arguments $manifestArguments

    Write-Output ""
    Write-Output "FPVS Studio installer built successfully:"
    Write-Output "  $installerPath"
}
finally {
    Pop-Location
}
