@echo off
rem Sets MF_BASE_PY to the system Python (not Musician Forge's own environment).
set "MF_BASE_PY="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "MF_BASE_PY=%%P"
if defined MF_BASE_PY goto :eof
rem python.org installs (newest first) before the "python" command, which may be the Microsoft Store's
for %%V in (315 314 313 312 311 310) do if not defined MF_BASE_PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "MF_BASE_PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
if defined MF_BASE_PY goto :eof
for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "MF_BASE_PY=%%P"
goto :eof
