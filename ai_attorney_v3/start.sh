#!/bin/bash
# AI Attorney v3 — Clause Validation Cascade Engine
cd "$(dirname "$0")"

# Install/update dependencies if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

echo ""
echo "Starting AI Attorney v3 on http://localhost:8083"
echo "Press Ctrl+C to stop"
echo ""

uvicorn app:app --host 0.0.0.0 --port 8083
