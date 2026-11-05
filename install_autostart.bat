@echo off
rem install_autostart.bat - make Exhibit Quantum start when Windows signs in.
rem
rem Puts an "Exhibit Quantum" shortcut to start_exhibit.bat in this user's
rem Startup folder. Run it once, by double-clicking it inside the project
rem folder; run it again after moving the project folder.
rem To undo: Win+R, type  shell:startup , delete "Exhibit Quantum".
rem
rem The shortcut opens its console window normally, not minimised: Windows
rem hands a "start minimised" setting on to the programs a batch file
rem starts, so the exhibit's own windows could come up minimised too. The
rem exhibit's full-screen windows cover the console once they open.

cd /d "%~dp0"

if not exist "start_exhibit.bat" (
    echo start_exhibit.bat is not next to this file. Run this from the project folder.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$dir = (Get-Location).Path;" ^
  "$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'Exhibit Quantum.lnk';" ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk);" ^
  "$s.TargetPath = Join-Path $dir 'start_exhibit.bat';" ^
  "$s.WorkingDirectory = $dir;" ^
  "$s.WindowStyle = 1;" ^
  "$s.Save();" ^
  "Write-Host ('Auto-start installed: ' + $lnk);" ^
  "Write-Host ('It runs:              ' + $s.TargetPath)"

echo.
echo Next: restart the computer, or double-click the shortcut to test it now.
echo If the exhibit does not appear, open exhibit.log in this folder.
pause
