[Files]
Source: C:\cygwin\home\oaubert\advene-project\dist\library.zip; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\advene.exe; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\_ctypes.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\_gtk.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\_imaging.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\_imagingtk.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\_socket.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\_sre.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\_ssl.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\_tkinter.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\_winreg.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\atk.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\boolean.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\cygwin1.dll; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\datetime.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\glade.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\gobject.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\libglade-2.0-0.dll; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\libxml2.dll; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\mmap.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\pango.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\pyexpat.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\select.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\sgmlop.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\tcl84.dll; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\tk84.dll; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\vlc.pyd; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\w9xpopen.exe; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\zlib1.dll; DestDir: {app}
Source: C:\cygwin\home\oaubert\advene-project\dist\python23.dll; DestDir: {app}
Source: share\*; DestDir: {app}\share; Flags: recursesubdirs
[Setup]
AppCopyright=GPL
AppName=Advene
AppVerName=Advene 0.13
DefaultDirName={pf}\Advene
ShowLanguageDialog=yes
VersionInfoVersion=0.13
VersionInfoCompany=LIRIS
PrivilegesRequired=poweruser
LicenseFile=C:\cygwin\home\oaubert\advene-project\debian\copyright
[Registry]
Root: HKLM; Subkey: Software\Advene; ValueType: string; ValueName: Path; ValueData: {app}\; Flags: uninsdeletekey
