$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

function Get-PlanStatus {
    param([string]$Path)

    $match = Select-String -LiteralPath $Path -Pattern "^Status:\s*(.+)$" -List
    if ($null -eq $match) {
        return ""
    }
    return $match.Matches[0].Groups[1].Value.Trim()
}

Push-Location $RepoRoot
try {
    $failures = [System.Collections.Generic.List[string]]::new()

    $requiredPaths = @(
        "docs\index.md",
        "docs\PLANS.md",
        "docs\exec-plans\README.md",
        "docs\exec-plans\planned",
        "docs\exec-plans\active",
        "docs\exec-plans\completed",
        "docs\exec-plans\plan-review-workflow.md",
        "docs\references\archive"
    )

    foreach ($path in $requiredPaths) {
        if (-not (Test-Path -LiteralPath $path)) {
            $failures.Add("Missing docs hygiene path: $path")
        }
    }

    $rootArchiveCandidates = @(
        Get-ChildItem -LiteralPath "docs" -File -Filter "*.md" |
            Where-Object {
                $_.Name -match "AUDIT|SCAFFOLD|INITIAL_PROMPT"
            } |
            ForEach-Object { $_.Name }
    )
    foreach ($name in $rootArchiveCandidates) {
        $failures.Add("Historical doc should live under docs\references\archive\: $name")
    }

    $activePlans = @(
        Get-ChildItem -LiteralPath "docs\exec-plans\active" -File -Filter "*.md" |
            Where-Object { $_.Name -ne "README.md" }
    )
    foreach ($plan in $activePlans) {
        $status = Get-PlanStatus $plan.FullName
        if ($status -ne "Active") {
            $failures.Add("Active plan must declare 'Status: Active': $($plan.FullName)")
        }
    }

    $plannedPlans = @(
        Get-ChildItem -LiteralPath "docs\exec-plans\planned" -File -Filter "*.md" |
            Where-Object { $_.Name -ne "README.md" }
    )
    foreach ($plan in $plannedPlans) {
        $status = Get-PlanStatus $plan.FullName
        if ($status -ne "Planned") {
            $failures.Add("Planned plan must declare 'Status: Planned': $($plan.FullName)")
        }
    }

    Write-Output "Execution plan inventory:"
    Write-Output "  Planned:  $($plannedPlans.Count)"
    Write-Output "  Active:   $($activePlans.Count)"
    Write-Output "  Completed: $((Get-ChildItem -LiteralPath "docs\exec-plans\completed" -File -Filter "*.md").Count)"
    Write-Output ""
    Write-Output "Root docs:"
    Get-ChildItem -LiteralPath "docs" -File -Filter "*.md" |
        Sort-Object Name |
        ForEach-Object { Write-Output "  $($_.Name)" }

    if ($failures.Count -gt 0) {
        Write-Error ($failures -join [Environment]::NewLine)
    }

    Write-Output ""
    Write-Output "Docs hygiene checks passed."
}
finally {
    Pop-Location
}
