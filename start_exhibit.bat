@echo off
rem start_exhibit.bat - launch Exhibit Quantum on Windows.
rem
rem Run by the auto-start shortcut that install_autostart.bat creates, and
rem double-clickable by hand. Output goes to exhibit.log next to this file.
rem
rem If the exhibit crashes it is started again. Quitting on purpose (X)
rem exits with code 0, which ends the loop, so staff can still close it.

cd /d "%~dp0"

rem Give the monitors, the touchscreen and the Arduino time to come up
rem after the machine boots, so the screens and the port are found.
timeout /t 15 /nobreak >nul

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

:run
echo [%date% %time%] Starting the exhibit>> exhibit.log
"%PY%" -u main.py >> exhibit.log 2>&1
if %errorlevel%==0 goto :eof

echo [%date% %time%] Exited with code %errorlevel% - restarting in 5 s>> exhibit.log
timeout /t 5 /nobreak >nul
goto run
