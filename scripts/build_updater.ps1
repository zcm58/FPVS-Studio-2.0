param(
    [string]$BuildLabel,
    [switch]$AllowVisibleGui
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "script_helpers.ps1")
. (Join-Path $PSScriptRoot "build_paths.ps1")
$BuildPaths = Get-PackagingBuildPaths -RepoRoot $RepoRoot -BuildLabel $BuildLabel
$Python = Resolve-RepoPython -RepoRoot $RepoRoot
$UpdaterWorkRoot = Join-Path (Split-Path -Parent $BuildPaths.WorkRoot) "pyinstaller-updater"
$UpdaterRoot = Join-Path $BuildPaths.BundleRoot "Updater"
$null = Assert-PackagingOutputPath -RepoRoot $RepoRoot -TargetPath $UpdaterWorkRoot
$null = Assert-PackagingOutputPath -RepoRoot $RepoRoot -TargetPath $UpdaterRoot

Push-Location $RepoRoot
try {
    # The ordinary executable stage owns dependency installation. Reject stale
    # metadata here, including standalone builds, without changing the environment.
    $versionLine = Select-String -LiteralPath (Join-Path $RepoRoot "pyproject.toml") `
        -Pattern '^version = "([^"]+)"$' | Select-Object -First 1
    if ($null -eq $versionLine) {
        throw "Could not find [project] version in pyproject.toml."
    }
    $appVersion = $versionLine.Matches[0].Groups[1].Value
    $versions = @(Invoke-NativeOutputChecked -File $Python -Arguments @(
        "-c",
        "import importlib.metadata as m, sys, fpvs_studio; sys.stdout.write(fpvs_studio.__version__ + '\n' + m.version('fpvs-studio') + '\n')"
    ))
    if ($versions.Count -ne 2 -or $versions[0].Trim() -ne $appVersion -or
        $versions[1].Trim() -ne $appVersion) {
        throw "Updater package metadata does not match pyproject.toml; refresh the editable installation first."
    }

    Remove-PackagingOutput -RepoRoot $RepoRoot -TargetPath $UpdaterWorkRoot
    Remove-PackagingOutput -RepoRoot $RepoRoot -TargetPath $UpdaterRoot
    Invoke-NativeChecked -File $Python -Arguments @(
        "-m", "PyInstaller", "--noconfirm", "--clean",
        "--workpath", $UpdaterWorkRoot,
        "--distpath", $UpdaterRoot,
        "packaging\pyinstaller\fpvs_updater.spec"
    )
    $updaterExe = Join-Path $UpdaterRoot "FPVS Studio Updater.exe"
    if (-not (Test-Path -LiteralPath $updaterExe -PathType Leaf)) {
        throw "Expected updater executable was not created: $updaterExe"
    }

    # This diagnostic loads only the updater backend: no Qt window, network,
    # installed-app mutation, user profile writes, or installer execution.
    $reportPath = Join-Path $UpdaterWorkRoot "packaging-check.json"
    $process = Start-Process -FilePath $updaterExe -WindowStyle Hidden -PassThru `
        -ArgumentList @("--packaging-check", "`"$reportPath`"")
    try {
        if (-not $process.WaitForExit(60000)) {
            $process.Kill()
            throw "Updater packaging diagnostic timed out."
        }
        if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
            throw "Updater packaging diagnostic failed with exit code $($process.ExitCode)."
        }
    }
    finally {
        $process.Dispose()
    }
    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    if ($report.version -ne $appVersion -or $report.frozen -ne $true -or
        $report.protocol_version -ne 1 -or $report.gui_loaded -ne $false) {
        throw "Updater packaging diagnostic rejected metadata, process mode, or GUI independence: $reportPath"
    }
    if ($AllowVisibleGui) {
        if ($env:QT_QPA_PLATFORM -in @("offscreen", "minimal")) {
            throw "Updater visible smoke requires a native Windows session, not offscreen Qt."
        }
        $guiReportPath = Join-Path $UpdaterWorkRoot "gui-smoke.json"
        $guiProcess = Start-Process -FilePath $updaterExe -WindowStyle Normal -PassThru `
            -ArgumentList @("--gui-smoke", "`"$guiReportPath`"")
        try {
            if (-not $guiProcess.WaitForExit(30000)) {
                $guiProcess.Kill()
                throw "Updater visible smoke timed out."
            }
            if ($guiProcess.ExitCode -ne 0 -or
                -not (Test-Path -LiteralPath $guiReportPath -PathType Leaf)) {
                throw "Updater visible smoke failed: $guiReportPath"
            }
        }
        finally {
            $guiProcess.Dispose()
        }
        $guiReport = Get-Content -LiteralPath $guiReportPath -Raw | ConvertFrom-Json
        if ($guiReport.passed -ne $true -or $guiReport.network -ne $false -or
            $guiReport.installer -ne $false -or $guiReport.standalone_repair -ne $true -or
            $guiReport.repair_after_failure -ne $true) {
            throw "Updater visible smoke rejected the UI result: $guiReportPath"
        }
    }
    Write-Output "FPVS Studio updater built and checked successfully: $updaterExe"
}
finally {
    Pop-Location
}
