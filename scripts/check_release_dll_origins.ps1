param([string]$BuildLabel)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "script_helpers.ps1")
. (Join-Path $PSScriptRoot "build_paths.ps1")
$BuildPaths = Get-PackagingBuildPaths -RepoRoot $RepoRoot -BuildLabel $BuildLabel
$Python = Resolve-RepoPython -RepoRoot $RepoRoot

Invoke-NativeChecked -File $Python -Arguments @(
    (Join-Path $PSScriptRoot "check_build_dll_origins.py"),
    "--studio-toc", $BuildPaths.StudioDllToc,
    "--updater-toc", $BuildPaths.UpdaterDllToc,
    "--installer-dir", $BuildPaths.InstallerRoot,
    "--verify-receipt", $BuildPaths.DllAuditReceipt
)
