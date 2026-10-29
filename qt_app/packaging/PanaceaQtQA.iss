#ifndef QtCandidateDir
  #error "Specify QtCandidateDir pointing to the SHA-256 verified QA bundle."
#endif
#ifndef QtOutputDir
  #error "Specify QtOutputDir."
#endif

[Setup]
; QA-only AppId: deliberately different from stable Panacea's AppId.
; This installer MUST NEVER upgrade, replace or remove the stable application.
AppId={{87859E85-3961-44DA-AA6A-008C0C09D8A3}
AppName=Panacea Qt QA
AppVersion=2.0.2
AppVerName=Panacea Qt QA (not a stable release)
AppPublisher=falker47
AppSupportURL=https://github.com/falker47/Panacea/issues
DefaultDirName={autopf}\PanaceaQtQA
UsePreviousAppDir=no
DisableDirPage=no
DefaultGroupName=Panacea Qt QA
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17134
OutputDir={#QtOutputDir}
OutputBaseFilename=PanaceaQtQASetup
UninstallDisplayIcon={app}\PanaceaQtCandidate.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Files]
Source: "{#QtCandidateDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Panacea Qt QA"; Filename: "{app}\PanaceaQtCandidate.exe"; WorkingDir: "{app}"
