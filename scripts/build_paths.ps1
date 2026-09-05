# Output isolation shared by the developer build stages; never used by installed apps.

function Assert-PackagingBuildLabel {
    param([string]$BuildLabel)

    if ($BuildLabel -eq "") {
        return
    }
    if ($BuildLabel -cnotmatch '\A[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9_-])?\z') {
        throw "BuildLabel must be 1-64 ASCII letters/digits, dots, underscores or hyphens; start with a letter/digit and do not end with a dot."
    }
    if ($BuildLabel -match '\A(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|\z)' -or
        $BuildLabel -in @("build", "dist", "pyinstaller", "installer", "installer-inventory")) {
        throw "BuildLabel is a reserved Windows or packaging-output name: $BuildLabel"
    }
}

function Assert-PackagingOutputPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        [string]$TargetPath
    )

    $repoPath = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\', '/')
    $target = [System.IO.Path]::GetFullPath($TargetPath).TrimEnd('\', '/')
    $withinOutput = $false
    foreach ($outputName in @("build", "dist")) {
        $outputPrefix = (Join-Path $repoPath $outputName) + [System.IO.Path]::DirectorySeparatorChar
        if ($target.StartsWith($outputPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            $withinOutput = $true
        }
    }
    if (-not $withinOutput) {
        throw "Refusing packaging output outside a child of repo build/ or dist/: $target"
    }

    # Inspect from the drive root down, before following any existing junction/symlink.
    $ancestor = [System.IO.Path]::GetPathRoot($target)
    $parts = $target.Substring($ancestor.Length).Split(
        [char[]]@('\', '/'), [System.StringSplitOptions]::RemoveEmptyEntries
    )
    foreach ($part in $parts) {
        $ancestor = Join-Path $ancestor $part
        try {
            $item = Get-Item -LiteralPath $ancestor -Force -ErrorAction Stop
        }
        catch [System.Management.Automation.ItemNotFoundException] {
            break
        }
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            throw "Refusing packaging output through a reparse point: $ancestor"
        }
        if (-not $item.PSIsContainer) {
            throw "Expected a packaging output directory, not a file: $ancestor"
        }
    }
    return $target
}

function Get-PackagingBuildPaths {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [string]$BuildLabel
    )

    Assert-PackagingBuildLabel -BuildLabel $BuildLabel
    $buildRoot = Join-Path $RepoRoot "build"
    $distRoot = Join-Path $RepoRoot "dist"
    if ($BuildLabel) {
        $buildRoot = Join-Path $buildRoot $BuildLabel
        $distRoot = Join-Path $distRoot $BuildLabel
    }
    $paths = [pscustomobject]@{
        WorkRoot = Join-Path $buildRoot "pyinstaller"
        DistRoot = $distRoot
        BundleRoot = Join-Path $distRoot "FPVS Studio"
        InstallerRoot = Join-Path $distRoot "installer"
        InventoryRoot = Join-Path $buildRoot "installer-inventory"
    }
    foreach ($target in @($paths.WorkRoot, $paths.BundleRoot, $paths.InstallerRoot, $paths.InventoryRoot)) {
        $null = Assert-PackagingOutputPath -RepoRoot $RepoRoot -TargetPath $target
    }
    return $paths
}

function Remove-PackagingOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        [string]$TargetPath
    )

    $target = Assert-PackagingOutputPath -RepoRoot $RepoRoot -TargetPath $TargetPath
    if (-not (Test-Path -LiteralPath $target)) {
        return
    }
    # Preflight all descendants without traversing links before recursive removal.
    $directories = New-Object 'System.Collections.Generic.Stack[string]'
    $directories.Push($target)
    while ($directories.Count -gt 0) {
        $directory = $directories.Pop()
        foreach ($item in Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop) {
            if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                throw "Refusing to remove packaging output containing a reparse point: $($item.FullName)"
            }
            if ($item.PSIsContainer) {
                $directories.Push($item.FullName)
            }
        }
    }
    Remove-Item -LiteralPath $target -Recurse -Force
}
