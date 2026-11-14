@echo off
rem Removes what "Install or Update Musician Forge" put on this computer (Russell, 10 Oct 2026).
rem Removed: %LOCALAPPDATA%\MusicianForge (Musician Forge's Python environment, sound engine, sounds, settings,
rem crash-recovery copy and recordings of projects never saved), and %LOCALAPPDATA%\MelodyForge if an older
rem version left it. Never touched: your projects, in Documents\Musician Forge Songs (each with its own
rem recordings and exports). Reinstalling opens them as before: project files stay .mforge.
rem From 0.9.13 also MusicianForge in the user folder, where an install made with the Microsoft Store's Python
rem keeps the same things (tools\check_python.py says why), but only when the file the installer wrote there,
rem about_this_folder.txt, says the folder is Musician Forge's. Otherwise MF_STORE names a folder that does not
rem exist, inside Musician Forge's own data folder, so nothing else can ever be removed through it.
setlocal EnableExtensions
title Remove Musician Forge
cd /d "%~dp0"
rem A screen reader reads only what is written after it has started listening to a new window, so the first words
rem wait two seconds, and the window closes on Enter only: an arrow key pressed to read it used to close it (0.9.14).
timeout /t 2 /nobreak > nul 2>&1
if "%LOCALAPPDATA%"=="" (
  echo Windows did not say where programs keep their files, so nothing was removed.
  goto :done
)
set "MF_DATA=%LOCALAPPDATA%\MusicianForge"
set "MF_OLD=%LOCALAPPDATA%\MelodyForge"
set "MF_STORE=%LOCALAPPDATA%\MusicianForge\no_store_install"
if not "%USERPROFILE%"=="" if exist "%USERPROFILE%\MusicianForge\about_this_folder.txt" set "MF_STORE=%USERPROFILE%\MusicianForge"
if not exist "%MF_DATA%\" if not exist "%MF_OLD%\" if not exist "%MF_STORE%\" (
  echo Musician Forge is not installed on this computer, so there is nothing to remove.
  echo Your projects in Documents, Musician Forge Songs, were not touched.
  goto :done
)
rem Musician Forge must be closed: its own Python is in the folder being removed (Melody Forge's, for an older one).
rem (exit code 7 means it is open; anything else, even PowerShell missing, goes on: Windows then refuses to remove
rem the files in use, and the end says so)
powershell -NoProfile -Command "if (Get-Process | Where-Object { $_.Path -and ($_.Path.StartsWith($env:LOCALAPPDATA + '\MusicianForge\', 'OrdinalIgnoreCase') -or $_.Path.StartsWith($env:LOCALAPPDATA + '\MelodyForge\', 'OrdinalIgnoreCase') -or $_.Path.StartsWith($env:USERPROFILE + '\MusicianForge\', 'OrdinalIgnoreCase')) }) { exit 7 } else { exit 0 }" > nul 2>&1
if "%errorlevel%"=="7" (
  echo Musician Forge is still open. Please close it, then run Remove Musician Forge again.
  goto :done
)
echo This removes Musician Forge from this computer: its Python environment, sound engine and sounds.
echo Your projects in Documents, Musician Forge Songs, are kept, and open again if you reinstall.
set "MF_UNSAVED="
if exist "%MF_DATA%\autosave\autosave.mforge" set "MF_UNSAVED=1"
if exist "%MF_STORE%\autosave\autosave.mforge" set "MF_UNSAVED=1"
if defined MF_UNSAVED (
  echo Musician Forge has a crash-recovery copy of unsaved work, and it will be removed. To keep it, choose
  echo No now, open Musician Forge, recover the project and save it.
)
choice /c YN /n /m "Remove Musician Forge? Press Y for yes or N for no."
if errorlevel 2 (
  echo Nothing was removed.
  goto :done
)
choice /c YN /n /m "Keep your settings (audio settings, measured delays, recent projects) for a reinstall? Press Y for yes or N for no."
if errorlevel 2 (set "MF_KEEP=") else (set "MF_KEEP=1")
if exist "%MF_DATA%\" (
  if defined MF_KEEP (
    for /d %%D in ("%MF_DATA%\*") do rmdir /s /q "%%D"
    for %%F in ("%MF_DATA%\*") do if /i not "%%~nxF"=="settings.json" del /f /q "%%F"
  ) else (
    rmdir /s /q "%MF_DATA%"
  )
)
rem The folder of an install made with the Microsoft Store's Python, the same way; the file that says the folder is
rem Musician Forge's stays with the settings, so a later Remove still knows it.
if exist "%MF_STORE%\" (
  if defined MF_KEEP (
    for /d %%D in ("%MF_STORE%\*") do rmdir /s /q "%%D"
    for %%F in ("%MF_STORE%\*") do if /i not "%%~nxF"=="settings.json" if /i not "%%~nxF"=="about_this_folder.txt" del /f /q "%%F"
  ) else (
    rmdir /s /q "%MF_STORE%"
  )
)
rem The folder of Melody Forge, Musician Forge's name before 8 Oct 2026: its settings are kept too when asked.
if exist "%MF_OLD%\" (
  if defined MF_KEEP (
    for /d %%D in ("%MF_OLD%\*") do rmdir /s /q "%%D"
    for %%F in ("%MF_OLD%\*") do if /i not "%%~nxF"=="settings.json" del /f /q "%%F"
  ) else (
    rmdir /s /q "%MF_OLD%"
  )
)
set "MF_LEFT="
if defined MF_KEEP (
  for /d %%D in ("%MF_DATA%\*") do set "MF_LEFT=1"
  for /d %%D in ("%MF_OLD%\*") do set "MF_LEFT=1"
  for /d %%D in ("%MF_STORE%\*") do set "MF_LEFT=1"
) else (
  if exist "%MF_DATA%\" set "MF_LEFT=1"
  if exist "%MF_OLD%\" set "MF_LEFT=1"
  if exist "%MF_STORE%\" set "MF_LEFT=1"
)
if defined MF_LEFT (
  echo Some files could not be removed, perhaps because a program is using them. Restart Windows, then run
  echo Remove Musician Forge again.
  goto :done
)
echo Musician Forge is removed.
if defined MF_KEEP echo Your settings are kept for a reinstall.
echo Your projects are still in Documents, Musician Forge Songs.
echo You can now delete this Musician Forge folder too. To install again, download Musician Forge and run
echo Install or Update Musician Forge.
:done
set /p "MF_ENTER=Press Enter to close this window. "
endlocal
