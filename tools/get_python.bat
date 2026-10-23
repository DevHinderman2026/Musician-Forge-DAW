@echo off
rem Offers to install Python 3.14 from python.org for this Windows user with winget, Windows' own installer tool,
rem which needs no administrator rights (Russell, 23 Oct 2026). "Install or Update Musician Forge" calls it when
rem find_base_python.bat found no Python that Musician Forge can use: none at all, only the Microsoft Store's, or
rem only one too new, too old, ARM64 or 32-bit. Sets MF_BASE_PY when it worked; otherwise the caller says how to
rem install Python by hand. Every step goes to MF_PY_LOG, which install.py copies into logs\install_log.txt.
rem winget's package for python.org's Python 3.14: its x64 installer, for this user only.
set "MF_WINGET_ID=Python.Python.3.14"
if not defined MF_PY_LOG set "MF_PY_LOG=%TEMP%\musicianforge_python_setup.txt"
echo.
if defined MF_PY_REASON echo %MF_PY_REASON%
if not defined MF_PY_REASON echo No Python was found on this computer.
>> "%MF_PY_LOG%" echo No Python that Musician Forge can use was found. Other Python: %MF_ANY_PY%. Reason: %MF_PY_REASON%
where winget > nul 2>&1
if errorlevel 1 goto :no_winget
choice /c YN /n /m "Musician Forge needs Python from python.org. Install Python 3.14 from python.org now? Press Y for yes or N for no."
if errorlevel 2 goto :declined
rem Control+C at the question ends with 0: that is no answer, so nothing is installed.
if not errorlevel 1 goto :declined
echo Installing Python 3.14 from python.org with winget. This takes a minute or two. Please wait.
>> "%MF_PY_LOG%" echo Running: winget install --id %MF_WINGET_ID% --exact --scope user --architecture x64 --silent
winget install --id %MF_WINGET_ID% --exact --scope user --architecture x64 --silent --accept-package-agreements --accept-source-agreements >> "%MF_PY_LOG%" 2>&1
>> "%MF_PY_LOG%" echo winget finished with exit code %errorlevel%.
call "%~dp0find_base_python.bat"
if not defined MF_BASE_PY goto :failed
echo Python 3.14 is installed. The installation of Musician Forge goes on.
>> "%MF_PY_LOG%" echo Python installed by winget: %MF_BASE_PY%
goto :eof

:no_winget
echo Windows' installer tool, winget, is not on this computer, so Python cannot be installed from here.
>> "%MF_PY_LOG%" echo winget was not found.
goto :eof

:declined
echo Python was not installed.
>> "%MF_PY_LOG%" echo The offer to install Python was declined.
goto :eof

:failed
echo Python 3.14 could not be installed with winget.
>> "%MF_PY_LOG%" echo After winget, there is still no Python that Musician Forge can use.
goto :eof
