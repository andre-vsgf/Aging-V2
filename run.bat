@echo off
setlocal

:: --- 1. Navigate to the script's directory ---
cd /d "%~dp0"

:: --- 2. Check for Virtual Environment ---
:: FIX: Removed parentheses around .venv in the echo command to avoid syntax errors
if not exist ".venv" (
    echo [ERROR] Virtual environment .venv not found.
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
set QT_PLUGIN_PATH=
set QML2_IMPORT_PATH=

:: --- 5. Run the Application ---
echo Starting Application...
python "App\App.py"

:: --- 6. Handle Exit ---
if errorlevel 1 (
    echo.
    echo [APP CRASHED] The application exited with an error.
    pause
)

endlocal
