@echo off
REM AI Attorney v3 — Clause Validation Cascade Engine
cd /d "%~dp0"

IF NOT EXIST venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate

echo Installing dependencies...
pip install -q -r requirements.txt

echo.
echo Starting AI Attorney v3 on http://localhost:8083
echo Press Ctrl+C to stop
echo.

uvicorn app:app --host 0.0.0.0 --port 8083
