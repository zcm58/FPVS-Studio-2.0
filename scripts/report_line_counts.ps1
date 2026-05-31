param(
    [int]$Threshold = 500,
    [int]$Top = 25,
    [switch]$All,
    [switch]$IncludeUntracked
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "script_helpers.ps1")

$TextExtensions = @(
    ".bat",
    ".cfg",
    ".cmd",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".iss",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".spec",
    ".toml",
    ".ts",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml"
)

Push-Location $RepoRoot
try {
    $files = @(Invoke-NativeOutputChecked -File "git" -Arguments @("ls-files"))
    if ($IncludeUntracked) {
        $files += @(Invoke-NativeOutputChecked -File "git" -Arguments @(
            "ls-files",
            "--others",
            "--exclude-standard"
        ))
    }

    $rows = foreach ($file in $files) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            continue
        }
        $extension = [System.IO.Path]::GetExtension($file).ToLowerInvariant()
        if ($TextExtensions -notcontains $extension) {
            continue
        }
        try {
            $lineCount = (
                Get-Content -LiteralPath $file -ErrorAction Stop |
                    Measure-Object -Line
            ).Lines
        }
        catch {
            continue
        }
        if ($All -or $lineCount -ge $Threshold) {
            [PSCustomObject]@{
                Lines = $lineCount
                Path = $file
            }
        }
    }

    $sortedRows = @($rows | Sort-Object Lines -Descending | Select-Object -First $Top)
    if ($sortedRows.Count -eq 0) {
        Write-Output "No files at or above $Threshold lines."
        return
    }

    $sortedRows | Format-Table -AutoSize
}
finally {
    Pop-Location
}
