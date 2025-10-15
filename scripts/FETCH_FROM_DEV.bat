@echo off
REM Fetch data from DEV environment
REM Purpose:
REM   Convenience wrapper for fetch_from_dev.py so non-technical users can double-click.
REM Usage:
REM   Requires Python in PATH plus network access to amichat.dev.amivero-solutions.com.
REM Side Effects:
REM   - Downloads latest development export into the data/ directory.
echo ================================================================================
echo   FETCHING FROM DEV ENVIRONMENT
echo   https://amichat.dev.amivero-solutions.com
echo ================================================================================
echo.

cd /d "%~dp0"

python fetch_from_dev.py

echo.
pause
