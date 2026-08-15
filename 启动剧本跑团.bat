@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   Paotuan - AI Interactive Story Client
echo ==========================================
echo.

rem ---- locate Python 3.12+ ----
set "PY="
where python >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PY=py -3"
    )
)
if not defined PY (
    echo [ERROR] Python 3.12+ not found on this PC.
    echo         Please install it from https://www.python.org/ and rerun.
    echo.
    pause
    exit /b 1
)

rem ---- create virtualenv on first run ----
if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Creating virtual environment ...
    %PY% -m venv .venv
    if errorlevel 1 goto :fail
)

rem ---- install deps if missing ----
".venv\Scripts\python.exe" -c "import paotuan, PySide6" >nul 2>nul
if errorlevel 1 (
    echo [SETUP] Installing dependencies, one moment ...
    ".venv\Scripts\python.exe" -m pip install -q --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -q -e .
    if errorlevel 1 goto :fail
)

rem ---- build demo story zip if missing ----
if not exist "examples\demo_story.zip" (
    echo [SETUP] Building demo story ...
    ".venv\Scripts\python.exe" examples\build_demo.py
)

echo [LAUNCH] Starting Paotuan ...
".venv\Scripts\python.exe" -m paotuan --script examples\demo_story.zip
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo [ERROR] Startup failed. Please check the messages above.
echo.
pause
exit /b 1