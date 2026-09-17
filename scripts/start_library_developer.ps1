param(
    [string]$LibraryRepository,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'script_helpers.ps1')
$studioPython = Resolve-RepoPython -RepoRoot $studioRoot

if ([string]::IsNullOrWhiteSpace($LibraryRepository)) {
    $LibraryRepository = Join-Path $studioRoot 'build\experiment-library-service'
}
$publisherRoot = (Resolve-Path -LiteralPath $LibraryRepository).Path
if (-not (Test-Path -LiteralPath (Join-Path $publisherRoot 'scripts\publish-catalog.py') -PathType Leaf)) {
    throw 'Choose the private FPVS-Studio-Library checkout containing scripts/publish-catalog.py.'
}

# Opt in only for this child process. Normal launches and installed builds stay unchanged.
$previousPublisherRoot = $env:FPVS_LIBRARY_PUBLISHER_REPO
$previousPythonPath = $env:PYTHONPATH
try {
    $env:FPVS_LIBRARY_PUBLISHER_REPO = $publisherRoot
    $env:PYTHONPATH = Join-Path $studioRoot 'src'
    if ($previousPythonPath) {
        $env:PYTHONPATH += [IO.Path]::PathSeparator + $previousPythonPath
    }
    $checkCode = 'from fpvs_studio.developer.library_publisher import get_publisher_config; import sys; config = get_publisher_config(); assert config is not None, "Developer publishing requires a source checkout"; sys.stdout.write(str(config.repository_root) + "\n")'
    Invoke-NativeChecked -File $studioPython -Arguments @('-c', $checkCode)
    if (-not $Check) {
        Start-Process -FilePath $studioPython -ArgumentList @('-m', 'fpvs_studio.app.main') `
            -WorkingDirectory $studioRoot -WindowStyle Hidden | Out-Null
    }
}
finally {
    $env:FPVS_LIBRARY_PUBLISHER_REPO = $previousPublisherRoot
    $env:PYTHONPATH = $previousPythonPath
}
