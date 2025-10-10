@echo off
REM Fetch data from DEV environment
echo ================================================================================
echo   FETCHING FROM DEV ENVIRONMENT
echo   https://amichat.dev.amivero-solutions.com
echo ================================================================================
echo.

cd /d "%~dp0"

python fetch_from_dev.py

echo.
pause

