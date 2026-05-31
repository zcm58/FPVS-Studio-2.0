$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "script_helpers.ps1")
$Python = Resolve-RepoPython -RepoRoot $RepoRoot
$TotalTimeoutSeconds = 900
if ($env:FPVS_GUI_CHECK_TIMEOUT_SECONDS) {
    $ParsedTimeout = 0
    if (
        [int]::TryParse($env:FPVS_GUI_CHECK_TIMEOUT_SECONDS, [ref] $ParsedTimeout) -and
        $ParsedTimeout -gt 0
    ) {
        $TotalTimeoutSeconds = $ParsedTimeout
    }
}

Push-Location $RepoRoot
try {
    $env:QT_QPA_PLATFORM = "offscreen"
    $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
    $PytestArgs = @(
        "-m",
        "pytest",
        "--disable-plugin-autoload",
        "-p",
        "pytestqt.plugin",
        "-p",
        "pytest_timeout",
        "--basetemp=build\pytest_tmp_gui",
        "--timeout=60",
        "-q",
        "tests\gui"
    )
    $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $StartInfo.FileName = $Python
    $StartInfo.Arguments = $PytestArgs -join " "
    $StartInfo.UseShellExecute = $false
    $Process = [System.Diagnostics.Process]::Start($StartInfo)
    $Exited = $Process.WaitForExit($TotalTimeoutSeconds * 1000)
    if (-not $Exited) {
        Write-Host "GUI pytest exceeded ${TotalTimeoutSeconds}s; terminating process tree."
        & taskkill.exe /PID $Process.Id /T /F | Out-Host
        exit 124
    }
    $Process.Refresh()
    exit $Process.ExitCode
}
finally {
    Pop-Location
}
