; Inno Setup script for Liminal Vibes.
;
; Builds a standalone Windows installer (LiminalVibesSetup.exe) that installs
; the PyInstaller-built LiminalVibes.exe with no prerequisites (no Python
; required on the target machine).
;
; Expects dist\LiminalVibes.exe to already exist (built via:
;   pyinstaller --noconfirm --clean LiminalVibes.spec
; run from the repository root).
;
; Compile with:
;   iscc installer\windows.iss
; Output is written to installer\Output\LiminalVibesSetup.exe

#define MyAppName "Liminal Vibes"
#define MyAppVersion "1.0.0"
#define MyAppExeName "LiminalVibes.exe"

[Setup]
AppId={{B6C1B3D2-6B3B-4E9A-9C9A-2C4B6D8E9A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=LiminalVibesSetup
OutputDir=Output
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
