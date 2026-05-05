param(
    [int]$Threshold = 500,
    [int]$Top = 25,
    [switch]$All,
    [switch]$IncludeUntracked
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $RepoRoot
try {
    $files = @(& git ls-files)
    if ($IncludeUntracked) {
        $files += @(& git ls-files --others --exclude-standard)
    }

    $rows = foreach ($file in $files) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
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
