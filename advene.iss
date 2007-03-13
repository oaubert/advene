[Files]
Source: dist\library.zip; DestDir: {app}
Source: dist\*.dll; DestDir: {app}
Source: dist\*.pyd; DestDir: {app}
Source: dist\advene.exe; DestDir: {app}
Source: dist\w9xpopen.exe; DestDir: {app}
Source: dist\share\*; DestDir: {app}\share; Flags: recursesubdirs
Source: dist\doc\*; DestDir: {app}\doc; Flags: recursesubdirs
Source: dist\locale\*; DestDir: {app}\locale; Flags: recursesubdirs
Source: share\pixmaps\dvd.ico; DestDir: {app}; DestName: advene.ico
Source: c:\gtk\etc\*; DestDir: {app}\etc; Flags: recursesubdirs
Source: examples\*v2.azp; DestDir: {app}\examples
Source: c:\gtk\lib\gtk-2.0\*; DestDir: {app}\lib\gtk-2.0; Flags: recursesubdirs
Source: c:\gtk\share\locale\fr\*; DestDir: {app}\lib\locale\fr; Flags: recursesubdirs
Source: c:\gtk\lib\pango\*; DestDir: {app}\lib\pango; Flags: recursesubdirs
Source: c:\gtk\share\themes\*; DestDir: {app}\share\themes; Flags: recursesubdirs
Source: c:\gtk\bin\libpng12.dll; DestDir: {app}
Source: c:\gtk\bin\libpangoft2-1.0-0.dll; DestDir: {app}
Source: c:\gtk\bin\libtiff3.dll; DestDir: {app}
Source: c:\gtk\bin\jpeg62.dll; DestDir: {app}
[Setup]
AppCopyright=GPL
AppName=Advene
AppVerName=Advene 0.22
DefaultDirName={pf}\Advene
ShowLanguageDialog=yes
VersionInfoVersion=0.22
VersionInfoCompany=LIRIS
PrivilegesRequired=none
LicenseFile=debian\copyright
DisableFinishedPage=false
DefaultGroupName=Advene
VersionInfoDescription=Annotate DVDs, Exchange on the NEt
InfoAfterFile=debian\changelog
OutputBaseFilename=setup_advene_0.22
VersionInfoTextVersion=0.22
[Registry]
Root: HKLM; Subkey: Software\Advene; ValueType: string; ValueName: Path; ValueData: {app}\; Flags: uninsdeletekey
[Icons]
Name: {group}\Advene; Filename: {app}\advene.exe; WorkingDir: {app}; IconFilename: {app}\advene.ico; Comment: Annotate DVDs, Exchange on the NEt; IconIndex: 0
