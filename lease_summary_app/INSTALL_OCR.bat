@echo off
echo ============================================================
echo   SeedJura - Install OCR Support (Tesseract)
echo ============================================================
echo.
echo Scanned PDFs require Tesseract OCR to read them.
echo This script downloads and installs Tesseract for Windows.
echo.
echo Digital (text-based) PDFs work WITHOUT this - only scanned
echo documents need OCR.
echo.
pause

REM Check if Tesseract is already installed
where tesseract >nul 2>&1
if not errorlevel 1 (
    echo Tesseract is already installed and on PATH.
    pause
    exit /b 0
)

if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo Tesseract is already installed at C:\Program Files\Tesseract-OCR\
    pause
    exit /b 0
)

echo.
echo Downloading Tesseract installer...
echo.

REM Download the official Tesseract Windows installer (UB Mannheim build)
set INSTALLER_URL=https://github.com/UB-Mannheim/tesseract/releases/download/v5.3.3.20231005/tesseract-ocr-w64-setup-5.3.3.20231005.exe
set INSTALLER=%TEMP%\tesseract-setup.exe

powershell -Command "Invoke-WebRequest -Uri '%INSTALLER_URL%' -OutFile '%INSTALLER%'"

if not exist "%INSTALLER%" (
    echo ERROR: Download failed.
    echo Please manually download Tesseract from:
    echo   https://github.com/UB-Mannheim/tesseract/wiki
    echo Install it to the default location, then restart SeedJura.
    pause
    exit /b 1
)

echo.
echo Running installer (install to the DEFAULT location)...
echo.
"%INSTALLER%"

echo.
echo Installation complete. Restart SeedJura to enable OCR.
echo.
pause
