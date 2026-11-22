[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Repository,
    [Parameter(Mandatory)][string]$Tag,
    [Parameter(Mandatory)][string]$SourceCommit,
    [Parameter(Mandatory)][string]$SetupSha256,
    [Parameter(Mandatory)][string]$UpdateSha256,
    [Parameter(Mandatory)][string]$TargetInventorySha256,
    [Parameter(Mandatory)][string]$DownloadDir,
    [Parameter(Mandatory)][string]$EvidenceDir
)

# Verify the draft before the disposable Windows job runs its installers.
$ErrorActionPreference = 'Stop'
$stableTag = '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$'
$sha256 = '^[0-9a-f]{64}$'
$maxPatchDistance = 5
if ($Repository -cnotmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' -or
    $Tag -cnotmatch $stableTag -or $SourceCommit -notmatch '^[0-9a-f]{40}$' -or
    $SetupSha256 -notmatch $sha256 -or $UpdateSha256 -notmatch $sha256 -or
    $TargetInventorySha256 -notmatch $sha256) {
    throw 'Supply a repository, a stable vX.Y.Z tag, the full source commit, and three SHA-256 digests.'
}

function Invoke-Gh([string[]]$Arguments) {
    $result = & gh @Arguments
    if ($LASTEXITCODE -ne 0) { throw "GitHub CLI failed: $($Arguments -join ' ')" }
    $result
}

function Get-ReleaseAsset($Release, [string]$Name) {
    $assets = @($Release.assets | Where-Object { $_.name -ceq $Name })
    if ($assets.Count -ne 1 -or $assets[0].state -cne 'uploaded' -or
        $assets[0].size -le 0 -or $assets[0].digest -cnotmatch '^sha256:[0-9a-f]{64}$') {
        throw "Invalid GitHub asset $Name on $($Release.tag_name)."
    }
    $assets[0]
}

function Save-ReleaseAsset($Release, $Asset) {
    $path = Join-Path $DownloadDir $Asset.name
    $null = Invoke-Gh @('release', 'download', $Release.tag_name, '--repo', $Repository,
        '--pattern', $Asset.name, '--dir', $DownloadDir)
    if ((Get-Item -LiteralPath $path).Length -ne $Asset.size -or
        (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash -ne $Asset.digest.Substring(7)) {
        throw "Downloaded asset does not match GitHub: $($Asset.name)."
    }
    $path
}

function Get-Baseline($Release) {
    if ($null -eq $Release -or $Release.immutable -ne $true) {
        throw 'The Windows baseline must be published, stable, and immutable.'
    }
    $version = $Release.tag_name.Substring(1)
    $setup = Get-ReleaseAsset $Release "FPVS-Studio-Setup-$version.exe"
    if ($setup.size -gt 4GB) { throw "Unexpected setup size for Windows baseline $version." }
    [pscustomobject]@{ version = $version; release = $Release; setup = $setup; installer = $null }
}

function Test-ChecksumSidecar($Release, $Asset) {
    $checksum = Get-ReleaseAsset $Release "$($Asset.name).sha256"
    $expected = "$($Asset.digest.Substring(7))  $($Asset.name)"
    if ($checksum.size -notin @(($expected.Length + 1), ($expected.Length + 2))) {
        throw "Unexpected checksum sidecar length: $($checksum.name)."
    }
    $path = Save-ReleaseAsset $Release $checksum
    if ((Get-Content -LiteralPath $path -Raw).TrimEnd("`r", "`n") -cne $expected) {
        throw "Checksum sidecar does not identify $($Asset.name)."
    }
}

function Assert-JsonKeys($Document, [string[]]$Keys) {
    if ($Document -isnot [System.Collections.IDictionary] -or
        (Compare-Object -ReferenceObject $Keys -DifferenceObject @($Document.Keys) -CaseSensitive)) {
        throw 'Invalid update manifest schema.'
    }
}

$draftId = (Invoke-Gh @('release', 'view', $Tag, '--repo', $Repository, '--json', 'databaseId') |
    ConvertFrom-Json).databaseId
$draft = Invoke-Gh @('api', "repos/$Repository/releases/$draftId") | ConvertFrom-Json
if ($draft.id -ne $draftId -or $draft.tag_name -cne $Tag -or
    $draft.draft -ne $true -or $draft.prerelease -ne $false) {
    throw "Expected a stable release draft for $Tag."
}
$remoteTag = git ls-remote --tags "https://github.com/$Repository.git" "refs/tags/${Tag}^{}"
if ($LASTEXITCODE -ne 0 -or (($remoteTag -split '\s+')[0] -ne $SourceCommit)) {
    throw "$Tag must be annotated and point at the exact build commit."
}

$targetVersion = $Tag.Substring(1)
$targetNumber = [version]$targetVersion
$releasePages = Invoke-Gh @('api', '--paginate', '--slurp', "repos/$Repository/releases?per_page=100") |
    ConvertFrom-Json -NoEnumerate
$publishedWindows = @($releasePages | ForEach-Object { $_ } | Where-Object {
    $_.draft -eq $false -and $_.prerelease -eq $false -and $_.published_at -and
    $_.tag_name -cmatch $stableTag -and [version]$_.tag_name.Substring(1) -lt $targetNumber -and
    ($_.assets.name -ccontains "FPVS-Studio-Setup-$($_.tag_name.Substring(1)).exe")
} | Sort-Object { [version]$_.tag_name.Substring(1) } -Descending)
$fullBaseline = Get-Baseline ($publishedWindows | Select-Object -First 1)
$baselines = [ordered]@{}
$baselines[$fullBaseline.version] = $fullBaseline

$targetSetup = Get-ReleaseAsset $draft "FPVS-Studio-Setup-$targetVersion.exe"
$updateAsset = Get-ReleaseAsset $draft "FPVS-Studio-Update-$targetVersion.json"
if ($targetSetup.digest -ne "sha256:$SetupSha256" -or $updateAsset.digest -ne "sha256:$UpdateSha256" -or
    $targetSetup.size -gt 4GB -or $updateAsset.size -gt 1MB) {
    throw 'Unexpected draft SHA-256 or asset size.'
}

$DownloadDir = (New-Item -ItemType Directory -Path $DownloadDir).FullName
$EvidenceDir = (New-Item -ItemType Directory -Path $EvidenceDir -Force).FullName
$updatePath = Save-ReleaseAsset $draft $updateAsset
$update = Get-Content -LiteralPath $updatePath -Raw | ConvertFrom-Json -AsHashtable
Assert-JsonKeys $update @('schema_version', 'target_version', 'platform', 'patches')
if ($update.schema_version -isnot [long] -or $update.schema_version -ne 1 -or
    $update.target_version -isnot [string] -or $update.target_version -cne $targetVersion -or
    $update.platform -isnot [string] -or $update.platform -cne 'windows-x64' -or
    $update.patches -isnot [array] -or $update.patches.Count -gt $maxPatchDistance) {
    throw "The update manifest must identify this Windows release and contain at most $maxPatchDistance patches."
}

$seenSources = [System.Collections.Generic.HashSet[string]]::new()
$patches = @(
    foreach ($patch in $update.patches) {
        Assert-JsonKeys $patch @('from_version', 'source_inventory_sha256', 'asset_name', 'size_bytes', 'sha256')
        $fromVersion = $patch.from_version
        if ($fromVersion -isnot [string] -or "v$fromVersion" -cnotmatch $stableTag) {
            throw 'A patch requires a stable X.Y.Z source version.'
        }
        $fromNumber = [version]$fromVersion
        $distance = $targetNumber.Build - $fromNumber.Build
        if ($fromNumber.Major -ne $targetNumber.Major -or $fromNumber.Minor -ne $targetNumber.Minor -or
            $distance -lt 1 -or $distance -gt $maxPatchDistance) {
            throw "Patch source $fromVersion must be 1 to $maxPatchDistance patch revisions behind $targetVersion within the same major and minor version."
        }
        if (-not $seenSources.Add($fromVersion)) { throw "Duplicate patch baseline $fromVersion." }
        $patchName = "FPVS-Studio-Patch-$fromVersion-to-$targetVersion.exe"
        if ($patch.asset_name -isnot [string] -or $patch.asset_name -cne $patchName -or
            $patch.source_inventory_sha256 -isnot [string] -or $patch.source_inventory_sha256 -cnotmatch $sha256 -or
            $patch.sha256 -isnot [string] -or $patch.sha256 -cnotmatch $sha256 -or
            $patch.size_bytes -isnot [long] -or $patch.size_bytes -le 0 -or $patch.size_bytes -ge $targetSetup.size) {
            throw "Patch $patchName must have valid metadata and be smaller than setup."
        }
        $patchAsset = Get-ReleaseAsset $draft $patchName
        if ($patchAsset.digest -cne "sha256:$($patch.sha256)" -or $patchAsset.size -ne $patch.size_bytes) {
            throw "The update manifest and GitHub patch asset disagree for $patchName."
        }
        if (-not $baselines.Contains($fromVersion)) {
            $matching = @($publishedWindows | Where-Object { $_.tag_name -ceq "v$fromVersion" })
            if ($matching.Count -ne 1) { throw "Expected one published stable Windows release for v$fromVersion." }
            $baselines[$fromVersion] = Get-Baseline $matching[0]
        }
        [pscustomobject]@{
            baseline = $baselines[$fromVersion]
            source_inventory_sha256 = $patch.source_inventory_sha256
            asset = $patchAsset
        }
    }
)

$payloads = @($targetSetup, $updateAsset) + @($patches | ForEach-Object { $_.asset })
if ($draft.assets.Count -ne 2 * $payloads.Count) {
    throw 'Draft assets must contain exactly the installer, update manifest, declared patches, and their checksums.'
}
foreach ($asset in $payloads) {
    Test-ChecksumSidecar $draft $asset
}
foreach ($baseline in $baselines.Values) {
    $baseline.installer = Save-ReleaseAsset $baseline.release $baseline.setup
    $null = Invoke-Gh @('release', 'verify-asset', $baseline.release.tag_name, $baseline.installer, '--repo', $Repository)
}
$targetInstaller = Save-ReleaseAsset $draft $targetSetup
$patchReceipts = @(
    foreach ($patch in $patches) {
        [ordered]@{
            baseline_version = $patch.baseline.version
            baseline_release_id = $patch.baseline.release.id
            baseline_installer = $patch.baseline.installer
            baseline_asset = $patch.baseline.setup | Select-Object id, name, size, digest
            baseline_inventory_sha256 = $patch.source_inventory_sha256
            patch_installer = Save-ReleaseAsset $draft $patch.asset
        }
    }
)

Copy-Item -LiteralPath $updatePath -Destination $EvidenceDir
[ordered]@{
    source_commit = $SourceCommit.ToLowerInvariant()
    target_release_id = $draft.id
    target_version = $targetVersion
    target_inventory_sha256 = $TargetInventorySha256.ToLowerInvariant()
    target_installer = $targetInstaller
    target_assets = @($draft.assets | Select-Object id, name, size, digest)
    baseline_version = $fullBaseline.version
    baseline_release_id = $fullBaseline.release.id
    baseline_installer = $fullBaseline.installer
    baseline_asset = $fullBaseline.setup | Select-Object id, name, size, digest
    patches = $patchReceipts
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $EvidenceDir 'release-assets.json')
Write-Output "Authenticated the $Tag draft, $($patches.Count) patches, and $($baselines.Count) published baseline installers."
