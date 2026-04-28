$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Targets = @(
    "build",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tmp"
)

$RepoRootPath = [System.IO.Path]::GetFullPath($RepoRoot)

foreach ($RelativeTarget in $Targets) {
    $TargetPath = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $RelativeTarget))
    if (-not $TargetPath.StartsWith($RepoRootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean path outside repository: $TargetPath"
    }
    if (Test-Path -LiteralPath $TargetPath) {
        Remove-Item -LiteralPath $TargetPath -Recurse -Force -ErrorAction Stop
        Write-Host "Removed $RelativeTarget"
    }
}
