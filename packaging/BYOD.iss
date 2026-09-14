#define AppVersion "0.1.0"
#define AppSource "..\dist\BYOD"

[Setup]
AppId={{E476C263-41A2-49D8-A218-172B50D06B7C}
AppName=BYOD
AppVersion={#AppVersion}
AppPublisher=BYOD
AppComments=Bring Your Own Documents
DefaultDirName={localappdata}\Programs\BYOD
DefaultGroupName=BYOD
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
OutputDir=..\dist\installers
OutputBaseFilename=BYOD-Setup-{#AppVersion}-x64
SetupIconFile=byod.ico
UninstallDisplayIcon={app}\BYOD.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
SetupLogging=no
UninstallDisplayName=BYOD

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\.tools\MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\BYOD"; Filename: "{app}\BYOD.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\BYOD"; Filename: "{app}\BYOD.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\BYOD.exe"; Description: "Open BYOD"; Flags: nowait postinstall skipifsilent

[Code]
function WebView2Installed: Boolean;
var
  Version: String;
  Key: String;
begin
  Key := 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result := (RegQueryStringValue(HKLM32, Key, 'pv', Version) and
    (Version <> '') and (Version <> '0.0.0.0')) or
    (RegQueryStringValue(HKCU, Key, 'pv', Version) and
    (Version <> '') and (Version <> '0.0.0.0'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExitCode: Integer;
begin
  Result := '';
  if not WebView2Installed then
  begin
    ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
    if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'),
      '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
      Result := 'Could not start WebView2 setup. Check your internet connection and retry.'
    else if not WebView2Installed then
      Result := 'WebView2 could not be installed. Check your internet connection and retry setup.';
  end;
end;
