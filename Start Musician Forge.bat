@echo off
rem Starts Musician Forge without a console window.
cd /d "%~dp0"
set "MF_PYW=%LOCALAPPDATA%\MusicianForge\venv\Scripts\pythonw.exe"
if not exist "%MF_PYW%" (
  echo Musician Forge is not installed yet. Please run "Install or Update Musician Forge" first.
  echo Press any key to close this window.
  pause > nul
  exit /b 1
)
start "" "%MF_PYW%" -m musicianforge %*
