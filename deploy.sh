#!/bin/bash
set -e

BASE_DIR=$(pwd)
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/app.log"

mkdir -p "$LOG_DIR"

# =========================
# Load .env from parent
# =========================
if [ -f "$BASE_DIR/.env" ]; then
    echo "Loading environment variables from .env"
    set -a
    source "$BASE_DIR/.env"
    set +a
else
    echo "No .env file found in root, continuing without it"
fi

# =========================
# FRONTEND BUILD
# =========================
echo "Building frontend..."
cd "$BASE_DIR/frontend"
npm install
npm run build

# =========================
# COPY FRONTEND BUILD
# =========================
echo "Copying frontend build to backend..."
rm -rf "$BASE_DIR/backend/app/static"
mkdir -p "$BASE_DIR/backend/app/static"
cp -r dist/* "$BASE_DIR/backend/app/static/"

# =========================
# BACKEND SETUP
# =========================
echo "Installing backend dependencies..."
cd "$BASE_DIR/backend"
pip install -r requirements.txt

cd app

# =========================
# START FASTAPI
# =========================
echo "Starting FastAPI server..."
nohup uvicorn main:app \
    --host 0.0.0.0 \
    --port 8001 \
    > "$LOG_FILE" 2>&1 &

echo "Application running globally"
echo "Logs: $LOG_FILE"
