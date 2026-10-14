#ifndef PanaceaVersion
  #error "Specify PanaceaVersion via scripts/build_installer.py."
#endif
#ifndef PanaceaExePath
  #error "Specify the verified PanaceaExePath."
#endif
#ifndef PanaceaIconPath
  #error "Specify the original PanaceaIconPath."
#endif
#ifndef PanaceaOutputDir
  #error "Specify PanaceaOutputDir."
#endif

[Setup]
; Do not change AppId in subsequent versions: upgrades and uninstall rely on it.
AppId={{B6C0FB10-27BC-4E6F-9078-40F9E8B49B2D}
AppName=Panacea
AppVersion={#PanaceaVersion}
AppVerName=Panacea {#PanaceaVersion}
AppPublisher=falker47
AppPublisherURL=https://falker47.github.io/Nexus-portfolio/
AppSupportURL=https://github.com/falker47/Panacea/issues
AppUpdatesURL=https://github.com/falker47/Panacea/releases/latest
DefaultDirName={autopf}\Panacea
DisableDirPage=yes
UsePreviousAppDir=no
DefaultGroupName=Panacea
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17134
OutputDir={#PanaceaOutputDir}
OutputBaseFilename=PanaceaSetup
SetupIconFile={#PanaceaIconPath}
UninstallDisplayIcon={app}\Panacea.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Never terminate a maintenance command to perform an upgrade.
CloseApplications=no
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#PanaceaExePath}"; DestDir: "{app}"; DestName: "Panacea.exe"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Panacea"; Filename: "{app}\Panacea.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Panacea"; Filename: "{app}\Panacea.exe"; WorkingDir: "{app}"; Tasks: desktopicon
