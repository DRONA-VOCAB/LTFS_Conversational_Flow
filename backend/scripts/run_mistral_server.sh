#!/bin/bash
# Script to run Mistral server on port 5001

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Go to project root (two levels up from scripts/)
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Set environment variables
export MISTRAL_PORT=5001
export MISTRAL_HOST=0.0.0.0
export MISTRAL_MODEL_PATH="${HOME}/mistral_models/7B-Instruct-v0.3"

# Check if CUDA is available
if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi &> /dev/null; then
        export MISTRAL_DEVICE=cuda
        echo "✅ CUDA detected, using GPU"
    else
        export MISTRAL_DEVICE=cpu
        echo "⚠️  CUDA not available, using CPU"
    fi
else
    export MISTRAL_DEVICE=cpu
    echo "⚠️  nvidia-smi not found, using CPU"
fi

echo "🚀 Starting Mistral server on port ${MISTRAL_PORT}..."
echo "📁 Model path: ${MISTRAL_MODEL_PATH}"
echo "📱 Device: ${MISTRAL_DEVICE}"
echo "📂 Project root: ${PROJECT_ROOT}"

# Run the server
python3 backend/scripts/start_mistral_server.py

