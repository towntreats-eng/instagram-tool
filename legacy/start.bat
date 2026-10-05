@echo off
title DM Flow - Instagram Automation for D2C
color 0f
echo ================================================================
echo        DM FLOW - INSTAGRAM AUTOMATION SUITE
echo ================================================================
echo.
echo  [1/2] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from python.org and try again.
    pause
    exit /b 1
)

echo  [2/2] Launching DM Flow...
echo.
python run.py
if %errorlevel% neq 0 (
    echo.
    echo [INFO] Running pip install -r requirements.txt in case of missing packages...
    pip install -r requirements.txt
    python run.py
)
pause
