@echo off
setlocal

:: --- 1. Navigate to the script's directory ---
:: This ensures the script runs from the repo root, even if run as Admin
cd /d "%~dp0"

:: --- 2. Check for Virtual Environment ---
if not exist ".venv" (
    echo [ERROR] Virtual environment (.venv) not found.
    echo Please run the Setup script first or create the env manually.
    pause
    exit /b 1
)

:: --- 3. Activate Virtual Environment ---
echo Activating virtual environment...
call ".venv\Scripts\activate.bat"

if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

:: --- 4. Clear Qt Environment Variables ---
:: Similar to your Linux script, this prevents conflicts if you have
:: other Qt/Python installations (like Anaconda) globally installed.
set QT_PLUGIN_PATH=
set QML2_IMPORT_PATH=

:: --- 5. Run the Application ---
echo Starting Application...
python "App\App.py"

:: --- 6. Handle Exit ---
:: If the app crashes, pause so you can read the error message.
:: If it closes normally, the window will close automatically.
if errorlevel 1 (
    echo.
    echo [APP CRASHED] The application exited with an error.
    pause
)

endlocal
