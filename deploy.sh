#!/bin/bash

# Simple Deployment Script for LTFS Conversational Flow
# Run with: sudo bash deploy.sh

set -e

echo "=========================================="
echo "LTFS Conversational Flow - Deployment"
echo "=========================================="

# Configuration
PROJECT_DIR="/opt/LTFS_Conversational_Flow"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# Check sudo
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run with sudo: sudo bash deploy.sh"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 1. Install dependencies
echo ""
echo "📦 Installing system packages..."
apt update -qq

# Install basic packages
apt install -y python3 python3-venv python3-pip nginx git || true

# Install Node.js (check if already installed)
if ! command_exists node || ! command_exists npm; then
    echo "📦 Installing Node.js..."
    # Try NodeSource repository first (includes npm)
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - 2>/dev/null || {
        echo "⚠️  NodeSource setup failed, trying system packages..."
        # Try installing just nodejs (npm comes with it in newer versions)
        apt install -y nodejs 2>/dev/null || {
            echo "⚠️  Node.js installation had issues, but continuing..."
        }
    }
    # Install nodejs after adding NodeSource repo
    apt install -y nodejs 2>/dev/null || true
fi

# Verify Node.js installation
if command_exists node && command_exists npm; then
    echo "✓ Node.js $(node --version) and npm $(npm --version) are ready"
else
    echo "⚠️  Warning: Node.js or npm may not be properly installed"
    echo "   You may need to install them manually"
fi

# 2. Setup project directory
echo ""
echo "📁 Setting up project..."
if [ ! -d "$PROJECT_DIR" ]; then
    mkdir -p /opt
    cd /opt
    git clone https://github.com/DRONA-VOCAB/LTFS_Conversational_Flow.git || {
        echo "❌ Failed to clone repository. Make sure it's accessible."
        exit 1
    }
fi
cd "$PROJECT_DIR"

# 3. Setup backend
echo ""
echo "🔧 Setting up backend..."
cd "$BACKEND_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
GEMINI_MODEL=gemini-pro
GEMINI_API_KEY=your-api-key-here
MAX_RETRIES=3
EOF
    echo "⚠️  Created .env file. Please update it with your Gemini API key!"
fi

# 4. Create backend service
echo ""
echo "⚙️  Creating backend service..."
cat > /etc/systemd/system/ltfs-backend.service << EOF
[Unit]
Description=LTFS Backend API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=$BACKEND_DIR
Environment="PATH=$BACKEND_DIR/venv/bin"
ExecStart=$BACKEND_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ltfs-backend
systemctl start ltfs-backend

# 5. Setup frontend
echo ""
echo "🎨 Setting up frontend..."
cd "$FRONTEND_DIR"
npm install --silent

# Create .env.production if it doesn't exist
if [ ! -f ".env.production" ]; then
    SERVER_IP=$(hostname -I | awk '{print $1}')
    cat > .env.production << EOF
VITE_API_URL=http://${SERVER_IP}:8000
EOF
fi

npm run build
chown -R www-data:www-data dist

# 6. Configure Nginx
echo ""
echo "🌐 Configuring Nginx..."
cat > /etc/nginx/sites-available/ltfs << EOF
server {
    listen 80;
    server_name _;

    root $FRONTEND_DIR/dist;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location ~ ^/(sessions|docs|openapi.json) {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

ln -sf /etc/nginx/sites-available/ltfs /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

# 7. Configure firewall
echo ""
echo "🔥 Configuring firewall..."
if command -v ufw >/dev/null 2>&1; then
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
fi

# Done!
echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
SERVER_IP=$(hostname -I | awk '{print $1}')
echo "🌐 Access your app at: http://$SERVER_IP"
echo ""
echo "📝 Next steps:"
echo "   1. Edit $BACKEND_DIR/.env with your Gemini API key"
echo "   2. Restart backend: sudo systemctl restart ltfs-backend"
echo "   3. Check status: sudo systemctl status ltfs-backend"
echo ""
