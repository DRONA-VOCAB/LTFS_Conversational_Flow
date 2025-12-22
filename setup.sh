#!/bin/bash

# Setup script for L&T Finance Feedback Survey System

echo "🚀 Setting up L&T Finance Feedback Survey System..."
echo ""

# Check Python version (requires 3.11 or 3.12)
echo "🐍 Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo "❌ Python 3.11 or higher is required. Found Python $PYTHON_VERSION"
    echo "Installing Python 3.11..."
    sudo apt-get install -y software-properties-common
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update
    sudo apt-get install -y python3.11 python3.11-venv python3.11-dev python3.11-distutils
    PYTHON_CMD="python3.11"
elif [ "$PYTHON_MINOR" -gt 12 ]; then
    echo "❌ Python 3.13+ is not supported. Please use Python 3.11 or 3.12"
    echo "Installing Python 3.12..."
    sudo apt-get install -y software-properties-common
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update
    sudo apt-get install -y python3.12 python3.12-venv python3.12-dev python3.12-distutils
    PYTHON_CMD="python3.12"
else
    echo "✅ Python $PYTHON_VERSION is compatible"
    PYTHON_CMD="python3"
fi

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "✅ Virtual environment already exists"
    echo "⚠️  Note: If you're switching Python versions, consider removing venv and recreating it"
else
    echo "📦 Creating virtual environment with $PYTHON_CMD..."
    $PYTHON_CMD -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        exit 1
    fi
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Setup complete!"
    echo ""
    echo "To activate the virtual environment in the future, run:"
    echo "  source venv/bin/activate"
    echo ""
    echo "To run the application:"
    echo "  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    echo ""
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

