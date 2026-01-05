#!/bin/bash

# Exit on error
set -e

BASE_DIR=$(pwd)
LOG_DIR="$BASE_DIR/logs"

FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_LOG="$LOG_DIR/backend.log"

echo "Starting LTFS deployment..."

# Create logs directory
mkdir -p "$LOG_DIR"

# =========================
# FRONTEND (React)
# =========================
echo "Starting frontend..."

cd "$BASE_DIR/frontend"

# Install node modules if not present
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Run frontend in background
nohup npm run dev > "$FRONTEND_LOG" 2>&1 &

FRONTEND_PID=$!
echo "Frontend started with PID $FRONTEND_PID"

# =========================
# BACKEND (FastAPI)
# =========================
echo "Starting backend..."

cd "$BASE_DIR/backend"

# Install python dependencies
pip install -r req.txt

cd app

# Run backend in background
nohup uvicorn main:app --reload > "$BACKEND_LOG" 2>&1 &

BACKEND_PID=$!
echo "Backend started with PID $BACKEND_PID"

# =========================
# DONE
# =========================
echo "Deployment complete!"
echo "Frontend log: $FRONTEND_LOG"
echo "Backend log: $BACKEND_LOG"
