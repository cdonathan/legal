#!/bin/bash
# AI Attorney v3 — Clause Validation Cascade Engine
cd "$(dirname "$0")"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed."
    echo "Install with: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

# Create venv if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

# Check for LibreOffice
if ! command -v libreoffice &> /dev/null; then
    echo ""
    echo "NOTE: LibreOffice not found."
    echo "For real Word track changes and PDF output, install:"
    echo "  sudo apt install libreoffice"
    echo ""
    echo "The app will still work without it (visual redlines in DOCX)."
    echo ""
fi

echo ""
echo "============================================================"
echo "  AI Attorney v3 — Clause Validation Cascade Engine"
echo "  Starting on http://localhost:8083"
echo "  Press Ctrl+C to stop"
echo "============================================================"
echo ""

uvicorn app:app --host 0.0.0.0 --port 8083
