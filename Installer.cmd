@echo off
rem AI Kit launcher for Windows: finds Python 3.9 or newer, then hands over to scripts\launcher.py, which installs the kit
rem in its private environment (%USERPROFILE%\.ai-kit\runtime) and opens the installer (the menu when no argument is given).
rem Command prompt only: no PowerShell, no administrator rights, no change to the system, the PATH or the execution policy.
rem Equivalent command, for IT: python -I scripts\launcher.py followed by setup, update, doctor or uninstall, run from this folder.
setlocal
set "KIT_DIR=%~dp0."

rem Python: py -3 (Python launcher), then python, then python3. The Microsoft Store alias without Python answers 9009: treated as absent.
set "KIT_PY="
set "KIT_FOUND="
call :try_python py -3
if not defined KIT_PY call :try_python python
if not defined KIT_PY call :try_python python3
if defined KIT_PY goto :launch
echo.
if "%KIT_FOUND%"=="old" (
  echo The Python found is older than 3.9: the AI Kit needs Python 3.9 or newer ^(3.11 recommended^).
) else if "%KIT_FOUND%"=="blocked" (
  echo Python is present but could not be started: a security policy or an incomplete installation may prevent it.
) else (
  echo Python 3.9 or newer was not found ^(commands py, python, python3^).
)
echo What to ask IT support: Python 3.9 or newer ^(3.11 recommended^) with its standard venv and pip modules, usable by your
echo standard account from a command prompt, as provided or approved by the company ^(software centre^). Then run Installer.cmd again.
set "KIT_CODE=2"
goto :end

:launch
rem The current folder stays the user's: a relative path (--json, --home) resolves there, not in the kit.
rem scripts\launcher.py prepares the private environment (git pull first for update in a clone), then runs the kit.
rem -I: no module from the current folder or PYTHONPATH can be imported in place of the kit's.
rem No parenthesised block around %*: a ")" in an argument (C:\Program Files (x86)) would close it.
%KIT_PY% -I "%KIT_DIR%\scripts\launcher.py" %*
set "KIT_CODE=%ERRORLEVEL%"

:end
rem Opened by a double-click (no argument): keep the window open to read the result. AI_KIT_NO_PAUSE=1 for automation.
if "%~1"=="" if not "%AI_KIT_NO_PAUSE%"=="1" (
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
