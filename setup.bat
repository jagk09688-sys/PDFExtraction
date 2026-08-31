@echo off
REM Windows Setup Script for PDF Extraction Project
REM This script sets up everything needed to run the Flask app

echo.
echo ============================================
echo  PDF Extraction Project - Windows Setup
echo ============================================
echo.

REM Check Python
echo [1/4] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)
echo OK: Python found

REM Create virtual environment
echo.
echo [2/4] Creating virtual environment...
if not exist venv (
    python -m venv venv
    echo OK: Virtual environment created
) else (
    echo OK: Virtual environment already exists
)

REM Activate virtual environment
echo.
echo [3/4] Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo OK: Dependencies installed

REM Check for Poppler
echo.
echo [4/4] Setting up Poppler (required for PDF conversion)...
where pdftoimage >nul 2>&1
if errorlevel 1 (
    echo.
    echo Poppler is not found in PATH.
    echo Attempting automatic installation...
    echo.
    
    REM Download and extract Poppler automatically
    powershell -Command "& {
        $url = 'https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0/Release-24.08.0.zip'
        $zipFile = 'poppler.zip'
        $extractPath = 'poppler-windows'
        
        Write-Host 'Downloading Poppler...'
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $url -OutFile $zipFile
            Write-Host 'Extracting Poppler...'
            Expand-Archive -Path $zipFile -DestinationPath $extractPath
            Remove-Item $zipFile
            Write-Host 'Poppler installed successfully!'
            Write-Host 'Adding Poppler to PATH...'
        } catch {
            Write-Host 'Failed to download Poppler automatically.'
            Write-Host 'Please download from: https://github.com/oschwartz10612/poppler-windows/releases/'
            Write-Host 'Extract to: poppler-windows'
            Exit 1
        }
    }"
    
    if errorlevel 1 (
        echo.
        echo ERROR: Could not download Poppler
        echo MANUAL SOLUTION:
        echo 1. Download from: https://github.com/oschwartz10612/poppler-windows/releases/
        echo 2. Extract the zip file to: poppler-windows (in this directory)
        echo 3. Re-run this script
        pause
        exit /b 1
    )
) else (
    echo OK: Poppler found in PATH
)

REM Create static/output directory
if not exist static\output (
    mkdir static\output
)

echo.
echo ============================================
echo  Setup Complete!
echo ============================================
echo.
echo To start the Flask app, run:
echo   python app.py
echo.
echo Then open: http://127.0.0.1:5000/
echo.
echo To deactivate the virtual environment later, type:
echo   deactivate
echo.
pause
