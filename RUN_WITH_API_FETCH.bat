@echo off
REM Mission Analysis Dashboard - Fetch from API and Analyze
REM This version automatically fetches data from OpenWebUI API

echo ================================================================================
echo   MISSION ANALYSIS DASHBOARD (API MODE)
echo   Fetching latest data from OpenWebUI...
echo ================================================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Install required package if needed
echo Checking dependencies...
python -c "import requests" 2>nul
if errorlevel 1 (
    echo Installing required package: requests
    pip install requests
    echo.
)

REM Fetch data from API and run analysis
python fetch_from_openwebui.py

echo.
echo ================================================================================
echo Complete! Dashboard should open in your browser.
echo ================================================================================
echo.
pause

