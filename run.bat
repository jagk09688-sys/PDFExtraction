@echo off
REM Quick run script for Flask app (after setup.bat has been run)
REM Double-click this file to start the server

REM Check if virtual environment exists
if not exist venv (
    echo.
    echo ERROR: Virtual environment not found
    echo.
    echo Please run setup.bat first to set up the project.
    echo.
    pause
    exit /b 1
)

REM Check if requirements are installed by trying to import flask
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Dependencies not installed properly
    echo.
    echo Please run setup.bat again to reinstall dependencies.
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment and run
call venv\Scripts\activate.bat

echo.
echo ============================================
echo  PDF Extraction App - Starting Server
echo ============================================
echo.
echo Starting Flask development server...
echo Press Ctrl+C to stop the server
echo.
echo The app will be available at:
echo   http://127.0.0.1:5000/
echo.
echo Opening in browser in 3 seconds...
echo.

timeout /t 3 /nobreak

REM Try to open browser
start http://127.0.0.1:5000/

REM Run the Flask app
python app.py
