@echo off
rem Installs or updates Musician Forge: finds a Python it can use, then tools\install.py does the work.
rem
rem For screen reader users (0.9.14). A tester, 13 Nov 2026: "installer opened and just said installer. After the
rem tester pressed a key it closed." A screen reader reads only what is written after it has started listening to a
rem new window, and this window wrote its message at once and closed at the first key, an arrow key pressed to read
rem it too. So now:
rem - the first words wait two seconds, until the screen reader listens;
rem - the window's title says what is going on and how it ended (a screen reader reads the title by itself);
rem - a problem is also written to a text file that opens in Notepad, where it stays, can be read line by line and
rem   copied into an email (Russell, 13 Nov 2026), and is kept in the logs folder as installer_message.txt;
rem - nothing the installer starts can wait for a key nobody was asked for (every such program reads from nul);
rem - the window closes on Enter only.
rem MF_INSTALLER_TEST is set by the tests only: Notepad is then not opened.
setlocal
title Musician Forge installer: starting
cd /d "%~dp0"
set "MF_MESSAGE=%TEMP%\Musician Forge installer message.txt"
set "MF_ERRORS=%TEMP%\musicianforge_installer_errors.txt"
set "MF_PY_LOG=%TEMP%\musicianforge_python_setup.txt"
if exist "%MF_MESSAGE%" del "%MF_MESSAGE%"
if exist "%MF_ERRORS%" del "%MF_ERRORS%"
if exist "%MF_PY_LOG%" del "%MF_PY_LOG%"
timeout /t 2 /nobreak > nul 2>&1
if not exist "%~dp0tools\install.py" goto :not_extracted
if not exist "logs" mkdir "logs" 2> nul
echo Installing Musician Forge. This takes a few minutes. Please wait.
echo Looking for Python on this computer.
title Musician Forge installer: looking for Python
call "%~dp0tools\find_base_python.bat"
if not defined MF_BASE_PY call "%~dp0tools\get_python.bat"
if not defined MF_BASE_PY goto :no_python
title Musician Forge installer: installing, please wait
rem install.py says each step, and writes the reason into MF_PROBLEM_FILE when it has to stop.
set "MF_PROBLEM_FILE=%MF_MESSAGE%"
"%MF_BASE_PY%" "%~dp0tools\install.py" 2> "%MF_ERRORS%" < nul
set "MF_CODE=%errorlevel%"
if not "%MF_CODE%"=="0" goto :install_problem
title Musician Forge installer: finished, Musician Forge is ready
echo Musician Forge is installed and ready. To open it, run Start Musician Forge in this folder.
goto :done

:not_extracted
rem Started from inside the zip file (Windows then unpacks this one file alone into a temporary folder), or only
rem this file was downloaded from the GitHub page.
> "%MF_MESSAGE%" echo Musician Forge was not installed: its other files were not found beside this installer.
>> "%MF_MESSAGE%" echo.
>> "%MF_MESSAGE%" echo This happens when Install or Update Musician Forge is started from inside the zip file, before the
>> "%MF_MESSAGE%" echo zip file is extracted, or when only this one file was downloaded. It was started from this folder:
>> "%MF_MESSAGE%" echo "%~dp0"
>> "%MF_MESSAGE%" echo.
>> "%MF_MESSAGE%" echo What to do:
>> "%MF_MESSAGE%" echo 1. If you do not have the zip file yet: on Musician Forge's GitHub page, choose Code, then Download ZIP.
>> "%MF_MESSAGE%" echo 2. In File Explorer, go to your Downloads folder and select the zip file. Do not press Enter on it.
>> "%MF_MESSAGE%" echo 3. Press Shift+F10 for its context menu and choose Extract All, then press Enter on Extract.
>> "%MF_MESSAGE%" echo 4. Open the folder Windows made, then the Musician-Forge-DAW-main folder inside it.
>> "%MF_MESSAGE%" echo 5. Run Install or Update Musician Forge from there.
goto :problem

:no_python
rem What finding (and perhaps installing) Python did: into the log a tester sends, as install.py does otherwise.
if exist "%MF_PY_LOG%" copy /y "%MF_PY_LOG%" "logs\install_log.txt" > nul 2>&1
> "%MF_MESSAGE%" echo Musician Forge was not installed: it needs Python, and this computer has no Python it can use.
>> "%MF_MESSAGE%" echo.
if defined MF_PY_REASON >> "%MF_MESSAGE%" echo %MF_PY_REASON%
if not defined MF_PY_REASON >> "%MF_MESSAGE%" echo No Python was found on this computer.
if defined MF_PY_NOTE >> "%MF_MESSAGE%" echo %MF_PY_NOTE%
>> "%MF_MESSAGE%" echo.
>> "%MF_MESSAGE%" echo What to do:
>> "%MF_MESSAGE%" echo 1. Please install Python 3.14 from python.org: choose Install Now, which does not need administrator rights.
>> "%MF_MESSAGE%" echo 2. Then run Install or Update Musician Forge again.
>> "%MF_MESSAGE%" echo.
>> "%MF_MESSAGE%" echo What was tried is in the logs folder, in install_log.txt.
goto :problem

:install_problem
rem install.py has said the reason and written it into the message file. Without that file it stopped before it
rem could say anything: the reason is what Python wrote last.
if exist "%MF_MESSAGE%" goto :open_message
> "%MF_MESSAGE%" echo Musician Forge was not installed: the installer stopped unexpectedly, with exit code %MF_CODE%.
>> "%MF_MESSAGE%" echo.
>> "%MF_MESSAGE%" echo What it wrote last:
>> "%MF_MESSAGE%" type "%MF_ERRORS%" 2> nul
>> "%MF_MESSAGE%" echo.
>> "%MF_MESSAGE%" echo What to do:
>> "%MF_MESSAGE%" echo 1. Run Install or Update Musician Forge again.
>> "%MF_MESSAGE%" echo 2. If it stops again, send this message and the file install_log.txt from the logs folder to
>> "%MF_MESSAGE%" echo    russellhinderman425@gmail.com.
goto :problem

:problem
echo.
type "%MF_MESSAGE%"
:open_message
title Musician Forge installer: not installed, the reason is in this window and in Notepad
if exist "logs\" copy /y "%MF_MESSAGE%" "logs\installer_message.txt" > nul 2>&1
if defined MF_INSTALLER_TEST goto :done
echo.
echo This message is also opening in Notepad, where you can read it line by line and copy it.
set "MF_NOTEPAD=1"
where notepad.exe > nul 2>&1
if not "%errorlevel%"=="0" set "MF_NOTEPAD="
if defined MF_NOTEPAD start "" notepad.exe "%MF_MESSAGE%"
if not defined MF_NOTEPAD start "" "%MF_MESSAGE%"

:done
echo.
set /p "MF_ENTER=Press Enter to close this window. "
endlocal
