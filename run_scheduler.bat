@echo off
REM NCSAA Basketball Scheduling System - Windows Batch Script
REM This script runs the basketball game scheduler

echo ============================================================
echo NCSAA Basketball Scheduling System
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

REM Check if dependencies are installed
echo Checking dependencies...
python -c "import gspread, ortools" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo.
echo Starting scheduler...
echo.

REM Run the scheduler
python main.py %*

echo.
echo ============================================================
echo Scheduling process completed
echo ============================================================
pause
