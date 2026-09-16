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

rem Check if Tesseract-OCR is installed
IF EXIST "C:\Program Files\Tesseract-OCR\tesseract.exe" GOTO TESSERACT_INSTALLED
IF EXIST "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" GOTO TESSERACT_INSTALLED
IF EXIST "%USERPROFILE%\AppData\Local\Programs\Tesseract-OCR\tesseract.exe" GOTO TESSERACT_INSTALLED

color 0E
echo [WARNING] Tesseract-OCR is not installed!
echo [INFO] Downloading Tesseract-OCR automatically (Required for image processing)...
curl -L -o tesseract-installer.exe https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe

IF NOT EXIST "tesseract-installer.exe" (
    color 0C
    echo [ERROR] Failed to download Tesseract-OCR.
    pause
    exit /b
)

echo [INFO] Installing Tesseract-OCR silently. Please wait...
start /wait tesseract-installer.exe /S
echo [INFO] Tesseract-OCR Installation Complete!
del tesseract-installer.exe

:TESSERACT_INSTALLED
color 0A

rem Ensure Bengali and English language packs are present locally
IF NOT EXIST "tessdata" mkdir tessdata
IF NOT EXIST "tessdata\eng.traineddata" (
    echo [INFO] Downloading English OCR Data...
    curl -L -o tessdata\eng.traineddata https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata
)
IF NOT EXIST "tessdata\ben.traineddata" (
    echo [INFO] Downloading Bengali OCR Data...
    curl -L -o tessdata\ben.traineddata https://github.com/tesseract-ocr/tessdata/raw/main/ben.traineddata
)

rem Point Tesseract to use our local language models
set "TESSDATA_PREFIX=%~dp0tessdata"

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
