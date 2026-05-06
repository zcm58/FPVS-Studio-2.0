param(
    [switch]$SkipLineCounts
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv3.10\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

function Invoke-GitGrep {
    param(
        [string]$Pattern,
        [string[]]$Paths
    )

    $output = @(& git grep -n $Pattern -- @Paths 2>$null)
    if ($LASTEXITCODE -eq 1) {
        return @()
    }
    if ($LASTEXITCODE -ne 0) {
        throw "git grep failed for pattern: $Pattern"
    }
    return $output
}

function Add-Failure {
    param(
        [System.Collections.Generic.List[string]]$Failures,
        [string]$Heading,
        [string[]]$Matches
    )

    if ($Matches.Count -eq 0) {
        return
    }

    $Failures.Add($Heading)
    foreach ($match in $Matches) {
        $Failures.Add("  $match")
    }
}

Push-Location $RepoRoot
try {
    $failures = [System.Collections.Generic.List[string]]::new()

    $printMatches = Invoke-GitGrep "print(" @("src", "scripts") |
        Where-Object { $_ -notlike "scripts/check_gc.ps1:*" }
    Add-Failure $failures "Use structured logging instead of print(...) in source/scripts." $printMatches

    $customTkMatches = Invoke-GitGrep "[Cc]ustom[Tt]kinter" @("src", "tests")
    Add-Failure $failures "PySide6 is the only active GUI framework; CustomTkinter must not return." $customTkMatches

    $stylesheetMatches = Invoke-GitGrep "setStyleSheet(" @("src/fpvs_studio/gui") |
        Where-Object { $_ -match "\.py:" } |
        Where-Object {
            $_ -notlike "src/fpvs_studio/gui/components.py:*" -and
            $_ -notlike "src/fpvs_studio/gui/main_window.py:*self.menuBar().setStyleSheet(`"`")*"
        }
    Add-Failure $failures "Shared GUI styles belong in gui/components.py." @($stylesheetMatches)

    $psychopyImportMatches = @(
        Invoke-GitGrep "import psychopy" @("src/fpvs_studio")
        Invoke-GitGrep "from psychopy" @("src/fpvs_studio")
    ) | Where-Object { $_ -notlike "src/fpvs_studio/engines/*" }
    Add-Failure $failures "PsychoPy imports must stay inside src/fpvs_studio/engines/." @($psychopyImportMatches)

    $localPathMatches = Invoke-GitGrep "C:\\Users\\" @("src", "tests", "scripts")
    Add-Failure $failures "Do not commit local machine paths into source, tests, or scripts." $localPathMatches

    & $Python -m pytest -q tests\unit\test_harness_docs.py tests\unit\test_import_boundaries.py
    & (Join-Path $PSScriptRoot "check_docs_hygiene.ps1")

    if ($failures.Count -gt 0) {
        Write-Error ($failures -join [Environment]::NewLine)
    }

    if (-not $SkipLineCounts) {
        Write-Output ""
        Write-Output "Advisory line-count report:"
        & (Join-Path $PSScriptRoot "report_line_counts.ps1") -Threshold 500 -Top 25
    }

    Write-Output "Harness garbage-collection checks passed."
}
finally {
    Pop-Location
}
