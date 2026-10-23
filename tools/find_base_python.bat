@echo off
rem Sets MF_BASE_PY to a Python that Musician Forge can use: python.org's 64-bit Python 3.14, 3.13 or 3.12, newest
rem first (check_python.py says why others cannot be used). Never Musician Forge's own environment.
rem When none is found, MF_BASE_PY stays empty, MF_ANY_PY is the first other Python found (Diagnose uses it) and
rem MF_PY_REASON says in words why it cannot be used, and which Python to install.
set "MF_BASE_PY="
set "MF_ANY_PY="
set "MF_PY_REASON="
set "MF_TOOLS=%~dp0"
set "MF_CHECK_OUT=%TEMP%\musicianforge_python_check.txt"
rem The py launcher of Python's install manager must never start installing a Python by itself while it is asked.
set "PYTHON_MANAGER_AUTOMATIC_INSTALL=false"
rem 1. python.org's install folders first. cmd keeps these paths right; a path printed by Python and read back with
rem for /f comes out wrong when the Windows user name has letters such as an accented e, and was not found.
for %%V in (314 313 312) do call :try "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
for %%V in (3.14 3.13 3.12) do call :try "%LOCALAPPDATA%\Python\pythoncore-%%V-64\python.exe"
for %%V in (314 313 312) do call :try "%ProgramFiles%\Python%%V\python.exe"
rem 2. The py launcher, asking for each version Musician Forge can use, then for its own choice; then "python".
for %%V in (3.14 3.13 3.12 3) do call :try_command py -%%V
call :try_command python
goto :eof

:try_command
rem A Python started by name: where it is, as it says itself.
if defined MF_BASE_PY goto :eof
set "MF_FOUND="
for /f "delims=" %%P in ('%* -c "import sys; print(sys.executable)" 2^>nul') do set "MF_FOUND=%%P"
if not defined MF_FOUND goto :eof
if not exist "%MF_FOUND%" set "MF_FOUND="
if not defined MF_FOUND goto :eof
call :try "%MF_FOUND%"
goto :eof

:try
rem One python.exe: used when check_python.py says it can be.
if defined MF_BASE_PY goto :eof
if not exist "%~1" goto :eof
if not defined MF_ANY_PY set "MF_ANY_PY=%~1"
"%~1" "%MF_TOOLS%check_python.py" > "%MF_CHECK_OUT%" 2> nul
if not "%errorlevel%"=="0" goto :rejected
set "MF_BASE_PY=%~1"
goto :eof
:rejected
if not defined MF_PY_REASON set /p MF_PY_REASON=<"%MF_CHECK_OUT%"
goto :eof
