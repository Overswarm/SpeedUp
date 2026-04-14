@echo off
title SpeedUp - Bulk Audio Speed Changer
echo.
echo  ========================================
echo   SpeedUp - Bulk Audio Speed Changer
echo  ========================================
echo.

:: Check Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo         Download it from: https://www.python.org/downloads/
    echo         Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

:: Check ffmpeg is installed
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] ffmpeg is not installed or not found.
    echo.
    echo  SpeedUp requires ffmpeg to process audio files.
    echo.
    echo  EASIEST METHOD (recommended):
    echo    Open a terminal and run one of these commands:
    echo      winget install Gyan.FFmpeg
    echo      choco install ffmpeg
    echo    Then close and reopen this script.
    echo.
    echo  MANUAL METHOD:
    echo    1. Go to: https://www.gyan.dev/ffmpeg/builds/
    echo    2. Download "ffmpeg-release-essentials.zip"
    echo    3. Extract the zip somewhere permanent, e.g. C:\ffmpeg
    echo    4. You need to tell Windows where to find ffmpeg:
    echo         - Press Win+R, type "sysdm.cpl" and press Enter
    echo         - Go to the "Advanced" tab
    echo         - Click "Environment Variables" at the bottom
    echo         - Under "User variables", find "Path" and click Edit
    echo         - Click "New" and paste the path to the bin folder
    echo           inside your extracted zip, e.g. C:\ffmpeg\bin
    echo         - Click OK on all windows
    echo    5. Close and reopen this script.
    echo.
    pause
    exit /b 1
)

:: Check and install Python dependencies
echo [1/2] Checking dependencies...
python -c "import PyQt6" >nul 2>&1
if %errorlevel% neq 0 (
    echo       PyQt6 not found. Installing...
    pip install PyQt6 --quiet
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install PyQt6.
        pause
        exit /b 1
    )
)

python -c "import pydub" >nul 2>&1
if %errorlevel% neq 0 (
    echo       pydub not found. Installing...
    pip install pydub --quiet
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install pydub.
        pause
        exit /b 1
    )
)

echo       All dependencies OK.
echo.

:: Launch the application
echo [2/2] Launching SpeedUp...
echo.
python "%~dp0speedup.py"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] SpeedUp exited with an error.
    pause
)
