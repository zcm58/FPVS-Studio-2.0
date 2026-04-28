$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv3.10\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

Push-Location $RepoRoot
try {
    $env:QT_QPA_PLATFORM = "offscreen"
    $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
    & $Python -m pytest `
        --disable-plugin-autoload `
        -p pytestqt.plugin `
        -p pytest_timeout `
        --basetemp=build\pytest_tmp_gui `
        --timeout=60 `
        -q `
        tests\gui
}
finally {
    Pop-Location
}
