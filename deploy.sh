#!/bin/bash
set -e

BASE_DIR=$(pwd)
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/app.log"

# =========================
# SERVER CONFIGURATION
# =========================
SERVER_IP="27.111.72.55"
SERVER_PORT="8001"

mkdir -p "$LOG_DIR"

# =========================
# SSL CONFIG - Let's Encrypt (from certs directory)
# =========================
# Use Let's Encrypt certificates from project certs directory
CERTS_DIR="$BASE_DIR/certs"
SSL_CERT_FILE="$CERTS_DIR/fullchain.pem"
SSL_KEY_FILE="$CERTS_DIR/privkey.pem"

if [ -f "$SSL_CERT_FILE" ] && [ -f "$SSL_KEY_FILE" ]; then
    echo "✅ Using Let's Encrypt certificate from certs directory"
else
    echo "⚠️  Let's Encrypt certificate not found in certs directory"
    echo "   Run ./setup_letsencrypt.sh to set up certificates"
    SSL_CERT_FILE=""
    SSL_KEY_FILE=""
fi

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
# SSL CERTIFICATE PERMISSIONS
# =========================
if [ -f "$SSL_CERT_FILE" ] && [ -f "$SSL_KEY_FILE" ]; then
    echo "Checking SSL certificate permissions..."
    CURRENT_USER=$(whoami)
    
    # Ensure certificates are readable by current user
    if [ ! -r "$SSL_CERT_FILE" ] || [ ! -r "$SSL_KEY_FILE" ]; then
        echo "Fixing SSL certificate permissions..."
        chmod 644 "$SSL_CERT_FILE" 2>/dev/null || true
        chmod 600 "$SSL_KEY_FILE" 2>/dev/null || true
    fi
    
    # Verify permissions
    if [ -r "$SSL_CERT_FILE" ] && [ -r "$SSL_KEY_FILE" ]; then
        echo "✅ SSL certificates are accessible"
    else
        echo "⚠️  Warning: SSL certificates not readable"
        echo "   Run: chmod 644 $SSL_CERT_FILE && chmod 600 $SSL_KEY_FILE"
    fi
else
    echo "⚠️  Warning: SSL certificate files not found at:"
    echo "   Certificate: $SSL_CERT_FILE"
    echo "   Private Key: $SSL_KEY_FILE"
    echo "   Server will start without HTTPS"
    SSL_CERT_FILE=""
    SSL_KEY_FILE=""
fi

# =========================
# START FASTAPI WITH SSL
# =========================
if [ -n "$SSL_CERT_FILE" ] && [ -n "$SSL_KEY_FILE" ]; then
    echo "Starting FastAPI server with HTTPS..."
    SSL_ARGS="--ssl-certfile $SSL_CERT_FILE --ssl-keyfile $SSL_KEY_FILE"
else
    echo "Starting FastAPI server without HTTPS..."
    SSL_ARGS=""
fi

nohup uvicorn main:app \
    --host 0.0.0.0 \
    --port $SERVER_PORT \
    $SSL_ARGS \
    > "$LOG_FILE" 2>&1 &

if [ -n "$SSL_CERT_FILE" ] && [ -n "$SSL_KEY_FILE" ]; then
    echo "✅ Application running with HTTPS"
    echo "🌐 URL: https://${SERVER_IP}:${SERVER_PORT}/"
else
    echo "✅ Application running with HTTP"
    echo "🌐 URL: http://${SERVER_IP}:${SERVER_PORT}/"
fi
echo "📄 Logs: $LOG_FILE"
echo "🆔 PID: $!"
