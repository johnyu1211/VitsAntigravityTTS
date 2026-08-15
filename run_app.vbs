Set WshShell = CreateObject("WScript.Shell")
strPath = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
appDir = Left(strPath, Len(strPath) - 1)
WshShell.CurrentDirectory = strPath
WshShell.Run Chr(34) & strPath & "node_modules\electron\dist\electron.exe" & Chr(34) & " " & Chr(34) & appDir & Chr(34), 1, False
