[Files]
Source: dist\library.zip; DestDir: {app}
Source: dist\*.dll; DestDir: {app}
Source: dist\*.pyd; DestDir: {app}
Source: dist\advene.exe; DestDir: {app}
Source: dist\w9xpopen.exe; DestDir: {app}
Source: dist\share\*; DestDir: {app}\share; Flags: recursesubdirs
Source: dist\doc\*; DestDir: {app}\doc; Flags: recursesubdirs
Source: dist\locale\*; DestDir: {app}\locale; Flags: recursesubdirs
Source: share\pixmaps\advene.ico; DestDir: {app}; DestName: advene.ico
Source: c:\gtk\etc\*; DestDir: {app}\etc; Flags: recursesubdirs
Source: examples\*v6.azp; DestDir: {app}\examples
Source: c:\gtk\lib\gtk-2.0\*; DestDir: {app}\lib\gtk-2.0; Flags: recursesubdirs
Source: c:\gtk\share\locale\fr\*; DestDir: {app}\lib\locale\fr; Flags: recursesubdirs
Source: c:\gtk\lib\pango\*; DestDir: {app}\lib\pango; Flags: recursesubdirs
Source: c:\gtk\share\themes\*; DestDir: {app}\share\themes; Flags: recursesubdirs
Source: c:\gtk\bin\libpng12.dll; DestDir: {app}
Source: c:\gtk\bin\libpangoft2-1.0-0.dll; DestDir: {app}
Source: c:\gtk\bin\libtiff3.dll; DestDir: {app}
Source: c:\gtk\bin\jpeg62.dll; DestDir: {app}
Source: c:\gtk\bin\librsvg-2-2.dll; DestDir: {app}
Source: c:\gtk\bin\libcroco-0.6-3.dll; DestDir: {app}
Source: c:\gtk\bin\libgsf-1-114.dll; DestDir: {app}
Source: c:\gtk\bin\bzip2.dll; DestDir: {app}
Source: Win32SoundPlayer\pySoundPlayer.exe; DestDir: {app}
Source: c:\cygwin\usr\local\bin\libgoocanvas.dll; DestDir: {app}

[Languages]
Name: Fr; MessagesFile: "compiler:Languages\French.isl"
Name: En; MessagesFile: "compiler:Default.isl"

[Setup]
AppCopyright=GPL
AppName=Advene
AppVerName=Advene 0.34
DefaultDirName={pf}\Advene
ShowLanguageDialog=yes
VersionInfoVersion=0.34
VersionInfoCompany=LIRIS
PrivilegesRequired=none
LicenseFile=debian\copyright
DisableFinishedPage=false
DefaultGroupName=Advene
VersionInfoDescription=Annotate DVDs, Exchange on the NEt
InfoAfterFile=debian\changelog
OutputBaseFilename=setup_advene_0.34
VersionInfoTextVersion=0.34

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

;[Registry]
;Root: HKLM; Subkey: Software\Advene; ValueType: string; ValueName: Path; ValueData: {app}\; Flags: uninsdeletekey

[Icons]
Name: {group}\Advene; Filename: {app}\advene.exe; WorkingDir: {app}; IconFilename: {app}\advene.ico; Comment: Annotate DVDs, Exchange on the NEt; IconIndex: 0
Name: {userdesktop}\Advene; Filename: {app}\advene.exe; WorkingDir: {app}; IconFilename: {app}\advene.ico; Comment: Annotate DVDs, Exchange on the NEt; Tasks: desktopicon

