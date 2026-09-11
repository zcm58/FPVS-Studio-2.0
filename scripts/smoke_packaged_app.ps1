param(
    [string]$ExePath,
    [switch]$AllowVisibleGui,
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"

if (-not $AllowVisibleGui) {
    throw "Packaged GUI verification requires user approval for a visible session. Pass -AllowVisibleGui after approval."
}
if ($env:QT_QPA_PLATFORM -in @("offscreen", "minimal")) {
    throw "Packaged GUI verification requires the native visible Qt platform."
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $ExePath) {
    $ExePath = Join-Path $RepoRoot "dist\FPVS Studio\FPVS Studio.exe"
}
$ReportDir = Join-Path $RepoRoot ".tmp"
$ReportPath = Join-Path $ReportDir "packaged-smoke-report.json"

if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Packaged executable was not found: $ExePath"
}

New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
if (Test-Path -LiteralPath $ReportPath) {
    Remove-Item -LiteralPath $ReportPath -Force
}

$previousQtOptIn = $env:FPVS_ALLOW_QT_TESTS
try {
    $env:FPVS_ALLOW_QT_TESTS = "1"
    $process = Start-Process -FilePath $ExePath -ArgumentList @(
        "--packaged-smoke-output",
        ('"' + $ReportPath + '"')
    ) -PassThru
}
finally {
    $env:FPVS_ALLOW_QT_TESTS = $previousQtOptIn
}

if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    Stop-Process -Id $process.Id -Force
    throw "Packaged app smoke check timed out after $TimeoutSeconds seconds."
}
if ($process.ExitCode -ne 0) {
    if (Test-Path -LiteralPath $ReportPath) {
        Get-Content -Path $ReportPath
    }
    throw "Packaged app smoke check failed with exit code $($process.ExitCode)."
}
if (-not (Test-Path -LiteralPath $ReportPath)) {
    throw "Packaged app smoke check did not write a report: $ReportPath"
}

Get-Content -Path $ReportPath
