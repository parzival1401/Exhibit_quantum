@echo off
rem install_autostart.bat - make Exhibit Quantum start when Windows signs in.
rem
rem Puts an "Exhibit Quantum" shortcut to start_exhibit.bat in this user's
rem Startup folder, set to run minimised so its console window stays out of
rem the way. Run it once; run it again after moving the project folder.
rem To undo: Win+R, type  shell:startup , delete "Exhibit Quantum".

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'Exhibit Quantum.lnk';" ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk);" ^
  "$s.TargetPath = Join-Path (Get-Location) 'start_exhibit.bat';" ^
  "$s.WorkingDirectory = (Get-Location).Path;" ^
  "$s.WindowStyle = 7;" ^
  "$s.Save();" ^
  "Write-Host ('Auto-start installed: ' + $lnk)"

pause
