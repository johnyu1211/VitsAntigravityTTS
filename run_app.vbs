Set WshShell = CreateObject("WScript.Shell")
strPath = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
WshShell.CurrentDirectory = strPath
WshShell.Run Chr(34) & strPath & "node_modules\electron\dist\electron.exe" & Chr(34) & " " & Chr(34) & strPath & "." & Chr(34), 0, False
