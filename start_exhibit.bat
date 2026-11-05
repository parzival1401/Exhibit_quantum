@echo off
rem start_exhibit.bat - launch Exhibit Quantum on Windows.
rem
rem Run by the auto-start shortcut that install_autostart.bat creates, and
rem double-clickable by hand. Output goes to exhibit.log next to this file.
rem It works from wherever the project folder is, spaces in the path included.
rem
rem If the exhibit crashes it is started again. Quitting on purpose (X)
rem exits with code 0, which ends the loop, so staff can still close it.

title Exhibit Quantum
cd /d "%~dp0"

rem Logged before anything else: if this line is in exhibit.log after a
rem restart, Windows did run the shortcut.
>> exhibit.log echo [%date% %time%] Launcher started in %cd%

rem Give the monitors, the touchscreen and the Arduino time to come up
rem after the machine boots, so the screens and the port are found.
timeout /t 15 /nobreak >nul

rem Write the log in UTF-8 whatever the Windows language settings are.
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

rem Find a Python that has the exhibit's packages. Each candidate is tried
rem with "import PyQt6", which also skips the Microsoft Store "python"
rem placeholder that Windows 11 puts on the PATH.
set "PY="
for %%P in (".venv\Scripts\python.exe" "venv\Scripts\python.exe") do (
    if not defined PY if exist %%P (
        %%P -c "import PyQt6" >nul 2>&1 && set "PY=%%~P"
    )
)
if not defined PY (
    py -3 -c "import PyQt6" >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
    python -c "import PyQt6" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    >> exhibit.log echo [%date% %time%] No Python with PyQt6 found. Install the requirements - see README.
    echo.
    echo   No Python with the exhibit's packages was found.
    echo   In this folder run:  py -m venv .venv
    echo   then:                .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
>> exhibit.log echo [%date% %time%] Using Python: %PY%

:run
>> exhibit.log echo [%date% %time%] Starting the exhibit
%PY% -u main.py >> exhibit.log 2>&1
set "CODE=%errorlevel%"
if "%CODE%"=="0" (
    >> exhibit.log echo [%date% %time%] Exhibit closed normally
    exit /b 0
)

>> exhibit.log echo [%date% %time%] Exited with code %CODE% - restarting in 5 s
timeout /t 5 /nobreak >nul
goto run
