Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
strPyw = chr(34) & strScriptDir & "\FocusPilot.pyw" & chr(34)

' Găsește pythonw.exe
strPythonw = "pythonw.exe"

' Rulează complet invizibil fără nicio fereastră de consolă (0 = hide)
WshShell.Run strPythonw & " " & strPyw, 0, False
