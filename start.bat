@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

where powershell >nul 2>nul
if errorlevel 1 (
    echo PowerShell is required to start MaxKB on Windows.
    echo Install or enable PowerShell, then run this file again.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%scripts\dev-all.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Startup exited with code %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
