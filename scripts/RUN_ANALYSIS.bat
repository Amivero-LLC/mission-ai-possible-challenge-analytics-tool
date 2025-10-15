@echo off
REM Mission Analysis Dashboard - Quick Run Script
REM Purpose:
REM   Launches the legacy CLI analyzer against the latest export in data/.
REM Usage:
REM   Double-click in Explorer or run from cmd/powershell.
REM Dependencies:
REM   - Python in PATH
REM   - data/all-chats-export-*.json present
REM Side Effects:
REM   - Generates/refreshes public/mission_dashboard.html

echo ================================================================================
echo   MISSION ANALYSIS DASHBOARD
echo   Analyzing latest chat export...
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

REM Run the analysis
python analyze_missions.py

echo.
echo ================================================================================
echo Analysis complete! Dashboard should open in your browser.
echo ================================================================================
echo.
pause
