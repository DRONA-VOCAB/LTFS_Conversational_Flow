#!/bin/bash
set -e

echo "Starting minimal deploy..."

# Use python3 (assumes 3.11/3.12 is already available)
PYTHON_CMD="python3"

# Create/refresh venv
if [ -d "venv" ]; then
  echo "Removing existing venv..."
  rm -rf venv
fi
echo "Creating venv..."
$PYTHON_CMD -m venv venv
source venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing requirements..."
pip install -r requirements.txt

echo "Done. Run the app with:"
echo "source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000"

