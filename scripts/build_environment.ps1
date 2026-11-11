# Process-local native search policy shared by the two PyInstaller build stages.

function Invoke-PackagingPyInstaller {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Python,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $previousPath = $env:Path
    try {
        if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
            $prefixOutput = Invoke-NativeOutputChecked -File $Python -Arguments @(
                "-I", "-c",
                "import json, sys; sys.stdout.write(json.dumps(dict(prefix=sys.prefix, base_prefix=sys.base_prefix)))"
            )
            $pythonEnvironment = ConvertFrom-Json -InputObject ($prefixOutput -join "")

            $system = [Environment]::SystemDirectory
            $windows = [Environment]::GetFolderPath([Environment+SpecialFolder]::Windows)
            $trustedDirectories = @(
                (Split-Path -Parent $Python), $pythonEnvironment.prefix, $pythonEnvironment.base_prefix,
                $system, $windows, (Join-Path $system "Wbem")
            )
            foreach ($directory in $trustedDirectories) {
                if (-not [IO.Path]::IsPathRooted($directory) -or $directory.Contains([IO.Path]::PathSeparator)) {
                    throw "Invalid directory for the restricted PyInstaller PATH: $directory"
                }
            }
            $env:Path = ($trustedDirectories | Select-Object -Unique) -join [IO.Path]::PathSeparator
        }

        Invoke-NativeChecked -File $Python -Arguments (@("-m", "PyInstaller") + $Arguments)
    }
    finally {
        $env:Path = $previousPath
    }
}
