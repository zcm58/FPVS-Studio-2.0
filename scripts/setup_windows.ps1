$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'script_helpers.ps1')

function Test-StudioPython {
    param([string]$Python, [switch]$VirtualEnvironment)

    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { return $false }
    $probe = "import sys, sysconfig; valid = sys.version_info[:2] == (3, 10) and sysconfig.get_platform() == 'win-amd64'"
    if ($VirtualEnvironment) {
        $probe += '; valid = valid and sys.prefix != sys.base_prefix'
    }
    # A broken venv can write an error to stderr before Python starts.
    $ErrorActionPreference = 'Continue'
    & $Python -I -c "$probe; sys.exit(not valid)" 2>$null
    return $LASTEXITCODE -eq 0
}

function Install-ManagedPython {
    param([string]$ToolsRoot)

    $version = '0.13.7'
    $url = "https://github.com/astral-sh/uv/releases/download/$version/uv-x86_64-pc-windows-msvc.zip"
    $sha256 = '0cdc5b38fe5a8168ed6a25814f5ba43c21d313dd3187314fccb37b7cec46e021'
    $temp = Join-Path ([IO.Path]::GetTempPath()) ('fpvs-uv-' + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $temp | Out-Null
    $archive = Join-Path $temp 'uv.zip'
    $uv = Join-Path $temp 'uv.exe'
    $previousInstallDir = $env:UV_PYTHON_INSTALL_DIR
    $ProgressPreference = 'SilentlyContinue'
    try {
        Write-Host 'Downloading the Python installer...'
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $archive
        $stream = [IO.File]::OpenRead($archive)
        $hasher = [Security.Cryptography.SHA256]::Create()
        try {
            $hash = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '')
            if ($hash -ne $sha256) { throw 'The Python installer checksum did not match.' }
        }
        finally {
            $hasher.Dispose()
            $stream.Dispose()
        }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [IO.Compression.ZipFile]::OpenRead($archive)
        try {
            [IO.Compression.ZipFileExtensions]::ExtractToFile($zip.GetEntry('uv.exe'), $uv)
        }
        finally {
            $zip.Dispose()
        }

        Write-Host 'Preparing checkout-local Python 3.10...'
        $env:UV_PYTHON_INSTALL_DIR = $ToolsRoot
        Invoke-NativeChecked -File $uv -Arguments @(
            '--no-config', 'python', 'install', '--no-bin', '3.10'
        ) | Out-Host
        return Invoke-NativeOutputChecked -File $uv -Arguments @(
            '--no-config', 'python', 'find', '--managed-python', '--system', '3.10'
        )
    }
    finally {
        $env:UV_PYTHON_INSTALL_DIR = $previousInstallDir
        foreach ($path in @($uv, $archive, $temp)) {
            if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
        }
    }
}

function Get-StudioPython {
    param([string]$ToolsRoot)

    $preferred = Join-Path $RepoRoot '.venv3.10'
    $fallback = Join-Path $RepoRoot '.venv'
    foreach ($folder in @($preferred, $fallback)) {
        $item = Get-Item -LiteralPath $folder -Force -ErrorAction SilentlyContinue
        if ($null -eq $item) { continue }
        $python = Join-Path $folder 'Scripts\python.exe'
        $activate = Join-Path $folder 'Scripts\Activate.ps1'
        if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -and
            (Test-StudioPython -Python $python -VirtualEnvironment) -and
            (Test-Path -LiteralPath $activate -PathType Leaf)) {
            return $python
        }
        if ($folder -eq $preferred) {
            throw "The environment at $preferred is incomplete or incompatible. Rename that folder and rerun Setup Windows.cmd."
        }
    }

    $basePython = $null
    $launcher = Get-Command 'py.exe' -CommandType Application -ErrorAction SilentlyContinue
    if ($launcher) {
        # PYLAUNCHER_ALLOW_INSTALL can trigger a Store install on older launchers.
        $allowInstall = $env:PYLAUNCHER_ALLOW_INSTALL
        $env:PYLAUNCHER_ALLOW_INSTALL = $null
        try {
            $candidate = & {
                $ErrorActionPreference = 'Continue'
                & $launcher.Source -3.10-64 -I -c 'import sys; sys.stdout.write(sys.executable)' 2>$null
            }
            if ($candidate -and (Test-StudioPython -Python $candidate)) {
                $basePython = $candidate
            }
        }
        finally {
            $env:PYLAUNCHER_ALLOW_INSTALL = $allowInstall
        }
    }
    if (-not $basePython) { $basePython = Install-ManagedPython -ToolsRoot $ToolsRoot }
    if (-not (Test-StudioPython -Python $basePython)) { throw '64-bit Python 3.10 is required.' }

    Write-Host 'Creating .venv3.10...'
    Invoke-NativeChecked -File $basePython -Arguments @('-I', '-m', 'venv', $preferred) | Out-Host
    return Join-Path $preferred 'Scripts\python.exe'
}

$setupLock = $null
try {
    Set-Location -LiteralPath $RepoRoot
    if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'X64') {
        throw 'Setup Windows.cmd requires 64-bit x86 Windows.'
    }
    $requirements = Join-Path $RepoRoot 'requirements.txt'
    if (-not (Test-Path -LiteralPath $requirements -PathType Leaf) -or
        -not (Test-Path -LiteralPath 'src/fpvs_studio/app/main.py' -PathType Leaf)) {
        throw 'Extract or clone the full FPVS Studio repository before running setup.'
    }
    $toolsRoot = Join-Path $RepoRoot '.python310'
    if ((Get-Item -LiteralPath $toolsRoot -Force -ErrorAction SilentlyContinue).Attributes -band
        [IO.FileAttributes]::ReparsePoint) {
        throw "The Python tools directory must be inside the checkout: $toolsRoot"
    }
    New-Item -ItemType Directory -Path $toolsRoot -Force | Out-Null
    try {
        $setupLock = [IO.File]::Open((Join-Path $toolsRoot 'setup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    }
    catch [IO.IOException] {
        throw "Could not lock $toolsRoot. If setup is already running, wait for it to finish."
    }

    $python = Get-StudioPython -ToolsRoot $toolsRoot
    if (-not (Test-StudioPython -Python $python -VirtualEnvironment)) {
        throw "Setup requires a 64-bit Python 3.10 virtual environment: $python"
    }
    Write-Host "Installing Studio requirements with $python..."
    Invoke-NativeChecked -File $python -Arguments @(
        '-I', '-m', 'pip', '--require-virtualenv', 'install', '--upgrade', 'pip>=26.2,<27'
    )
    Invoke-NativeChecked -File $python -Arguments @(
        '-I', '-m', 'pip', '--require-virtualenv', 'install', '--requirement', $requirements
    )
    Invoke-NativeChecked -File $python -Arguments @('-I', '-m', 'pip', 'check')
    Invoke-NativeChecked -File $python -Arguments @(
        '-I', '-c', "from fpvs_studio.app.main import main; from importlib.metadata import version; version('psychopy')"
    )
    . (Join-Path (Split-Path -Parent $python) 'Activate.ps1')
    Write-Host 'Python setup complete. The Python 3.10 environment is active in this window.'
    Write-Host 'Run fpvs-studio here to open Studio.'

    if (Get-Process -Name 'pycharm*' -ErrorAction SilentlyContinue) {
        Write-Warning 'Close PyCharm and rerun Setup Windows.cmd to finish configuring its interpreter.'
    }
    else {
        Invoke-NativeChecked -File $python -Arguments @(
            '-I', (Join-Path $PSScriptRoot 'windows_pycharm.py')
        )
    }
}
catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'Resolve the error above, then double-click Setup Windows.cmd again.'
    throw
}
finally {
    if ($setupLock) { $setupLock.Dispose() }
}
