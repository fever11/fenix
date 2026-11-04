' Core: MK-Agentic-System - Powered by FENIX Engine - (c) 2026 Mustafa Koc - GPL-3.0-only (LICENSE, NOTICE.md)
' FENIX - Tek tikla baslatici / one-click launcher (no console window)
Dim fso, scriptDir, shell, pythonwPath, mainScript
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = scriptDir
pythonwPath = scriptDir & "\venv\Scripts\pythonw.exe"
If Not fso.FileExists(pythonwPath) Then
    pythonwPath = "pythonw.exe"
End If
mainScript = scriptDir & "\app.py"
shell.Run """" & pythonwPath & """ """ & mainScript & """", 0, False
