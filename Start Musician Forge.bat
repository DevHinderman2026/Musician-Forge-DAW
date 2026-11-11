@echo off
rem Starts Musician Forge without a console window.
cd /d "%~dp0"
set "MF_DATA=%LOCALAPPDATA%\MusicianForge"
rem An install made with the Microsoft Store's Python keeps Musician Forge's files in MusicianForge in the user
rem folder instead, where the Store's Python does not hide them, and says so in this file, which an install with
rem any other Python takes away again (0.9.13; tools\check_python.py and tools\install.py).
if exist "%USERPROFILE%\MusicianForge\installed_with_store_python.txt" set "MF_DATA=%USERPROFILE%\MusicianForge"
set "MF_PYW=%MF_DATA%\venv\Scripts\pythonw.exe"
if not exist "%MF_PYW%" (
  echo Musician Forge is not installed yet. Please run "Install or Update Musician Forge" first.
  echo Press any key to close this window.
  pause > nul
  exit /b 1
)
rem install.py writes this file when an install starts and removes it once everything Musician Forge needs to start
rem is installed. While it is there, the last Install or Update stopped partway, and Musician Forge would close at
rem once without a word. (An install from before 0.9.7 has no such file and starts as before.)
if exist "%MF_DATA%\install_unfinished.json" (
  echo The last Install or Update of Musician Forge did not finish, so Musician Forge cannot start yet.
  echo Please run "Install or Update Musician Forge" again. If it stops again, the logs folder has install_log.txt.
  echo Press any key to close this window.
  pause > nul
  exit /b 1
)
start "" "%MF_PYW%" -m musicianforge %*
