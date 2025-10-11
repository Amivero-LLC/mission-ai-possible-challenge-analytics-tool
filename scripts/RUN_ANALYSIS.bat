@echo off
REM Mission Analysis Dashboard - Quick Run Script
REM Double-click this file to run the analysis and open the dashboard

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

