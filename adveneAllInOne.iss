[Files]
Source: dist\library.zip; DestDir: {app}; Components: advene
Source: dist\*.dll; DestDir: {app}; Components: advene
Source: dist\*.pyd; DestDir: {app}; Components: advene
Source: dist\advene.exe; DestDir: {app}; Components: advene
Source: dist\w9xpopen.exe; DestDir: {app}; Components: advene
Source: dist\share\*; DestDir: {app}\share; Flags: recursesubdirs; Components: advene
Source: dist\doc\*; DestDir: {app}\doc; Flags: recursesubdirs; Components: advene
Source: dist\locale\*; DestDir: {app}\locale; Flags: recursesubdirs; Components: advene
Source: share\pixmaps\advene.ico; DestDir: {app}; DestName: advene.ico; Components: advene
Source: c:\gtk\etc\*; DestDir: {app}\etc; Flags: recursesubdirs; Components: advene
Source: examples\*v10.azp; DestDir: {app}\examples; Components: advene
Source: c:\gtk\lib\gtk-2.0\*; DestDir: {app}\lib\gtk-2.0; Flags: recursesubdirs; Components: advene
Source: c:\gtk\share\locale\fr\*; DestDir: {app}\lib\locale\fr; Flags: recursesubdirs; Components: advene
;Source: c:\gtk\lib\pango\*; DestDir: {app}\lib\pango; Flags: recursesubdirs     gtk < 2.16.6
Source: c:\gtk\share\themes\*; DestDir: {app}\share\themes; Flags: recursesubdirs; Components: advene
;Source: c:\gtk\bin\libpng12.dll; DestDir: {app}  gtk < 2.16.6
;Source: c:\gtk\bin\libpng12-0.dll; DestDir: {app}; Components: advene    gtk = 2.16
Source: c:\gtk\bin\libpng14-14.dll; DestDir: {app}; Components: advene
Source: c:\gtk\bin\libpangoft2-1.0-0.dll; DestDir: {app}; Components: advene
;Source: c:\gtk\bin\libtiff3.dll; DestDir: {app}  gtk < 2.16.6
Source: c:\gtk\bin\libtiff-3.dll; DestDir: {app}; Components: advene
;Source: c:\gtk\bin\jpeg62.dll; DestDir: {app}    gtk < 2.16.6
Source: c:\gtk\bin\libjpeg-7.dll; DestDir: {app}; Components: advene
Source: c:\gtk\bin\librsvg-2-2.dll; DestDir: {app}; Components: advene
Source: c:\gtk\bin\libcroco-0.6-3.dll; DestDir: {app}; Components: advene
Source: c:\gtk\bin\libgsf-1-114.dll; DestDir: {app}; Components: advene
Source: c:\gtk\bin\bzip2.dll; DestDir: {app}; Components: advene
Source: c:\gtk\bin\libgio-2.0-0.dll; DestDir: {app}; Components: advene
Source: c:\gtk\bin\libxml2-2.dll; DestDir: {app}; Components: advene
Source: c:\gtk\bin\iconv.dll; DestDir: {app}; Components: advene
Source: Brl\*; DestDir: {app}; Components: advene

;Source: c:\cygwin\usr\local\bin\libgoocanvas3.dll; DestDir: {app}    goocanvas0.10
;Source: Win32SoundPlayer\*; DestDir: {app}\Win32SoundPlayer; Components: advene     not needed anymore
Source: c:\GTK\bin\libgoocanvas-3.dll; DestDir: {app}; Components: advene
;msvcr90.dll,m,p & manifest needed for pygtk2.16 & co. Can be found in visual studio redist
;http://www.microsoft.com/downloads/details.aspx?FamilyID=9B2DA534-3E03-4391-8A4D-074B9F2BC1BF&displaylang=fr
Source: vcredist_x86.exe; DestDir: {tmp}; Components: advene
Source: c:\gtk\bin\gdk-pixbuf-query-loaders.exe; DestDir: {app}; Components: advene
Source: post_install.bat; DestDir: {app}; Components: advene

Source: c:\Program Files (x86)\VLC\libvlccore.dll; DestDir: {app}; Components: vlc
Source: c:\Program Files (x86)\VLC\libvlc.dll; DestDir: {app}; Components: vlc
Source: c:\Program Files (x86)\VLC\plugins\*; DestDir: {app}\vlcplugins; Components: vlc

Source: gst\*; DestDir: {app}\gst; Flags: recursesubdirs; Components: gst

;To be able to detect if advene is already running
Source: psvince.dll; Flags: dontcopy

[CustomMessages]
En.CleanPrefs=Clean &preferences
Fr.CleanPrefs=Effacer les &préférences
En.ITadvenegst=Advene with included gstreamer
Fr.ITadvenegst=Advene et gstreamer inclus
En.ITadvenevlc=Advene with included vlc
Fr.ITadvenevlc=Advene et vlc inclus
En.ITadvene=Advene without included vlc
Fr.ITadvene=Advene sans vlc
En.ITcustom=Custom installation
Fr.ITcustom=Installation personnalisée

[Types]
Name: "AdveneGst"; Description: "{cm:ITadvenegst}"
Name: "AdveneVlc"; Description: "{cm:ITadvenevlc}"
Name: "AdveneOnly"; Description: "{cm:ITadvene}"
Name: "Custom"; Description: "{cm:ITcustom}"; Flags: iscustom

[Components]
Name: advene; Description: Advene files; Types: AdveneOnly AdveneVlc AdveneGst Custom; Flags: fixed
Name: vlc; Description: VLC files; Types: AdveneVlc Custom
Name: gst; Description: Gstreamer files; Types: AdveneGst Custom

[Languages]
Name: Fr; MessagesFile: "compiler:Languages\French.isl"
Name: En; MessagesFile: "compiler:Default.isl"

[Setup]
AppCopyright=GPL
AppName=Advene
AppVerName=Advene 0.42
DefaultDirName={pf}\Advene
ShowLanguageDialog=yes
VersionInfoVersion=0.42
VersionInfoCompany=LIRIS
PrivilegesRequired=none
LicenseFile=debian\copyright
DisableFinishedPage=false
DefaultGroupName=Advene
VersionInfoDescription=Annotate DVDs, Exchange on the NEt
InfoAfterFile=debian\changelog
OutputBaseFilename=setup_advene_0.42_vlc_1.0.3_gstreamer_0.10.5
VersionInfoTextVersion=0.42
ChangesAssociations=yes

[Registry]
Root: HKCU; Subkey: Software\Advene; ValueType: string; ValueName: Path; ValueData: {app}\; Flags: uninsdeletekey
Root: HKCU; Subkey: ".azp"; ValueType: string; ValueName: ""; ValueData: "Advene"; Flags: uninsdeletevalue; Check: CanChange;
Root: HKCU; Subkey: "Advene"; ValueType: string; ValueName: ""; ValueData: "Advene"; Flags: uninsdeletekey; Check: CanChange;
Root: HKCU; Subkey: "Advene\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\advene.exe,0"; Check: CanChange;
Root: HKCU; Subkey: "Advene\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\advene.exe"" ""%1"""; Check: CanChange;
;Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "GST_PLUGIN_PATH"; ValueData: "{app}\gst\lib\gstreamer-0.10"; Check: GstreamerPathSet;
;Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "PATH"; ValueData: "{app}\gst\bin;{olddata}"; Check: GstreamerPathSet;


[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "cleanprefs"; Description: "{cm:CleanPrefs}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Icons]
Name: {group}\Advene; Filename: {app}\advene.exe; WorkingDir: {app}; IconFilename: {app}\advene.ico; Comment: Annotate DVDs, Exchange on the NEt; IconIndex: 0
Name: {userdesktop}\Advene; Filename: {app}\advene.exe; WorkingDir: {app}; IconFilename: {app}\advene.ico; Comment: Annotate DVDs, Exchange on the NEt; Tasks: desktopicon
Name: {userappdata}\Microsoft\Internet Explorer\Quick Launch\Advene; Filename: {app}\advene.exe; WorkingDir: {app}; IconFilename: {app}\advene.ico; Comment: Annotate DVDs, Exchange on the NEt; Tasks: quicklaunchicon

[InstallDelete]
Type: files; Name: "{userappdata}\..\advene\advene.prefs"; Tasks: cleanprefs
Type: files; Name: "{userappdata}\..\advene\player.prefs"; Tasks: cleanprefs
Type: files; Name: "{userappdata}\..\advene\advene.ini"; Tasks: cleanprefs

[Run]
Filename: "{tmp}\vcredist_x86.exe"; Parameters: "/qb!";
Filename: "{app}\post_install.bat"; Parameters: "";

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Uninstall: String;
begin
  if (CurStep = ssInstall) then begin
    if RegQueryStringValue(HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\Advene_is1', 'UninstallString', Uninstall) then begin
      if MsgBox('Warning: Old Version will be removed!', mbConfirmation, MB_OKCANCEL)=IDOK then begin
          Exec(RemoveQuotes(Uninstall), ' /SILENT', '', SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode);
      end
      else begin
          Abort();
      end;
    end;
  end;
end;

function GstreamerPathSet(): Boolean;
var
  gst_plugin_path: String;
begin
    if IsComponentSelected('gst') then begin
      //MsgBox('Gst Selected', mbError, MB_OK);
      if RegQueryStringValue(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'GST_PLUGIN_PATH', gst_plugin_path) then begin
        if DirExists(gst_plugin_path) then begin
          //MsgBox('You seem to already have gstreamer installed in '+ gst_plugin_path + ', trying to use this one.', mbError, MB_OK);
          Result := False;
        end;
      end
      else begin
        if RegQueryStringValue(HKCU, 'Environment', 'GST_PLUGIN_PATH', gst_plugin_path) then begin
          if DirExists(gst_plugin_path) then begin
            //MsgBox('You seem to already have gstreamer installed in '+ gst_plugin_path + ', trying to use this one.', mbError, MB_OK);
            Result := False;
          end
          else begin
            //MsgBox('Your GST_PLUGIN_PATH environment variable ' + gst_plugin_path + 'seems to be corrupted, we will override it to use our included gstreamer.', mbError, MB_OK);
            Result := True;
          end;
        end
        else begin
          //MsgBox('Setting your PATH and GST_PLUGIN_PATH environment variables to use our included gstreamer.', mbError, MB_OK);
          Result := True;
        end;
      end;
    end;
end;

function CanChange(): Boolean;
begin
  Result := (IsAdminLoggedOn or IsPowerUserLoggedOn);
end;


function IsModuleLoaded(modulename: String ): Boolean;
external 'IsModuleLoaded@files:psvince.dll stdcall';

function InitializeSetup(): Boolean;
begin

if(Not IsModuleLoaded( 'advene.exe' )) then
begin
Result := true;
end

else
begin
MsgBox('Application is already running, exiting setup.', mbInformation, MB_OK);
Result := false;
end

end;

