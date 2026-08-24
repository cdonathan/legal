@echo off
echo ============================================================
echo   SeedJura Agreement Summary - Build Executable
echo ============================================================
echo.

REM Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [2/3] Building executable with PyInstaller...
python build_exe.py
if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Build complete!
echo.
echo Output folder: %~dp0dist\SeedJura\
echo Executable:    %~dp0dist\SeedJura\SeedJura.exe
echo.
echo To test: run dist\SeedJura\SeedJura.exe
echo To distribute: zip the entire dist\SeedJura\ folder.
echo.
echo IMPORTANT: Users need an OpenAI API key.
echo Place it in: C:\seedJura\openai_api_key.txt
echo Or set environment variable: OPENAI_API_KEY
echo.
pause
