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
    echo [WARNING] ffmpeg is not installed or not in PATH.
    echo.
    echo  SpeedUp requires ffmpeg to process audio files.
    echo  Download it from: https://www.gyan.dev/ffmpeg/builds/
    echo    1. Download "ffmpeg-release-essentials.zip"
    echo    2. Extract the zip file
    echo    3. Add the "bin" folder to your system PATH
    echo.
    echo  Alternatively, install via winget:
    echo    winget install Gyan.FFmpeg
    echo.
    echo  Or via chocolatey:
    echo    choco install ffmpeg
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
