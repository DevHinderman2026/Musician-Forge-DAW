@echo off
setlocal
title Musician Forge installer
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
echo Installing Musician Forge. This takes a few minutes. Please wait.
call "%~dp0tools\find_base_python.bat"
if not defined MF_BASE_PY (
  echo Python 3 was not found. Please install Python from python.org, then run this again.
  echo Press any key to close this window.
  pause > nul
  exit /b 1
)
"%MF_BASE_PY%" "%~dp0tools\install.py"
if errorlevel 1 (
  echo The installation had a problem. The details are in the logs folder, in install_log.txt.
) else (
  echo Musician Forge is installed and ready.
)
echo Press any key to close this window.
pause > nul
endlocal
