@echo off
setlocal EnableDelayedExpansion
title Loan Easier OCR Portal
color 0A

rem Ensure the script runs in its own directory
cd /d "%~dp0"

echo ==========================================
echo       Loan Easier - Auto Setup ^& Run
echo ==========================================

rem Check if project files exist
IF NOT EXIST "run_server.py" (
    color 0C
    echo [ERROR] run_server.py not found! 
    echo Did you only copy the .bat file? You must copy the ENTIRE "Loan Easier" folder.
    pause
    exit /b
)

rem Check if Python is installed
python --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 GOTO PYTHON_INSTALLED

color 0E
echo [WARNING] Python is not installed or not in PATH!
echo [INFO] Downloading Python 3.11 automatically...
curl -L -o python-installer.exe https://www.python.org/ftp/python/3.11.8/python-3.11.8-amd64.exe

IF NOT EXIST "python-installer.exe" (
    color 0C
    echo [ERROR] Failed to download Python. Please check your internet connection.
    pause
    exit /b
)

echo [INFO] Installing Python (This may take a minute). Please wait...
start /wait python-installer.exe /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
echo [INFO] Python Installation Complete!
del python-installer.exe

rem Inject Python into the current session's PATH
set "PATH=%USERPROFILE%\AppData\Local\Programs\Python\Python311\Scripts\;%USERPROFILE%\AppData\Local\Programs\Python\Python311\;%PATH%"

:PYTHON_INSTALLED
color 0A

rem Validate existing VENV
IF NOT EXIST "venv" GOTO CREATE_VENV

venv\Scripts\python.exe -c "import sys" >nul 2>&1
IF %ERRORLEVEL% EQU 0 GOTO VENV_OK

echo [WARNING] Broken Virtual Environment detected (likely copied from another folder).
echo [INFO] Cleaning up broken environment...
rmdir /s /q venv

:CREATE_VENV
echo [INFO] Creating virtual environment...
python -m venv venv

:VENV_OK
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

echo [INFO] Checking and installing dependencies...
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q

echo [INFO] Configuring PDF Engine (Chromium)...
playwright install chromium

echo [INFO] Starting the Server...
python run_server.py

IF %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo [ERROR] The server crashed or failed to start.
    echo Check the error message above for details.
)

pause
