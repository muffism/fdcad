; FDCAD Windows installer.
; Builds a one folder PyInstaller build at ..\..\dist\FDCAD into a
; self extracting x64 setup with .fdprt (and older .fdef) file associations.
; Run: iscc /DAppVersion=1.0.0 packaging\windows\fdcad.iss

#ifndef AppVersion
#define AppVersion "0.0.0"
#endif

; The notices, the source offer and the license must be in the build, beside
; FDCAD.exe, where the spec copies them (D2867). Stop here if one is missing.
#if !FileExists(AddBackslash(SourcePath) + "..\..\dist\FDCAD\THIRD_PARTY_NOTICES.txt")
  #error dist\FDCAD\THIRD_PARTY_NOTICES.txt is missing: build with packaging\fdcad.spec first
#endif
#if !FileExists(AddBackslash(SourcePath) + "..\..\dist\FDCAD\SOURCE_OFFER.md")
  #error dist\FDCAD\SOURCE_OFFER.md is missing: build with packaging\fdcad.spec first
#endif
#if !FileExists(AddBackslash(SourcePath) + "..\..\dist\FDCAD\LICENSE")
  #error dist\FDCAD\LICENSE is missing: build with packaging\fdcad.spec first
#endif

[Setup]
AppName = FDCAD
AppVerName = FDCAD {#AppVersion}
AppPublisher = Muffism
AppVersion = {#AppVersion}
AppId = {{8F3C2A71-5D4E-4B9A-9C61-2E7F0D5A3B14}
DefaultDirName = {autopf}\FDCAD
DefaultGroupName = FDCAD
DisableProgramGroupPage = yes
; The GPL is shown as information, not as terms to accept: it needs no acceptance
; to run the program (D2867).
InfoBeforeFile = ..\..\LICENSE
OutputDir = Output
OutputBaseFilename = FDCAD-{#AppVersion}-windows-x64-setup
Compression = lzma2
SolidCompression = yes
WizardStyle = modern
ArchitecturesAllowed = x64compatible
ArchitecturesInstallIn64BitMode = x64compatible
PrivilegesRequired = admin
PrivilegesRequiredOverridesAllowed = dialog
ChangesAssociations = yes
UninstallDisplayIcon = {app}\FDCAD.exe
UninstallDisplayName = FDCAD {#AppVersion}
SetupIconFile = ..\icons\fdcad.ico
; Wizard pictures made from the app icon by tools/make_installer_images.py (D588).
WizardImageFile = images\wizard_164x314.bmp,images\wizard_192x386.bmp,images\wizard_246x459.bmp,images\wizard_273x556.bmp,images\wizard_328x604.bmp,images\wizard_355x700.bmp,images\wizard_410x797.bmp
WizardSmallImageFile = images\small_55.bmp,images\small_64.bmp,images\small_69.bmp,images\small_83.bmp,images\small_92.bmp,images\small_110.bmp,images\small_138.bmp
CloseApplications = yes
AppCopyright = Copyright (C) 2026 the FDCAD contributors

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\FDCAD\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FDCAD"; Filename: "{app}\FDCAD.exe"; Comment: "Parametric part modeler"
Name: "{group}\{cm:UninstallProgram,FDCAD}"; Filename: "{uninstallexe}"
Name: "{group}\FDCAD Third Party Notices"; Filename: "{app}\THIRD_PARTY_NOTICES.txt"
Name: "{autodesktop}\FDCAD"; Filename: "{app}\FDCAD.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.fdprt"; ValueName: ""; ValueType: string; ValueData: "FDCAD.Part"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.fdef"; ValueName: ""; ValueType: string; ValueData: "FDCAD.Part"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.fdprt"; ValueName: "Content Type"; ValueType: string; ValueData: "application/vnd.fdcad.part+json"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.fdef"; ValueName: "Content Type"; ValueType: string; ValueData: "application/vnd.fdcad.part+json"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.fdprt\OpenWithProgids"; ValueName: "FDCAD.Part"; ValueType: string; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.fdef\OpenWithProgids"; ValueName: "FDCAD.Part"; ValueType: string; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\FDCAD.Part"; ValueName: ""; ValueType: string; ValueData: "FDCAD Part"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\FDCAD.Part\DefaultIcon"; ValueName: ""; ValueType: string; ValueData: """{app}\FDCAD.exe"",0"
Root: HKA; Subkey: "Software\Classes\FDCAD.Part\shell\open\command"; ValueName: ""; ValueType: string; ValueData: """{app}\FDCAD.exe"" ""%1"""
Root: HKA; Subkey: "Software\Classes\Applications\FDCAD.exe"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\FDCAD.exe\SupportedTypes"; ValueName: ".fdprt"; ValueType: string; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\FDCAD.exe\SupportedTypes"; ValueName: ".fdef"; ValueType: string; ValueData: ""

[Run]
Filename: "{app}\FDCAD.exe"; Description: "{cm:LaunchProgram,FDCAD}"; Flags: nowait postinstall skipifsilent