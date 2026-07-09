@echo off
REM AI Attorney v3 — Clause Validation Cascade Engine
cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo ERROR: Python is not installed or not on PATH.
    echo Download Python 3.12 from https://www.python.org/downloads/
    echo Make sure to CHECK "Add python.exe to PATH" during install.
    pause
    exit /b 1
)

REM Create venv if needed
IF NOT EXIST venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate

REM Install dependencies
echo Installing dependencies...
pip install -q -r requirements.txt

REM Check for LibreOffice (needed for real track changes and PDF)
where soffice >nul 2>&1
IF ERRORLEVEL 1 (
    echo.
    echo NOTE: LibreOffice not found.
    echo For real Word track changes and PDF output, install LibreOffice:
    echo   https://www.libreoffice.org/download/
    echo.
    echo The application will still work without it — you will get visual
    echo redlines in DOCX format instead of Word-compatible track changes.
    echo.
)

echo.
echo ============================================================
echo   AI Attorney v3 — Clause Validation Cascade Engine
echo   Starting on http://localhost:8083
echo   Press Ctrl+C to stop
echo ============================================================
echo.

uvicorn app:app --host 0.0.0.0 --port 8083
