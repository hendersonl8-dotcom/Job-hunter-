; Inno Setup script: wraps dist\JobHunter into JobHunter-Setup.exe with Start Menu + Desktop shortcuts.
#define AppName "Job Hunter"
[Setup]
AppName={#AppName}
AppVersion=1.0
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\installer
OutputBaseFilename=JobHunter-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\JobHunter.exe

[Files]
Source: "..\dist\JobHunter\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\JobHunter.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\JobHunter.exe"

[Run]
Filename: "{app}\JobHunter.exe"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent
