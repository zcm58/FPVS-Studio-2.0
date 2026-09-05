#define AppName "FPVS Studio"
#ifndef AppVersion
#define AppVersion "0.0.0-dev"
#endif
#define AppPublisher "FPVS Studio"
#define AppExeName "FPVS Studio.exe"
#if VER < 0x06050000
  #error Inno Setup 6.5 or later is required for handle-bound SHA-256 cleanup.
#endif
#ifndef BundleRoot
  #define BundleRoot "..\..\dist\FPVS Studio"
#endif
#ifndef OwnedInventoryRoot
  #define OwnedInventoryRoot "..\..\build\installer-inventory"
#endif

[Setup]
AppId={{C0EAFB18-1DC5-4C77-8FDB-F6C1E7874694}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=FPVS-Studio-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile=..\..\src\fpvs_studio\assets\fpvs-studio.ico
CloseApplications=yes
UninstallLogMode=append

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#BundleRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#OwnedInventoryRoot}\current-owned-files.txt"; DestDir: "{app}"; DestName: "fpvs-owned-files-v1.txt"; Flags: ignoreversion
Source: "{#OwnedInventoryRoot}\current-owned-files.txt"; Flags: dontcopy
Source: "{#OwnedInventoryRoot}\legacy-owned-files.txt"; Flags: dontcopy

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent; Check: not RelaunchRequested
Filename: "{app}\{#AppExeName}"; Flags: nowait skipifsilent; Check: RelaunchRequested

[Code]
#include "owned_files.iss"
#include "updater_cache.iss"

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  try
    Result := OwnedPrepareUpgrade;
  except
    Result := 'Could not safely prepare the application upgrade: ' + GetExceptionMessage;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    try
      OwnedReconcileAfterSuccess;
    except
      Log('Ownership cleanup remains pending: ' + GetExceptionMessage);
    end;
  end;
end;

procedure DeinitializeSetup;
begin
  OwnedDisposeState;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then begin
    try
      OwnedRemovePendingOnUninstall;
    except
      Log('Nonfatal ownership-journal uninstall cleanup error: ' + GetExceptionMessage);
    end;
    try
      UpdateCleanupCacheOnUninstall;
    except
      Log('Nonfatal update-cache uninstall cleanup error: ' + GetExceptionMessage);
    end;
  end;
end;

function RelaunchRequested: Boolean;
begin
  Result := Pos('/RELAUNCH=1', Uppercase(GetCmdTail)) > 0;
end;
