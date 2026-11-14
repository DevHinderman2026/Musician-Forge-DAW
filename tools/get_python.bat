@echo off
rem Offers to install Python 3.14 from python.org for this Windows user with winget, Windows' own installer tool,
rem which needs no administrator rights (Russell, 23 Oct 2026). "Install or Update Musician Forge" calls it when
rem find_base_python.bat found no Python that Musician Forge can use: none at all, or only one too new, too old,
rem ARM64 or 32-bit. The Microsoft Store's Python 3.12 or 3.13 is used as it is from 0.9.13, so it is not asked for. Sets MF_BASE_PY when it worked; otherwise the caller says how to
rem install Python by hand. Every step goes to MF_PY_LOG, which install.py copies into logs\install_log.txt.
rem From 0.9.14 MF_PY_NOTE says in one sentence how the offer ended, for the message the installer opens in Notepad,
rem and winget reads from nul, so it cannot wait for a key while its words go to the log.
rem winget's package for python.org's Python 3.14: its x64 installer, for this user only.
set "MF_WINGET_ID=Python.Python.3.14"
if not defined MF_PY_LOG set "MF_PY_LOG=%TEMP%\musicianforge_python_setup.txt"
set "MF_PY_NOTE="
echo.
if defined MF_PY_REASON echo %MF_PY_REASON%
if not defined MF_PY_REASON echo No Python was found on this computer.
>> "%MF_PY_LOG%" echo No Python that Musician Forge can use was found. Other Python: "%MF_ANY_PY%". Reason: %MF_PY_REASON%
where winget > nul 2>&1
if errorlevel 1 goto :no_winget
title Musician Forge installer: a question, press Y for yes or N for no
choice /c YN /n /m "Musician Forge needs Python from python.org. Install Python 3.14 from python.org now? Press Y for yes or N for no."
if errorlevel 2 goto :declined
rem Control+C at the question ends with 0: that is no answer, so nothing is installed.
if not errorlevel 1 goto :declined
title Musician Forge installer: installing Python, please wait
echo Installing Python 3.14 from python.org with winget. This takes a minute or two. Please wait.
>> "%MF_PY_LOG%" echo Running: winget install --id %MF_WINGET_ID% --exact --scope user --architecture x64 --silent
winget install --id %MF_WINGET_ID% --exact --scope user --architecture x64 --silent --accept-package-agreements --accept-source-agreements >> "%MF_PY_LOG%" 2>&1 < nul
>> "%MF_PY_LOG%" echo winget finished with exit code %errorlevel%.
call "%~dp0find_base_python.bat"
if not defined MF_BASE_PY goto :failed
echo Python 3.14 is installed. The installation of Musician Forge goes on.
>> "%MF_PY_LOG%" echo Python installed by winget: "%MF_BASE_PY%"
goto :eof

:no_winget
echo Windows' installer tool, winget, is not on this computer, so Python cannot be installed from here.
set "MF_PY_NOTE=Windows' installer tool, winget, is not on this computer, so the installer could not install Python itself."
>> "%MF_PY_LOG%" echo winget was not found.
goto :eof

:declined
echo Python was not installed.
set "MF_PY_NOTE=The installer offered to install Python 3.14 from python.org, and the answer was no."
>> "%MF_PY_LOG%" echo The offer to install Python was declined.
goto :eof

:failed
echo Python 3.14 could not be installed with winget.
set "MF_PY_NOTE=The installer tried to install Python 3.14 from python.org with winget, and that did not work."
>> "%MF_PY_LOG%" echo After winget, there is still no Python that Musician Forge can use.
goto :eof
