[Files]
Source: dist\library.zip; DestDir: {app}
Source: dist\advene.exe; DestDir: {app}
Source: dist\_ctypes.pyd; DestDir: {app}
Source: dist\_gtk.pyd; DestDir: {app}
Source: dist\_imaging.pyd; DestDir: {app}
Source: dist\_imagingtk.pyd; DestDir: {app}
Source: dist\_socket.pyd; DestDir: {app}
Source: dist\_sre.pyd; DestDir: {app}
Source: dist\_ssl.pyd; DestDir: {app}
Source: dist\_tkinter.pyd; DestDir: {app}
Source: dist\_winreg.pyd; DestDir: {app}
Source: dist\atk.pyd; DestDir: {app}
Source: dist\boolean.pyd; DestDir: {app}
Source: dist\cygwin1.dll; DestDir: {app}
Source: dist\datetime.pyd; DestDir: {app}
Source: dist\glade.pyd; DestDir: {app}
Source: dist\gobject.pyd; DestDir: {app}
Source: dist\libglade-2.0-0.dll; DestDir: {app}
Source: dist\libxml2.dll; DestDir: {app}
Source: dist\mmap.pyd; DestDir: {app}
Source: dist\pango.pyd; DestDir: {app}
Source: dist\pyexpat.pyd; DestDir: {app}
Source: dist\select.pyd; DestDir: {app}
Source: dist\sgmlop.pyd; DestDir: {app}
Source: dist\tcl84.dll; DestDir: {app}
Source: dist\tk84.dll; DestDir: {app}
Source: dist\vlc.pyd; DestDir: {app}
Source: dist\w9xpopen.exe; DestDir: {app}
Source: dist\zlib1.dll; DestDir: {app}
Source: dist\python23.dll; DestDir: {app}
Source: share\*; DestDir: {app}\share; Flags: recursesubdirs
Source: locale\*; DestDir: {app}\locale; Flags: recursesubdirs
[Setup]
AppCopyright=GPL
AppName=Advene
AppVerName=Advene 0.14
DefaultDirName={pf}\Advene
ShowLanguageDialog=yes
VersionInfoVersion=0.13
VersionInfoCompany=LIRIS
PrivilegesRequired=poweruser
LicenseFile=debian\copyright
DisableFinishedPage=true
[Registry]
Root: HKLM; Subkey: Software\Advene; ValueType: string; ValueName: Path; ValueData: {app}\; Flags: uninsdeletekey
