"""Windows observation script for Recorder-owned, growing raw BDF output.

The caller bounds this subprocess with a timeout. The script neither controls
Recorder nor reads EEG samples. Restart Manager is used only to query which
process has a candidate file open; its shutdown and restart APIs are not bound.
"""

from __future__ import annotations

POWER_SHELL_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$snapshot = [ordered]@{
    state = 'unavailable'; process_id = $null; version = $null
    raw_folder = $null; raw_prefix = $null
}

function Get-RecorderState {
    $sessionId = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
    $recorders = @([System.Diagnostics.Process]::GetProcessesByName('UnicornRecorder') |
        Where-Object { $_.SessionId -eq $sessionId })
    if ($recorders.Count -eq 0) { return 'not_running' }
    if ($recorders.Count -ne 1) { return 'ambiguous' }
    $recorder = $recorders[0]
    $recorderId = $recorder.Id
    $startTime = $recorder.StartTime.ToUniversalTime().ToFileTimeUtc()
    $snapshot.process_id = $recorderId
    $version = $recorder.MainModule.FileVersionInfo
    $snapshot.version = '{0}.{1}.{2}.{3}' -f $version.FileMajorPart,
        $version.FileMinorPart, $version.FileBuildPart, $version.FilePrivatePart
    # Configuration indices below are specific to this inspected vendor build.
    if ($snapshot.version -ne '1.24.2.2760') { return 'unavailable' }

    $configPath = Join-Path ([Environment]::GetFolderPath('ApplicationData')) `
        'gtec\Unicorn Suite\Hybrid Black\Unicorn Recorder\UnicornRecorderConfiguration.json'
    $xmlSettings = [System.Xml.XmlReaderSettings]::new()
    $xmlSettings.DtdProcessing = [System.Xml.DtdProcessing]::Prohibit
    $xmlSettings.XmlResolver = $null
    $xmlSettings.MaxCharactersInDocument = 1048576
    # Recorder writes an XML Unicode declaration into a UTF-8 text file. Match
    # its text-reader semantics rather than trusting that declaration as bytes.
    $configInfo = [System.IO.FileInfo]::new($configPath)
    if (-not $configInfo.Exists -or $configInfo.Length -gt 2097152) {
        return 'unavailable'
    }
    $textReader = [System.IO.StreamReader]::new($configPath, $true)
    try {
        $reader = [System.Xml.XmlReader]::Create($textReader, $xmlSettings)
        try {
            $configuration = [System.Xml.XmlDocument]::new()
            $configuration.XmlResolver = $null
            $configuration.Load($reader)
        } finally { $reader.Dispose() }
    } finally { $textReader.Dispose() }
    $loggers = $configuration.SelectNodes(
        '/RecorderConfiguration/BDFLoggingConfigurations/BDFLoggingConfiguration')
    if ($loggers.Count -ne 2) { return 'unavailable' }
    # Index 0 is processed output; index 1 is the raw-data logger in 1.24.02.
    $rawLogger = $loggers[1]
    $folder = [string]$rawLogger.Filepath
    $prefix = [string]$rawLogger.Filename
    # Optional diagnostics only; never use them as evidence of live configuration.
    if ($folder.Length -le 2048) { $snapshot.raw_folder = $folder }
    if ($prefix.Length -le 255) { $snapshot.raw_prefix = $prefix }
    if ($rawLogger.Enabled -ne 'true') { return 'not_configured' }
    if ([string]::IsNullOrWhiteSpace($folder) -or
        [string]::IsNullOrWhiteSpace($prefix) -or
        $prefix.IndexOfAny([System.IO.Path]::GetInvalidFileNameChars()) -ge 0 -or
        -not [System.IO.Path]::IsPathRooted($folder)) { return 'not_configured' }
    $folder = [System.IO.Path]::GetFullPath($folder)
    # Never contact network destinations while checking local Recorder state.
    if ($folder.StartsWith('\\', [StringComparison]::Ordinal)) { return 'unavailable' }
    $drive = [System.IO.DriveInfo]::new([System.IO.Path]::GetPathRoot($folder))
    if ($drive.DriveType -eq [System.IO.DriveType]::Network) { return 'unavailable' }
    $directory = [System.IO.DirectoryInfo]::new($folder)
    if (-not $directory.Exists) { return 'not_recording' }
    $ancestor = $directory
    while ($null -ne $ancestor) {
        if (($ancestor.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            return 'unavailable'
        }
        $ancestor = $ancestor.Parent
    }
    $files = [System.Collections.Generic.List[System.IO.FileInfo]]::new()
    $enumerated = 0
    foreach ($name in [System.IO.Directory]::EnumerateFiles($folder)) {
        $enumerated++
        if ($enumerated -gt 1024) { return 'unavailable' }
        $leaf = [System.IO.Path]::GetFileName($name)
        if ($leaf.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -and
            [System.IO.Path]::GetExtension($leaf).Equals(
                '.bdf', [StringComparison]::OrdinalIgnoreCase)) {
            $file = [System.IO.FileInfo]::new($name)
            if (($file.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0) {
                $files.Add($file)
            }
        }
    }
    $candidates = @($files | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 5)
    if ($candidates.Count -eq 0) { return 'not_recording' }

    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class FpvsRecorderFileOwner
{
    [StructLayout(LayoutKind.Sequential)]
    private struct UniqueProcess
    {
        public uint Id;
        public System.Runtime.InteropServices.ComTypes.FILETIME StartTime;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct ProcessInfo
    {
        public UniqueProcess Process;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)]
        public string ApplicationName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)]
        public string ServiceName;
        public uint ApplicationType;
        public uint ApplicationStatus;
        public uint SessionId;
        [MarshalAs(UnmanagedType.Bool)]
        public bool Restartable;
    }

    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    private static extern uint RmStartSession(out uint session, uint flags, StringBuilder key);
    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    private static extern uint RmRegisterResources(uint session, uint fileCount,
        [MarshalAs(UnmanagedType.LPArray, ArraySubType = UnmanagedType.LPWStr)] string[] files,
        uint processCount, IntPtr processes, uint serviceCount, IntPtr services);
    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    private static extern uint RmGetList(uint session, out uint needed, ref uint count,
        [In, Out] ProcessInfo[] processes, ref uint reasons);
    [DllImport("rstrtmgr.dll")]
    private static extern uint RmEndSession(uint session);

    public static bool IsOpenBy(string path, uint processId, long startTime)
    {
        uint session;
        uint result = RmStartSession(out session, 0, new StringBuilder(33));
        if (result != 0) throw new InvalidOperationException("File-owner query unavailable.");
        try
        {
            result = RmRegisterResources(session, 1, new[] { path }, 0, IntPtr.Zero,
                0, IntPtr.Zero);
            if (result != 0) throw new InvalidOperationException("File-owner query unavailable.");
            uint needed, count = 0, reasons = 0;
            result = RmGetList(session, out needed, ref count, null, ref reasons);
            if (result == 0 && needed == 0) return false;
            for (int attempt = 0; attempt < 3; attempt++)
            {
                if (result != 234 || needed == 0 || needed > 64)
                    throw new InvalidOperationException("File-owner query unavailable.");
                count = needed;
                ProcessInfo[] owners = new ProcessInfo[count];
                result = RmGetList(session, out needed, ref count, owners, ref reasons);
                if (result == 234) continue;
                if (result != 0)
                    throw new InvalidOperationException("File-owner query unavailable.");
                for (int index = 0; index < count; index++)
                {
                    UniqueProcess owner = owners[index].Process;
                    ulong observedStart = ((ulong)(uint)owner.StartTime.dwHighDateTime << 32)
                        | (uint)owner.StartTime.dwLowDateTime;
                    if (owner.Id == processId && observedStart == (ulong)startTime) return true;
                }
                return false;
            }
            throw new InvalidOperationException("File-owner query changed during inspection.");
        }
        finally { RmEndSession(session); }
    }
}
'@
    $owned = @($candidates | Where-Object {
        [FpvsRecorderFileOwner]::IsOpenBy($_.FullName, $recorderId, $startTime)
    })
    if ($owned.Count -eq 0) { return 'not_recording' }
    if ($owned.Count -ne 1) { return 'unavailable' }
    $activeFile = $owned[0]
    $activeFile.Refresh()
    $creationTime = $activeFile.CreationTimeUtc
    $previousLength = $activeFile.Length
    # Require fresh growth twice; one final buffered flush does not establish readiness.
    for ($observation = 0; $observation -lt 2; $observation++) {
        Start-Sleep -Milliseconds 1000
        $activeFile.Refresh()
        if (-not $activeFile.Exists -or $activeFile.CreationTimeUtc -ne $creationTime) {
            return 'not_recording'
        }
        if (-not [FpvsRecorderFileOwner]::IsOpenBy(
            $activeFile.FullName, $recorderId, $startTime)) { return 'not_recording' }
        # An open file with no fresh writes does not identify the cause. In
        # particular it cannot prove the headset is disconnected or switched off.
        if ($activeFile.Length -le $previousLength) { return 'not_writing' }
        $previousLength = $activeFile.Length
    }
    $remaining = @([System.Diagnostics.Process]::GetProcessesByName('UnicornRecorder') |
        Where-Object { $_.SessionId -eq $sessionId })
    if ($remaining.Count -eq 0) { return 'not_running' }
    if ($remaining.Count -ne 1) { return 'ambiguous' }
    if ($remaining[0].Id -ne $recorderId -or
        $remaining[0].StartTime.ToUniversalTime().ToFileTimeUtc() -ne $startTime) {
        return 'unavailable'
    }
    return 'recording'
}

try { $snapshot.state = Get-RecorderState } catch { $snapshot.state = 'unavailable' }
$snapshot | ConvertTo-Json -Compress
"""
