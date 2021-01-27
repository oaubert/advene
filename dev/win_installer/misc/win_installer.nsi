; Copyright 2016 Christoph Reiter
;
; This program is free software; you can redistribute it and/or modify
; it under the terms of the GNU General Public License as published by
; the Free Software Foundation; either version 2 of the License, or
; (at your option) any later version.

Unicode true

!define ADVENE_NAME "Advene"
!define ADVENE_ID "advene"
!define ADVENE_DESC "Video Annotation / Player"

!define ADVENE_WEBSITE "https://www.advene.org"

!define ADVENE_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${ADVENE_NAME}"
!define ADVENE_INSTDIR_KEY "Software\${ADVENE_NAME}"
!define ADVENE_INSTDIR_VALUENAME "InstDir"

!define MUI_CUSTOMFUNCTION_GUIINIT custom_gui_init
!include "MUI2.nsh"
!include "FileFunc.nsh"

Name "${ADVENE_NAME} (${VERSION})"
OutFile "advene-LATEST.exe"
SetCompressor /SOLID /FINAL lzma
SetCompressorDictSize 32
InstallDir "$PROGRAMFILES\${ADVENE_NAME}"
RequestExecutionLevel admin

Var ADVENE_INST_BIN
Var UNINST_BIN

!define MUI_ABORTWARNING
!define MUI_ICON "..\advene.ico"

!insertmacro MUI_PAGE_LICENSE "..\advene\COPYING"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Esperanto"
!insertmacro MUI_LANGUAGE "French"

Section "Install"
    SetShellVarContext all

    ; Use this to make things faster for testing installer changes
    ;~ SetOutPath "$INSTDIR\bin"
    ;~ File /r "mingw32\bin\*.exe"

    SetOutPath "$INSTDIR"
    File /r "*.*"

    StrCpy $ADVENE_INST_BIN "$INSTDIR\bin\advene.exe"
    StrCpy $UNINST_BIN "$INSTDIR\uninstall.exe"

    ; Store installation folder
    WriteRegStr HKLM "${ADVENE_INSTDIR_KEY}" "${ADVENE_INSTDIR_VALUENAME}" $INSTDIR

    ; Set up an entry for the uninstaller
    WriteRegStr HKLM "${ADVENE_UNINST_KEY}" \
        "DisplayName" "${ADVENE_NAME} - ${ADVENE_DESC}"
    WriteRegStr HKLM "${ADVENE_UNINST_KEY}" "DisplayIcon" "$\"$ADVENE_INST_BIN$\""
    WriteRegStr HKLM "${ADVENE_UNINST_KEY}" "UninstallString" \
        "$\"$UNINST_BIN$\""
    WriteRegStr HKLM "${ADVENE_UNINST_KEY}" "QuietUninstallString" \
    "$\"$UNINST_BIN$\" /S"
    WriteRegStr HKLM "${ADVENE_UNINST_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "${ADVENE_UNINST_KEY}" "HelpLink" "${ADVENE_WEBSITE}"
    WriteRegStr HKLM "${ADVENE_UNINST_KEY}" "Publisher" "The ${ADVENE_NAME} Development Community"
    WriteRegStr HKLM "${ADVENE_UNINST_KEY}" "DisplayVersion" "${VERSION}"
    WriteRegDWORD HKLM "${ADVENE_UNINST_KEY}" "NoModify" 0x1
    WriteRegDWORD HKLM "${ADVENE_UNINST_KEY}" "NoRepair" 0x1
    ; Installation size
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "${ADVENE_UNINST_KEY}" "EstimatedSize" "$0"

    ; Register a default entry for file extensions
    WriteRegStr HKLM "Software\Classes\${ADVENE_ID}.assoc.ANY\shell\play\command" "" "$\"$ADVENE_INST_BIN$\" --run --play-file $\"%1$\""
    WriteRegStr HKLM "Software\Classes\${ADVENE_ID}.assoc.ANY\DefaultIcon" "" "$\"$ADVENE_INST_BIN$\""
    WriteRegStr HKLM "Software\Classes\${ADVENE_ID}.assoc.ANY\shell\play" "FriendlyAppName" "${ADVENE_NAME}"

    ; Add application entry
    WriteRegStr HKLM "Software\${ADVENE_NAME}\${ADVENE_ID}\Capabilities" "ApplicationDescription" "${ADVENE_DESC}"
    WriteRegStr HKLM "Software\${ADVENE_NAME}\${ADVENE_ID}\Capabilities" "ApplicationName" "${ADVENE_NAME}"

    ; Register supported file extensions
    ; (generated using gen_supported_types.py)
    !define ADVENE_ASSOC_KEY "Software\${ADVENE_NAME}\${ADVENE_ID}\Capabilities\FileAssociations"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".264" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".3gp" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".apl" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".asf" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".avi" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".azp" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".dv" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".flv" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".m4v" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".mjpg" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".mjpg" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".mkv" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".mov" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".mp3" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".mp4" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".mp4v" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".mpeg" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".mpg" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".mts" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".ogg" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".ogm" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".ogv" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".ogx" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".ps" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".qt" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".qtm" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".rm" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".rmd" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".rmvb" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".rv" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".ts" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".vfw" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".vob" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".vp6" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".vp7" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".vp8" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".wav" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".webm" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".wmv" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".xml" "${ADVENE_ID}.assoc.ANY"
    WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" ".xvid" "${ADVENE_ID}.assoc.ANY"

    ; Register application entry
    WriteRegStr HKLM "Software\RegisteredApplications" "${ADVENE_NAME}" "Software\${ADVENE_NAME}\${ADVENE_ID}\Capabilities"

    ; Register app paths
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\App Paths\advene.exe" "" "$ADVENE_INST_BIN"

    ; Create uninstaller
    WriteUninstaller "$UNINST_BIN"

    ; Create start menu shortcuts
    CreateDirectory "$SMPROGRAMS\${ADVENE_NAME}"
;     CreateShortCut "$SMPROGRAMS\${ADVENE_NAME}\${ADVENE_NAME}.lnk" "$ADVENE_INST_BIN"
SectionEnd

Function custom_gui_init
    BringToFront

    ; Read the install dir and set it
    Var /GLOBAL instdir_temp
    Var /GLOBAL uninst_bin_temp

    SetRegView 32
    ReadRegStr $instdir_temp HKLM "${ADVENE_INSTDIR_KEY}" "${ADVENE_INSTDIR_VALUENAME}"
    SetRegView lastused
    StrCmp $instdir_temp "" skip 0
        StrCpy $INSTDIR $instdir_temp
    skip:

    SetRegView 64
    ReadRegStr $instdir_temp HKLM "${ADVENE_INSTDIR_KEY}" "${ADVENE_INSTDIR_VALUENAME}"
    SetRegView lastused
    StrCmp $instdir_temp "" skip2 0
        StrCpy $INSTDIR $instdir_temp
    skip2:

    StrCpy $uninst_bin_temp "$INSTDIR\uninstall.exe"

    ; try to un-install existing installations first
    IfFileExists "$INSTDIR" do_uninst do_continue
    do_uninst:
        ; instdir exists
        IfFileExists "$uninst_bin_temp" exec_uninst rm_instdir
        exec_uninst:
            ; uninstall.exe exists, execute it and
            ; if it returns success proceed, otherwise abort the
            ; installer (uninstall aborted by user for example)
            ExecWait '"$uninst_bin_temp" _?=$INSTDIR' $R1
            ; uninstall succeeded, since the uninstall.exe is still there
            ; goto rm_instdir as well
            StrCmp $R1 0 rm_instdir
            ; uninstall failed
            Abort
        rm_instdir:
            ; either the uninstaller was successfull or
            ; the uninstaller.exe wasn't found
            RMDir /r "$INSTDIR"
    do_continue:
        ; the instdir shouldn't exist from here on

    BringToFront
FunctionEnd

Section "Uninstall"
    SetShellVarContext all
    SetAutoClose true

    ; Remove start menu entries
;    Delete "$SMPROGRAMS\${ADVENE_NAME}\${ADVENE_NAME}.lnk"
    RMDir "$SMPROGRAMS\${ADVENE_NAME}"

    ; Remove application registration and file assocs
    DeleteRegKey HKLM "Software\Classes\${ADVENE_ID}.assoc.ANY"
    DeleteRegKey HKLM "Software\${ADVENE_NAME}"
    DeleteRegValue HKLM "Software\RegisteredApplications" "${ADVENE_NAME}"

    ; Remove app paths
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\App Paths\advene.exe"

    ; Delete installation related keys
    DeleteRegKey HKLM "${ADVENE_UNINST_KEY}"
    DeleteRegKey HKLM "${ADVENE_INSTDIR_KEY}"

    ; Delete files
    RMDir /r "$INSTDIR"
SectionEnd
