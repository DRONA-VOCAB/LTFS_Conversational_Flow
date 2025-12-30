#!/bin/bash

# Deploy script for L&T Finance Feedback Survey System

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./setup.sh first"
    exit 1
fi

# Activate virtual environment and run uvicorn using venv's Python
source venv/bin/activate

# Use the venv's Python directly to ensure correct interpreter
echo "🚀 Starting L&T Finance Feedback Survey API..."
echo "📍 Using Python: $(which python3)"
echo ""

# Run uvicorn using venv's Python
venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
