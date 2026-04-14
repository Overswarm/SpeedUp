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

:: Check ffmpeg — first system PATH, then local copy
set "FFMPEG_LOCAL=%~dp0ffmpeg\bin"
ffmpeg -version >nul 2>&1
if %errorlevel% equ 0 (
    goto :ffmpeg_ok
)
:: Check for a local copy bundled next to this script
if exist "%FFMPEG_LOCAL%\ffmpeg.exe" (
    set "PATH=%FFMPEG_LOCAL%;%PATH%"
    goto :ffmpeg_ok
)

:: ffmpeg not found anywhere — offer to download it automatically
echo [WARNING] ffmpeg is not installed.
echo.
echo  SpeedUp requires ffmpeg to process audio files.
echo  It can be downloaded automatically (~90 MB).
echo.
set /p DOWNLOAD_CHOICE="  Download ffmpeg now? (Y/N): "
if /i "%DOWNLOAD_CHOICE%" neq "Y" (
    echo.
    echo  You can install ffmpeg manually later:
    echo    winget install Gyan.FFmpeg
    echo    -- or --
    echo    choco install ffmpeg
    echo.
    pause
    exit /b 1
)

echo.
echo  Downloading ffmpeg...
set "FFMPEG_ZIP=%TEMP%\ffmpeg-release-essentials.zip"
set "FFMPEG_EXTRACT=%TEMP%\ffmpeg_extract"
set "FFMPEG_URL=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

:: Download using PowerShell (available on all modern Windows)
powershell -NoProfile -Command ^
    "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; " ^
    "Invoke-WebRequest -Uri '%FFMPEG_URL%' -OutFile '%FFMPEG_ZIP%'" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Download failed. Check your internet connection.
    echo         You can install manually: winget install Gyan.FFmpeg
    pause
    exit /b 1
)

echo  Extracting...
:: Clean up any previous extraction
if exist "%FFMPEG_EXTRACT%" rmdir /s /q "%FFMPEG_EXTRACT%"
powershell -NoProfile -Command ^
    "Expand-Archive -Path '%FFMPEG_ZIP%' -DestinationPath '%FFMPEG_EXTRACT%' -Force" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Extraction failed.
    pause
    exit /b 1
)

:: The zip contains a folder like "ffmpeg-7.1-essentials_build" — find it
:: and move its contents into a clean "ffmpeg" folder next to this script
set "FFMPEG_DEST=%~dp0ffmpeg"
if exist "%FFMPEG_DEST%" rmdir /s /q "%FFMPEG_DEST%"
for /d %%D in ("%FFMPEG_EXTRACT%\ffmpeg-*") do (
    move "%%D" "%FFMPEG_DEST%" >nul
)

:: Clean up temp files
del /q "%FFMPEG_ZIP%" 2>nul
rmdir /s /q "%FFMPEG_EXTRACT%" 2>nul

:: Verify it worked
if not exist "%FFMPEG_DEST%\bin\ffmpeg.exe" (
    echo [ERROR] Something went wrong — ffmpeg.exe not found after extraction.
    pause
    exit /b 1
)

echo  ffmpeg installed successfully to: %FFMPEG_DEST%
set "PATH=%FFMPEG_DEST%\bin;%PATH%"

:ffmpeg_ok
echo  ffmpeg OK.
echo.

:: Check and install Python dependencies
echo [1/2] Checking dependencies...
python -c "import PyQt6" >nul 2>&1
if %errorlevel% neq 0 (
    echo       PyQt6 not found. Installing...
    python -m pip install PyQt6 --quiet
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install PyQt6.
        pause
        exit /b 1
    )
)

python -c "import pydub" >nul 2>&1
if %errorlevel% neq 0 (
    echo       pydub not found. Installing...
    python -m pip install pydub --quiet
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
