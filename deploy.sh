#!/bin/bash

# Ubuntu Server Deployment Script for L&T Finance Feedback Survey System
# Run this script on your Ubuntu server

set -e  # Exit on error

echo "🚀 Starting Ubuntu Server Deployment..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Please do not run as root. Use a regular user with sudo privileges.${NC}"
   exit 1
fi

# Update system packages
echo -e "${YELLOW}📦 Updating system packages...${NC}"
sudo apt-get update
sudo apt-get upgrade -y

# Install required system packages
echo -e "${YELLOW}📦 Installing system dependencies...${NC}"
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    build-essential \
    postgresql-client \
    nginx \
    supervisor

# Create application directory
APP_DIR="/opt/lnt-feedback"
echo -e "${YELLOW}📁 Creating application directory at $APP_DIR...${NC}"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Clone or copy repository
read -p "Do you want to clone from GitHub? (y/n): " clone_repo
if [ "$clone_repo" = "y" ] || [ "$clone_repo" = "Y" ]; then
    echo -e "${YELLOW}📥 Cloning repository...${NC}"
    cd $APP_DIR
    git clone https://github.com/DRONA-VOCAB/LTFS_Conversational_Flow.git .
    git checkout feedback-survey
else
    echo -e "${YELLOW}📁 Copying files to $APP_DIR...${NC}"
    # If running locally, copy files
    cp -r . $APP_DIR/
fi

cd $APP_DIR

# Create virtual environment
echo -e "${YELLOW}🐍 Creating Python virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}⬆️  Upgrading pip...${NC}"
pip install --upgrade pip

# Install Python dependencies
echo -e "${YELLOW}📥 Installing Python dependencies...${NC}"
pip install -r requirements.txt

# Create .env file
echo -e "${YELLOW}⚙️  Setting up environment variables...${NC}"
if [ ! -f .env ]; then
    cat > .env << EOF
# Database Configuration
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require

# API Keys
GEMINI_API_KEY=your_gemini_api_key_here

# Service URLs
ASR_URL=http://27.111.72.52:5073/transcribe
TTS_URL=http://27.111.72.52:5057/synthesize

# Debug Mode
DEBUG=False
EOF
    echo -e "${GREEN}✅ Created .env file. Please edit it with your actual values:${NC}"
    echo "   nano $APP_DIR/.env"
fi

# Create systemd service file
echo -e "${YELLOW}⚙️  Creating systemd service...${NC}"
sudo tee /etc/systemd/system/lnt-feedback.service > /dev/null << EOF
[Unit]
Description=L&T Finance Feedback Survey API
After=network.target postgresql.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable lnt-feedback.service

echo ""
echo -e "${GREEN}✅ Deployment setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Edit environment variables: sudo nano $APP_DIR/.env"
echo "2. Start the service: sudo systemctl start lnt-feedback"
echo "3. Check status: sudo systemctl status lnt-feedback"
echo "4. View logs: sudo journalctl -u lnt-feedback -f"
echo ""
echo "Optional: Set up Nginx reverse proxy (see deployment guide)"

