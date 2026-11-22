param(
    [Parameter(Mandatory)][string]$SourceRoot,
    [Parameter(Mandatory)][string]$ReceiptPath,
    [Parameter(Mandatory)][string]$EvidenceDir
)

$ErrorActionPreference = 'Stop'
if (-not $IsWindows -or $env:GITHUB_ACTIONS -cne 'true' -or
    $env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or $env:RUNNER_OS -cne 'Windows' -or
    $env:RUNNER_ARCH -cne 'X64') {
    throw 'Installer lifecycle checks require a disposable GitHub-hosted Windows x64 runner.'
}
if ($env:QT_QPA_PLATFORM -in @('offscreen', 'minimal')) {
    throw 'Native Windows Qt is required.'
}

# The workflow authenticates the receipt and installer bytes before calling this script.
$receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
$checkout = git -C $SourceRoot rev-parse --verify HEAD
if ($LASTEXITCODE -ne 0 -or $checkout -cne $receipt.source_commit) {
    throw 'The candidate checkout does not match the authenticated source commit.'
}
$smokeSource = Join-Path $SourceRoot 'src/fpvs_studio/gui/packaged_smoke.py'
$supportsPlaybackSmoke = (Test-Path -LiteralPath $smokeSource -PathType Leaf) -and
    (Select-String -LiteralPath $smokeSource -Pattern 'FPVS_PACKAGED_PLAYBACK_SMOKE' -SimpleMatch -Quiet)
if ($receipt.target_inventory_sha256 -notmatch '^[0-9a-f]{64}$') {
    throw 'The receipt is missing the expected target inventory SHA-256.'
}
if ($receipt.patches -isnot [array] -or $receipt.patches.Count -gt 5) {
    throw 'The receipt must contain an array of up to five patches.'
}
$fullBaselineInventoryHash = ''
$installers = @($receipt.baseline_installer, $receipt.target_installer)
$patchVersions = [System.Collections.Generic.HashSet[string]]::new()
foreach ($patch in $receipt.patches) {
    if ($patch.baseline_version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$' -or
        -not $patchVersions.Add($patch.baseline_version)) {
        throw 'Each patch must have a distinct stable baseline version.'
    }
    if ($patch.baseline_inventory_sha256 -notmatch '^[0-9a-f]{64}$') {
        throw "Patch acceptance from $($patch.baseline_version) requires the authenticated source inventory SHA-256."
    }
    if ($patch.baseline_version -ceq $receipt.baseline_version) {
        $fullBaselineInventoryHash = $patch.baseline_inventory_sha256
    }
    $installers += @($patch.baseline_installer, $patch.patch_installer)
}
foreach ($installer in $installers) {
    if (-not $installer -or -not [IO.Path]::IsPathFullyQualified($installer) -or
        -not (Test-Path -LiteralPath $installer -PathType Leaf)) {
        throw 'An authenticated installer path is missing.'
    }
}

$installRoot = Join-Path $env:LOCALAPPDATA 'Programs\FPVS Studio'
$uninstallId = '{C0EAFB18-1DC5-4C77-8FDB-F6C1E7874694}_is1'
$registryRoots = @(
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall'
    'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'
)
if (Test-Path -LiteralPath $installRoot) {
    throw 'The runner already contains a canonical Studio installation folder.'
}
foreach ($registryRoot in $registryRoots) {
    if (Test-Path -LiteralPath (Join-Path $registryRoot $uninstallId)) {
        throw 'The runner already has a Studio uninstall registration.'
    }
}

$work = Join-Path $EvidenceDir 'lifecycle'
if (Test-Path -LiteralPath $work) {
    throw 'The lifecycle evidence directory already exists.'
}
$null = New-Item -ItemType Directory -Path $work
$manifest = Join-Path $installRoot 'fpvs-owned-files-v1.txt'
$patchMarker = Join-Path $installRoot 'fpvs-patch-transaction-v1.txt'
$app = Join-Path $installRoot 'FPVS Studio.exe'
$updater = Join-Path $installRoot 'Updater\FPVS Studio Updater.exe'
$treeChecker = Join-Path $SourceRoot 'scripts/check_installer_tree.py'
$legacyInventory = Join-Path $SourceRoot 'packaging/inventory/published-legacy-inventory.json'
$settingsKey = 'HKCU:\Software\FPVS Studio\FPVS Studio'
$userSentinel = Join-Path $installRoot 'lab-notes.txt'

function Invoke-InstallerProcess([string]$Executable, [string[]]$Arguments, [string]$Operation) {
    # Waiting for the whole process tree also covers the Inno child process.
    # The hosted job timeout bounds setup and uninstall.
    $run = Start-Process -FilePath $Executable -ArgumentList $Arguments -Wait -PassThru -WindowStyle Hidden
    try {
        if ($run.ExitCode -ne 0) {
            throw "$Operation exited with code $($run.ExitCode)."
        }
    } finally {
        $run.Dispose()
    }
}

function Invoke-Setup([string]$Executable, [string]$Phase) {
    $log = Join-Path $work "$Phase-setup.log"
    $arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/NOLAUNCH=1', ('/LOG="' + $log + '"'))
    Invoke-InstallerProcess $Executable $arguments "$Phase setup"
    if (-not (Test-Path -LiteralPath $app -PathType Leaf)) {
        throw "$Phase Studio executable was not installed."
    }
}

function Invoke-NativeSmoke(
    [string]$Executable, [string]$Option, [string]$ReportPath, [int]$TimeoutMilliseconds,
    [switch]$Playback
) {
    $savedPath = $env:PATH
    $savedQt = $env:FPVS_ALLOW_QT_TESTS
    $savedPlayback = $env:FPVS_PACKAGED_PLAYBACK_SMOKE
    try {
        $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
        $env:FPVS_ALLOW_QT_TESTS = '1'
        $env:FPVS_PACKAGED_PLAYBACK_SMOKE = if ($Playback) { '1' } else { $null }
        $run = Start-Process -FilePath $Executable -ArgumentList @($Option, ('"' + $ReportPath + '"')) -PassThru
        try {
            if (-not $run.WaitForExit($TimeoutMilliseconds)) {
                $run.Kill()
                throw "Packaged smoke timed out for $Executable."
            }
            if (-not (Test-Path -LiteralPath $ReportPath -PathType Leaf)) {
                throw "Packaged smoke did not write $ReportPath (exit $($run.ExitCode))."
            }
            return $run.ExitCode
        } finally {
            $run.Dispose()
        }
    } finally {
        $env:PATH = $savedPath
        $env:FPVS_ALLOW_QT_TESTS = $savedQt
        $env:FPVS_PACKAGED_PLAYBACK_SMOKE = $savedPlayback
    }
}

function Test-InstalledInventory([string]$Phase, [string]$Version, [string]$ExpectedHash) {
    if ($ExpectedHash -and (Get-FileHash -LiteralPath $manifest).Hash -ne $ExpectedHash) {
        throw "$Phase manifest differs from the expected ownership inventory."
    }
    $header = @(Get-Content -LiteralPath $manifest -TotalCount 3)
    if ($header.Count -ne 3 -or $header[2] -cne "version=$Version") {
        throw "$Phase manifest does not match installed version $Version."
    }
    python $treeChecker --install-root $installRoot --expected-manifest $manifest --legacy-inventory $legacyInventory |
        Tee-Object -FilePath (Join-Path $work "$Phase-inventory.json")
    if ($LASTEXITCODE -ne 0) {
        throw "$Phase installed-file parity check failed."
    }
    Copy-Item -LiteralPath $manifest -Destination (Join-Path $work "$Phase-owned-files.txt")
}

function Test-RemovedBaselineFiles([string]$BaselinePhase, [string]$Phase) {
    # Both manifests have passed the shared parser. Check recent removals even
    # when their paths are missing from the committed legacy inventory.
    $targetPaths = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($record in (Get-Content -LiteralPath $manifest | Select-Object -Skip 3)) {
        $null = $targetPaths.Add(($record -split '\|', 2)[0])
    }
    $baselineManifest = Join-Path $work "$BaselinePhase-owned-files.txt"
    $remaining = @(
        foreach ($record in (Get-Content -LiteralPath $baselineManifest | Select-Object -Skip 3)) {
            $relative = ($record -split '\|', 2)[0]
            if (-not $targetPaths.Contains($relative) -and
                (Test-Path -LiteralPath (Join-Path $installRoot $relative) -PathType Leaf)) {
                $relative
            }
        }
    )
    if ($remaining.Count -ne 0) {
        throw "$Phase retained obsolete baseline files: $($remaining -join ', ')."
    }
}

function Test-HostedOpenGlVersionLimit($Playback) {
    # PsychoPy 2026.1.1's Pyglet backend throws this exact text for driver OpenGL below 2.
    $reportedError = 'RuntimeError: OpenGL version 2.0 or higher is required! Please update your ' +
        'graphics drivers or use a different backend.'
    return (
        $Playback.status -ceq 'failed' -and
        $Playback.stage -ceq 'open presentation window' -and
        $Playback.error -ceq $reportedError -and
        [string]::IsNullOrEmpty($Playback.cleanup_error) -and
        $null -eq $Playback.completed_frames -and
        ($Playback.planned_frames -is [long] -or $Playback.planned_frames -is [int]) -and
        $Playback.planned_frames -eq 50 -and
        $Playback.fullscreen -is [bool] -and $Playback.fullscreen -and
        $Playback.experiment_test_mode -is [bool] -and $Playback.experiment_test_mode
    )
}

function Test-Target([string]$Phase, [string]$BaselinePhase) {
    Test-InstalledInventory $Phase $receipt.target_version $receipt.target_inventory_sha256
    if ($BaselinePhase) {
        Test-RemovedBaselineFiles $BaselinePhase $Phase
    }
    if (Test-Path -LiteralPath $patchMarker) {
        throw "$Phase retained a patch transaction marker."
    }

    $studioReport = Join-Path $work "$Phase-studio-smoke.json"
    $playbackEnabled = $Phase -ceq 'fresh' -and $supportsPlaybackSmoke
    $studioExit = Invoke-NativeSmoke $app '--packaged-smoke-output' $studioReport 180000 `
        -Playback:$playbackEnabled
    $smoke = Get-Content -LiteralPath $studioReport -Raw | ConvertFrom-Json
    if ($smoke.app_version -cne $receipt.target_version -or $smoke.metadata_version -cne $receipt.target_version -or
        $smoke.frozen -ne $true -or $smoke.runtime_dependency_report.ok -ne $true -or
        $smoke.settings_layout.ok -ne $true) {
        throw "$Phase installed Studio failed the frozen runtime checks."
    }
    if ($studioExit -ne 0 -or $smoke.ok -ne $true) {
        # Accept only the hosted desktop cap from the 3.1.2 native check.
        $limited = @($smoke.online_workflows.states | Where-Object { -not $_.ok })
        $otherFailures = @($smoke.PSObject.Properties | Where-Object {
            $_.Name -ne 'ok' -and $_.Value -is [bool] -and -not $_.Value
        })
        if ($studioExit -ne 1 -or $smoke.ok -ne $false -or $otherFailures.Count -ne 0 -or
            $limited.Count -ne 1 -or $limited[0].dialog -ne 'experiment_library_dialog' -or
            $limited[0].state -ne 'view-only' -or
            ($limited[0].layout_issues -join ';') -ne 'Requested (1040, 760); rendered (1028, 749)' -or
            @($limited[0].checks.PSObject.Properties | Where-Object { $_.Value -ne $true }).Count -ne 0) {
            throw "$Phase installed Studio has an unexpected smoke failure (exit $studioExit)."
        }
        Write-Output "$Phase installed Studio runtime passed with the hosted Library size cap (1028 x 749)."
    }
    if ($playbackEnabled) {
        $playback = $smoke.packaged_playback
        if ($null -eq $playback) { throw 'Fresh setup did not report the fullscreen Test Mode probe.' }
        $playback | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $work 'fresh-playback-smoke.json')
        if ($playback.status -ceq 'host_graphics_unavailable' -or
            (Test-HostedOpenGlVersionLimit $playback)) {
            Write-Warning "Hosted fullscreen playback remains unverified. $($playback.error)"
        } elseif ($playback.status -cne 'passed') {
            throw "Fresh fullscreen playback failed at $($playback.stage). $($playback.error) $($playback.cleanup_error)"
        } elseif ($playback.fullscreen -ne $true -or $playback.experiment_test_mode -ne $true -or
            $playback.aborted -ne $false -or $playback.planned_frames -le 0 -or
            $playback.completed_frames -ne $playback.planned_frames) {
            throw 'Fresh fullscreen Test Mode did not complete every compiled frame.'
        }
    }

    $updaterReport = Join-Path $work "$Phase-updater-smoke.json"
    $updaterExit = Invoke-NativeSmoke $updater '--gui-smoke' $updaterReport 30000
    $updaterSmoke = Get-Content -LiteralPath $updaterReport -Raw | ConvertFrom-Json
    if ($updaterExit -ne 0 -or $updaterSmoke.passed -ne $true -or
        $updaterSmoke.network -ne $false -or $updaterSmoke.installer -ne $false -or
        $updaterSmoke.standalone_repair -ne $true -or $updaterSmoke.repair_after_failure -ne $true) {
        throw "$Phase installed updater native smoke failed (exit $updaterExit)."
    }
}

function Invoke-Uninstall([string]$Phase, [string]$KeepFile) {
    $uninstallers = @(Get-ChildItem -LiteralPath $installRoot -File -Filter 'unins*.exe')
    if ($uninstallers.Count -ne 1) {
        throw "$Phase expected one Studio uninstaller."
    }
    $log = Join-Path $work "$Phase-uninstall.log"
    $arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/LOG="' + $log + '"'))
    Invoke-InstallerProcess $uninstallers[0].FullName $arguments "$Phase uninstall"
    if (Test-Path -LiteralPath $installRoot) {
        $remaining = @(Get-ChildItem -LiteralPath $installRoot -Force -Recurse -File |
            Where-Object { $_.FullName -ne $KeepFile })
        if ($remaining.Count -ne 0) {
            throw "$Phase left installed files: $($remaining.FullName -join ', ')."
        }
    }
}

function Test-Preservation([string]$Phase, [string[]]$Paths, [string[]]$ExpectedHashes) {
    if ((Get-ItemPropertyValue -LiteralPath $settingsKey -Name 'ReleaseQaKeep') -ne 'keep settings') {
        throw "$Phase modified the settings sentinel."
    }
    $actualHashes = @(Get-FileHash -LiteralPath $Paths | Select-Object -ExpandProperty Hash)
    if (($actualHashes -join ',') -ne ($ExpectedHashes -join ',')) {
        throw "$Phase modified a file sentinel."
    }
}

function Test-Upgrade(
    [string]$Executable,
    [string]$Phase,
    [string]$BaselineInstaller,
    [string]$BaselineVersion,
    [string]$BaselineInventoryHash
) {
    $baselinePhase = "$Phase-baseline"
    Invoke-Setup $BaselineInstaller $baselinePhase
    Test-InstalledInventory $baselinePhase $BaselineVersion $BaselineInventoryHash
    Set-Content -LiteralPath $userSentinel -Value 'keep unrelated files'
    $paths = @($userSentinel) + $projectSentinels
    $hashes = @((Get-FileHash -LiteralPath $userSentinel).Hash) + $projectHashes

    Invoke-Setup $Executable $Phase
    Test-Target $Phase $baselinePhase
    Test-Preservation $Phase $paths $hashes
    Invoke-Uninstall $Phase $userSentinel
    Test-Preservation "$Phase uninstall" $paths $hashes
    Remove-Item -LiteralPath $userSentinel
}

$projectSentinels = @(
    foreach ($folder in @('.fpvs-studio\templates', 'runs', 'logs')) {
        $directory = Join-Path $work "synthetic-project\$folder"
        $null = New-Item -ItemType Directory -Path $directory -Force
        $sentinel = Join-Path $directory 'keep.txt'
        Set-Content -LiteralPath $sentinel -Value 'keep project data'
        $sentinel
    }
)
$projectHashes = @(Get-FileHash -LiteralPath $projectSentinels | Select-Object -ExpandProperty Hash)
$null = New-Item -Path 'HKCU:\Software\FPVS Studio' -Force
$null = New-Item -Path $settingsKey -Force
$null = New-ItemProperty -LiteralPath $settingsKey -Name 'ReleaseQaKeep' -Value 'keep settings'

Test-Upgrade -Executable $receipt.target_installer -Phase 'upgrade' `
    -BaselineInstaller $receipt.baseline_installer -BaselineVersion $receipt.baseline_version `
    -BaselineInventoryHash $fullBaselineInventoryHash
Invoke-Setup $receipt.target_installer 'fresh'
Test-Target 'fresh'
Invoke-Uninstall 'fresh' ''
Test-Preservation 'fresh uninstall' $projectSentinels $projectHashes
foreach ($patch in $receipt.patches) {
    Test-Upgrade -Executable $patch.patch_installer -Phase "patch-upgrade-from-$($patch.baseline_version)" `
        -BaselineInstaller $patch.baseline_installer -BaselineVersion $patch.baseline_version `
        -BaselineInventoryHash $patch.baseline_inventory_sha256
}
