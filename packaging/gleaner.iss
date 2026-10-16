; Inno Setup script for Gleaner-Setup.exe. Built by packaging/build.py, which passes /DAppVersion.
; Installs per user (no admin rights needed). Uninstall keeps the user's data and Excel files.

#define AppName "Gleaner"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6B1E8C2A-4F3D-4E7A-9C51-2D8F0A7B3E64}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
SetupIconFile=gleaner.ico
UninstallDisplayIcon={app}\Gleaner.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
#ifdef Sign
; build.py passes /DSign and /Sgleaner=<signtool command> when a code signing certificate is set up.
SignTool=gleaner
SignedUninstaller=yes
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\Gleaner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\Gleaner.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Gleaner.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Gleaner.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; Update now (app/updater.py) installs silently with /RELAUNCH=1: open Gleaner again afterwards.
Filename: "{app}\Gleaner.exe"; Flags: nowait; Check: RelaunchAfterUpdate

[Code]
function RelaunchAfterUpdate(): Boolean;
begin
  Result := WizardSilent() and (ExpandConstant('{param:RELAUNCH|0}') = '1');
end;
