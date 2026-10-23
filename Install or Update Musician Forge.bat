@echo off
setlocal
title Musician Forge installer
cd /d "%~dp0"
if not exist "%~dp0tools\install.py" goto :not_extracted
if not exist "logs" mkdir "logs"
set "MF_PY_LOG=%TEMP%\musicianforge_python_setup.txt"
if exist "%MF_PY_LOG%" del "%MF_PY_LOG%"
echo Installing Musician Forge. This takes a few minutes. Please wait.
call "%~dp0tools\find_base_python.bat"
if not defined MF_BASE_PY call "%~dp0tools\get_python.bat"
if not defined MF_BASE_PY goto :no_python
"%MF_BASE_PY%" "%~dp0tools\install.py"
if not "%errorlevel%"=="0" (
  echo The installation had a problem. The details are in the logs folder, in install_log.txt.
) else (
  echo Musician Forge is installed and ready.
)
goto :done

:not_extracted
echo Musician Forge's files cannot be found: this window was probably opened from inside the zip file.
echo Close this window. In File Explorer, choose Extract All on the zip file, then open the Musician Forge
echo folder it makes and run Install or Update Musician Forge from there.
goto :done

:no_python
rem What finding (and perhaps installing) Python did: into the log a tester sends, as install.py does otherwise.
if exist "%MF_PY_LOG%" copy /y "%MF_PY_LOG%" "logs\install_log.txt" > nul
echo Please install Python 3.14 from python.org: choose Install Now, which does not need administrator rights.
echo Then run Install or Update Musician Forge again.

:done
echo Press any key to close this window.
pause > nul
endlocal
