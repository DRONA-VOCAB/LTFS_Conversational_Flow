#!/bin/bash
set -e

BASE_DIR=$(pwd)
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/app.log"

mkdir -p "$LOG_DIR"

# =========================
# SSL CONFIG
# =========================
SSL_DIR="$BASE_DIR/certs"
SSL_CERT_FILE="$SSL_DIR/fullchain.pem"
SSL_KEY_FILE="$SSL_DIR/privkey.pem"

# Check if certificates exist
if [ ! -f "$SSL_CERT_FILE" ] || [ ! -f "$SSL_KEY_FILE" ]; then
    echo "❌ ERROR: SSL certificates not found at $SSL_DIR"
    echo "   Expected files:"
    echo "   - $SSL_CERT_FILE"
    echo "   - $SSL_KEY_FILE"
    exit 1
fi

echo "✅ Using SSL certificates from $SSL_DIR"

# Verify certificate details
CERT_ISSUER=$(openssl x509 -in "$SSL_CERT_FILE" -noout -issuer 2>/dev/null | grep -i "Let's Encrypt" || echo "")
CERT_SUBJECT=$(openssl x509 -in "$SSL_CERT_FILE" -noout -subject 2>/dev/null | grep -o "CN = [^,]*" | cut -d'=' -f2 | tr -d ' ')
if [ -z "$CERT_ISSUER" ]; then
    echo "⚠️  WARNING: Certificate issuer is not Let's Encrypt"
    echo "   Certificate issuer: $(openssl x509 -in "$SSL_CERT_FILE" -noout -issuer 2>/dev/null)"
else
    echo "✅ Certificate verified: Let's Encrypt"
fi
if [ "$CERT_SUBJECT" != "server2.vo-cab.dev" ]; then
    echo "⚠️  WARNING: Certificate subject ($CERT_SUBJECT) doesn't match expected domain (server2.vo-cab.dev)"
else
    echo "✅ Certificate domain verified: $CERT_SUBJECT"
fi

# Ensure proper permissions on certificate files
chmod 644 "$SSL_CERT_FILE" 2>/dev/null || true
chmod 600 "$SSL_KEY_FILE" 2>/dev/null || true

# =========================
# STOP EXISTING SERVER
# =========================
echo "Checking for existing server on port 8002..."
EXISTING_PID=$(lsof -ti:8002 2>/dev/null || echo "")
if [ -n "$EXISTING_PID" ]; then
    echo "Stopping existing server (PID: $EXISTING_PID)..."
    kill -9 $EXISTING_PID 2>/dev/null || true
    sleep 2
    echo "✅ Existing server stopped"
else
    echo "No existing server found on port 8002"
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

# Set production API URL for frontend build
export VITE_API_URL="https://server2.vo-cab.dev:8002"
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

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "🐍 Activating virtual environment..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "🐍 Activating virtual environment..."
    source venv/bin/activate
fi

pip install -r requirements.txt

cd app

# =========================
# START FASTAPI WITH SSL
# =========================
echo "Starting FastAPI server with HTTPS..."

# Use PYTHONNOUSERSITE to prevent loading from ~/.local
export PYTHONNOUSERSITE=1

nohup python3 -m uvicorn main:app \
    --host 0.0.0.0 \
    --port 8002 \
    --ssl-certfile "$SSL_CERT_FILE" \
    --ssl-keyfile "$SSL_KEY_FILE" \
    > "$LOG_FILE" 2>&1 &

echo "✅ Application running with HTTPS"
echo "🌐 URL: https://server2.vo-cab.dev:8002/"
echo "📄 Logs: $LOG_FILE"
echo "🆔 PID: $!"
