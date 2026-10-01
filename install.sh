#!/bin/bash
set -e

echo "========================================="
echo " PB HERO Discord Bot Installer"
echo "========================================="

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo bash install.sh)"
  exit 1
fi

echo "Checking dependencies..."
if ! command -v docker &> /dev/null; then
    echo "Docker not found. Please install Docker first."
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "Git not found. Installing Git..."
    apt-get update && apt-get install -y git || echo "Failed to install git automatically."
fi

echo "Creating project directories..."
mkdir -p data backup logs secrets

if [ -f .env ]; then
    echo ".env file already exists. Skipping configuration."
else
    echo "Starting interactive configuration..."
    
    read -p "Discord Bot Token: " DISCORD_BOT_TOKEN
    read -p "Discord Client ID: " DISCORD_CLIENT_ID
    read -p "Discord Client Secret: " DISCORD_CLIENT_SECRET
    read -p "Discord Owner ID: " DISCORD_OWNER_ID
    read -p "Discord Primary Guild ID: " DISCORD_PRIMARY_GUILD_ID
    read -p "Dashboard Domain (e.g., panel.example.com or IP): " DASHBOARD_DOMAIN
    read -p "Dashboard Port [3000]: " DASHBOARD_PORT
    DASHBOARD_PORT=${DASHBOARD_PORT:-3000}
    read -p "YouTube Poll Interval (seconds) [120]: " YOUTUBE_POLL_INTERVAL
    YOUTUBE_POLL_INTERVAL=${YOUTUBE_POLL_INTERVAL:-120}
    read -p "Enable Moderation? [Y/n]: " MODERATION_ENABLED
    if [[ "$MODERATION_ENABLED" =~ ^[Nn]$ ]]; then
        MODERATION_ENABLED="false"
    else
        MODERATION_ENABLED="true"
    fi
    read -p "Moderation Log Channel ID: " MODERATION_LOG_CHANNEL_ID
    
    SESSION_SECRET=$(head -c 32 /dev/urandom | base64)

    cat <<EOF > .env
DISCORD_BOT_TOKEN=$DISCORD_BOT_TOKEN
DISCORD_CLIENT_ID=$DISCORD_CLIENT_ID
DISCORD_CLIENT_SECRET=$DISCORD_CLIENT_SECRET
DISCORD_OWNER_ID=$DISCORD_OWNER_ID
DISCORD_PRIMARY_GUILD_ID=$DISCORD_PRIMARY_GUILD_ID
DASHBOARD_PORT=$DASHBOARD_PORT
DASHBOARD_URL=http://$DASHBOARD_DOMAIN
SESSION_SECRET=$SESSION_SECRET
YOUTUBE_POLL_INTERVAL_SECONDS=$YOUTUBE_POLL_INTERVAL
MODERATION_ENABLED=$MODERATION_ENABLED
MODERATION_LOG_CHANNEL_ID=$MODERATION_LOG_CHANNEL_ID
DATABASE_URL=sqlite:///app/data/database.sqlite
EOF
    chmod 600 .env
    echo "Configuration saved securely to .env"
fi

echo "Building and starting Docker containers..."
docker compose up -d --build

echo "========================================="
echo " Installation Complete!"
echo " Bot: ✅ Running"
echo " Dashboard API: ✅ Running"
echo " Dashboard available at configured domain/IP"
echo "========================================="
