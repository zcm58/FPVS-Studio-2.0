param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv3.10\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string]$File,
        [string[]]$Arguments
    )

    & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $File $($Arguments -join ' ')"
    }
}

function Remove-RepoOutput {
    param([string]$RelativePath)

    $target = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $target)) {
        return
    }

    $resolvedRepo = (Resolve-Path -LiteralPath $RepoRoot).Path
    $resolvedTarget = (Resolve-Path -LiteralPath $target).Path
    if (-not $resolvedTarget.StartsWith($resolvedRepo, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside repo: $resolvedTarget"
    }

    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
}

Push-Location $RepoRoot
try {
    $pythonVersion = & $Python -c "import sys; sys.stdout.write(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not run Python executable: $Python"
    }
    if ($pythonVersion.Trim() -ne "3.10") {
        throw "FPVS Studio packaging requires Python 3.10; found $pythonVersion at $Python"
    }

    if (-not $SkipInstall) {
        Invoke-Native -File $Python -Arguments @(
            "-m",
            "pip",
            "install",
            "-e",
            ".[engine,packaging]"
        )
    }

    Remove-RepoOutput "build\pyinstaller"
    Remove-RepoOutput "dist\FPVS Studio"

    Invoke-Native -File $Python -Arguments @(
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--workpath",
        "build\pyinstaller",
        "--distpath",
        "dist",
        "packaging\pyinstaller\fpvs_studio.spec"
    )

    $exePath = Join-Path $RepoRoot "dist\FPVS Studio\FPVS Studio.exe"
    if (-not (Test-Path -LiteralPath $exePath)) {
        throw "Expected packaged executable was not created: $exePath"
    }

    Write-Output ""
    Write-Output "FPVS Studio executable built successfully:"
    Write-Output "  $exePath"
}
finally {
    Pop-Location
}
