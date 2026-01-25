@echo off
setlocal

:: --- 1. Navigate to the script's directory (Root of Aging-V2) ---
cd /d "%~dp0"

:: --- 2. Check for Virtual Environment & Auto-Setup ---
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Virtual environment not found.
    echo [INFO] Initiating automated setup...

    if exist "Setup\setup_windows.bat" (
        :: The setup script expects to be run from inside the Setup folder
        pushd Setup
        call setup_windows.bat
        popd
        
        :: Force return to root just in case
        cd /d "%~dp0"
    ) else (
        echo [ERROR] Setup script not found at Setup\setup_windows.bat
        pause
        exit /b 1
    )

    echo [INFO] Setup complete. Launching application...
)

:: --- 3. Activate Virtual Environment ---
:: Double check if venv exists now
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Setup failed to create virtual environment.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"

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
