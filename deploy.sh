#!/bin/bash
set -e

BASE_DIR=$(pwd)
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/app.log"

mkdir -p "$LOG_DIR"

# =========================
# SSL CONFIG (ABSOLUTE PATHS ONLY)
# =========================
SSL_CERT_FILE="/opt/ssl/fullchain.pem"
SSL_KEY_FILE="/opt/ssl/privkey.pem"

# =========================
# Load .env from root
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
# START FASTAPI WITH SSL
# =========================
echo "Starting FastAPI server with HTTPS..."

nohup uvicorn main:app \
    --host 0.0.0.0 \
    --port 8001 \
    --ssl-certfile "$SSL_CERT_FILE" \
    --ssl-keyfile "$SSL_KEY_FILE" \
    > "$LOG_FILE" 2>&1 &

echo "✅ Application running with HTTPS"
echo "🌐 URL: https://server6.vo-cab.dev:8000/"
echo "📄 Logs: $LOG_FILE"
echo "🆔 PID: $!"
