$RequiredPythonVersion = "3.10"

function Format-CommandLine {
    param(
        [Parameter(Mandatory = $true)]
        [string]$File,
        [string[]]$Arguments = @()
    )

    $argumentText = $Arguments -join " "
    if ([string]::IsNullOrWhiteSpace($argumentText)) {
        return $File
    }
    return "$File $argumentText"
}

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$File,
        [string[]]$Arguments = @()
    )

    & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $(Format-CommandLine -File $File -Arguments $Arguments)"
    }
}

function Invoke-NativeOutputChecked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$File,
        [string[]]$Arguments = @()
    )

    $output = @(& $File @Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $(Format-CommandLine -File $File -Arguments $Arguments)"
    }
    return $output
}

function Assert-RequiredPython {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Python
    )

    $versionOutput = Invoke-NativeOutputChecked -File $Python -Arguments @(
        "-c",
        "import sys; sys.stdout.write(f'{sys.version_info.major}.{sys.version_info.minor}')"
    )
    $pythonVersion = ($versionOutput -join "").Trim()
    if ($pythonVersion -ne $RequiredPythonVersion) {
        throw "FPVS Studio scripts require Python $RequiredPythonVersion; found $pythonVersion at $Python"
    }
    return $Python
}

function Resolve-RepoPython {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $candidatePaths = @(
        (Join-Path $RepoRoot ".venv3.10\Scripts\python.exe"),
        (Join-Path $RepoRoot ".venv\Scripts\python.exe")
    )

    foreach ($candidatePath in $candidatePaths) {
        if (Test-Path -LiteralPath $candidatePath) {
            return Assert-RequiredPython -Python $candidatePath
        }
    }

    $pythonCommand = Get-Command "python" -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw (
            "Python was not found. Create a repo-local Python $RequiredPythonVersion " +
            "environment at .venv or .venv3.10 before running this script."
        )
    }

    return Assert-RequiredPython -Python $pythonCommand.Source
}
