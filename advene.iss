[Files]
Source: dist\library.zip; DestDir: {app}
Source: dist\*.dll; DestDir: {app}
Source: dist\*.pyd; DestDir: {app}
Source: dist\advene.exe; DestDir: {app}
Source: dist\w9xpopen.exe; DestDir: {app}
Source: dist\share\*; DestDir: {app}\share; Flags: recursesubdirs
Source: dist\doc\*; DestDir: {app}\doc; Flags: recursesubdirs
Source: dist\locale\*; DestDir: {app}\locale; Flags: recursesubdirs
Source: share\pixmaps\dvd_small.png; DestDir: {app}; DestName: advene.png
Source: \devel\gtk\etc\*; DestDir: {app}\etc; Flags: recursesubdirs
Source: \devel\gtk\lib\gtk-2.0\*; DestDir: {app}\lib\gtk-2.0; Flags: recursesubdirs
Source: \devel\gtk\lib\locale\fr\*; DestDir: {app}\lib\locale\fr; Flags: recursesubdirs
Source: \devel\gtk\lib\pango\*; DestDir: {app}\lib\pango; Flags: recursesubdirs
Source: \devel\gtk\share\themes\*; DestDir: {app}\share\themes; Flags: recursesubdirs
Source: \devel\gtk\bin\libpng12.dll; DestDir: {app}
[Setup]
AppCopyright=GPL
AppName=Advene
AppVerName=Advene 0.15
DefaultDirName={pf}\Advene
ShowLanguageDialog=yes
VersionInfoVersion=0.15
VersionInfoCompany=LIRIS
PrivilegesRequired=poweruser
LicenseFile=debian\copyright
DisableFinishedPage=false
DefaultGroupName=Advene
VersionInfoDescription=Annotate DVDs, Exchange on the NEt
[Registry]
Root: HKLM; Subkey: Software\Advene; ValueType: string; ValueName: Path; ValueData: {app}\; Flags: uninsdeletekey
[Icons]
Name: {group}\Advene; Filename: {app}\advene.exe; WorkingDir: {app}; IconFilename: {app}\advene.png
