; Meet Lessons — Inno Setup installer script
; Docs: https://jrsoftware.org/ishelp/
;
; Before compiling:
;   1. Update TESSERACT_INSTALLER below to match the exact filename you downloaded.
;   2. Ensure dist\MeetLessons.exe exists (run PyInstaller first — see BUILD.md Step 3).
;   3. Ensure the Tesseract installer .exe is in this folder (desktop/installer/).

#define TESSERACT_INSTALLER "tesseract-ocr-w64-setup-5.5.0.20241111.exe"
#define APP_VERSION "1.0.0"

[Setup]
AppName=Meet Lessons
AppVersion={#APP_VERSION}
AppPublisher=Meet Lessons
AppPublisherURL=https://meetlessons.onrender.com
DefaultDirName={autopf}\MeetLessons
DefaultGroupName=Meet Lessons
OutputDir=..\dist
OutputBaseFilename=MeetLessonsInstaller
SetupIconFile=..\assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\MeetLessons.exe
; Require Windows 10 or later
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: checked

[Files]
; Main app executable (built by PyInstaller)
Source: "..\dist\MeetLessons.exe"; DestDir: "{app}"; Flags: ignoreversion

; .env.example — user copies this to .env to configure the backend URL
Source: "..\.env.example"; DestDir: "{app}"; Flags: ignoreversion; DestName: ".env.example"

; Tesseract OCR installer — bundled, installed silently, deleted after install
Source: "{#TESSERACT_INSTALLER}"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\Meet Lessons"; Filename: "{app}\MeetLessons.exe"; IconFilename: "{app}\MeetLessons.exe"
Name: "{group}\Uninstall Meet Lessons"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Meet Lessons"; Filename: "{app}\MeetLessons.exe"; Tasks: desktopicon

[Run]
; Install Tesseract silently (/S = silent, /D sets install dir to default)
Filename: "{tmp}\{#TESSERACT_INSTALLER}"; Parameters: "/S"; StatusMsg: "Installing Tesseract OCR (required for screenshot capture)..."; Flags: waitprogress

; Optionally launch the app after install
Filename: "{app}\MeetLessons.exe"; Description: "Launch Meet Lessons now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Tesseract has its own entry in Add/Remove Programs — nothing extra needed here

