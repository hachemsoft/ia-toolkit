@echo off
rem AI Kit launcher for Windows: finds Python 3.9 or newer, then runs the installer (setup when no argument is given).
rem Command prompt only: no PowerShell, no administrator rights, no change to the system or to the PATH.
rem Equivalent command, for IT: python -m installer setup, run from this folder.
setlocal
set "KIT_DIR=%~dp0."
set "KIT_ACTION=%~1"
if "%KIT_ACTION%"=="" set "KIT_ACTION=setup"

rem Python: py -3 (Python launcher), then python, then python3. The Microsoft Store alias without Python answers 9009: treated as absent.
set "KIT_PY="
set "KIT_FOUND="
call :try_python py -3
if not defined KIT_PY call :try_python python
if not defined KIT_PY call :try_python python3
if defined KIT_PY goto :run
echo.
if "%KIT_FOUND%"=="old" (
  echo The Python found is older than 3.9: the AI Kit needs Python 3.9 or newer ^(3.11 recommended^).
) else if "%KIT_FOUND%"=="blocked" (
  echo Python is present but could not be started: a security policy or an incomplete installation may prevent it.
) else (
  echo Python 3.9 or newer was not found ^(commands py, python, python3^).
)
echo What to ask IT support: Python 3.9 or newer ^(3.11 recommended^), usable by your standard account from a command prompt,
echo as provided or approved by the company ^(software centre^). Then run Installer.cmd again.
set "KIT_CODE=2"
goto :end

:run
rem update: in a git clone without local changes, fetch the new version first; never blocks the update.
if /i not "%KIT_ACTION%"=="update" goto :launch
if not exist "%KIT_DIR%\.git\" goto :launch
where git >nul 2>nul || goto :launch
git -C "%KIT_DIR%" diff --quiet || goto :local_changes
git -C "%KIT_DIR%" diff --cached --quiet || goto :local_changes
git -C "%KIT_DIR%" pull --ff-only --quiet || echo Could not fetch the new version ^(network or diverging history^): updating from the current folder. 1>&2
goto :launch
:local_changes
echo Local changes in the kit folder: no git pull; updating from the current folder. 1>&2

:launch
rem The current folder stays the user's: a relative path (--json, --home) resolves there, not in the kit.
set "KIT_PYTHONPATH=%KIT_DIR%"
if defined PYTHONPATH set "KIT_PYTHONPATH=%KIT_DIR%;%PYTHONPATH%"
set "PYTHONPATH=%KIT_PYTHONPATH%"
rem No parenthesised block around %*: a ")" in an argument (C:\Program Files (x86)) would close it.
if "%~1"=="" goto :launch_setup
%KIT_PY% -m installer %*
set "KIT_CODE=%ERRORLEVEL%"
goto :end
:launch_setup
%KIT_PY% -m installer setup
set "KIT_CODE=%ERRORLEVEL%"

:end
rem Opened by a double-click (no argument): keep the window open to read the result.
if "%~1"=="" (
  echo.
  pause
)
endlocal & exit /b %KIT_CODE%

:try_python
where %1 >nul 2>nul || exit /b 0
%* -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 3)" >nul 2>nul
if not errorlevel 1 (
  set "KIT_PY=%*"
  exit /b 0
)
if errorlevel 9009 exit /b 0
if errorlevel 3 if not errorlevel 4 (
  set "KIT_FOUND=old"
  exit /b 0
)
if not defined KIT_FOUND set "KIT_FOUND=blocked"
exit /b 0
