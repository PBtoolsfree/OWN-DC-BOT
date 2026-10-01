#!/bin/bash
set -e

echo "========================================="
echo " PB HERO Discord Bot - Automated Setup"
echo "========================================="

if [ "$EUID" -ne 0 ]; then
  echo "Please run this script as root (sudo bash setup.sh)"
  exit 1
fi

echo "Step 1: Updating system packages..."
apt-get update -y && apt-get upgrade -y

echo "Step 2: Checking and installing required packages..."
PACKAGES="git curl wget ufw"
for pkg in $PACKAGES; do
    if ! dpkg -l | grep -q "^ii  $pkg "; then
        echo "Installing $pkg..."
        apt-get install -y $pkg
    fi
done

if ! command -v docker &> /dev/null; then
    echo "Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    systemctl enable docker
    systemctl start docker
else
    echo "Docker is already installed."
fi

if ! docker compose version &> /dev/null && ! docker-compose version &> /dev/null; then
    echo "Docker Compose not found. Installing Docker Compose plugin..."
    apt-get install -y docker-compose-plugin
fi

echo "Step 3: Cloning Repository..."
if [ ! -d "DC-BOT-" ]; then
    git clone https://github.com/PBtoolsfree/DC-BOT-.git
fi
cd DC-BOT-

echo "Step 4: Bot Configuration..."
mkdir -p data backup logs secrets

if [ -f .env ]; then
    echo ".env file already exists. Skipping configuration."
else
    echo "Please provide your Bot details carefully:"
    
    while true; do
        read -p "Discord Bot Token: " DISCORD_BOT_TOKEN
        if [ -n "$DISCORD_BOT_TOKEN" ]; then break; else echo "Token cannot be empty."; fi
    done
    
    while true; do
        read -p "Discord Client ID: " DISCORD_CLIENT_ID
        if [ -n "$DISCORD_CLIENT_ID" ]; then break; else echo "Client ID cannot be empty."; fi
    done
    
    while true; do
        read -p "Discord Client Secret: " DISCORD_CLIENT_SECRET
        if [ -n "$DISCORD_CLIENT_SECRET" ]; then break; else echo "Client Secret cannot be empty."; fi
    done
    
    while true; do
        read -p "Discord Owner ID (Your personal Discord ID): " DISCORD_OWNER_ID
        if [ -n "$DISCORD_OWNER_ID" ]; then break; else echo "Owner ID cannot be empty."; fi
    done
    
    while true; do
        read -p "Discord Primary Guild ID (Server ID): " DISCORD_PRIMARY_GUILD_ID
        if [ -n "$DISCORD_PRIMARY_GUILD_ID" ]; then break; else echo "Guild ID cannot be empty."; fi
    done
    
    read -p "Dashboard Domain (e.g., panel.example.com or your Server IP): " DASHBOARD_DOMAIN
    read -p "Do you want to setup HTTPS with Nginx for this domain? (Requires valid DNS pointing to this IP) [y/N]: " SETUP_NGINX
    
    read -p "YouTube Poll Interval in seconds [120]: " YOUTUBE_POLL_INTERVAL
    YOUTUBE_POLL_INTERVAL=${YOUTUBE_POLL_INTERVAL:-120}
    
    read -p "Enable Moderation features by default? [Y/n]: " MODERATION_ENABLED
    if [[ "$MODERATION_ENABLED" =~ ^[Nn]$ ]]; then MODERATION_ENABLED="false"; else MODERATION_ENABLED="true"; fi
    
    read -p "Moderation Log Channel ID (Leave empty to skip): " MODERATION_LOG_CHANNEL_ID
    
    SESSION_SECRET=$(head -c 32 /dev/urandom | base64)
    
    if [[ "$SETUP_NGINX" =~ ^[Yy]$ ]]; then
        PROTOCOL="https"
    else
        PROTOCOL="http"
    fi

    cat <<EOF > .env
DISCORD_BOT_TOKEN=$DISCORD_BOT_TOKEN
DISCORD_CLIENT_ID=$DISCORD_CLIENT_ID
DISCORD_CLIENT_SECRET=$DISCORD_CLIENT_SECRET
DISCORD_OWNER_ID=$DISCORD_OWNER_ID
DISCORD_PRIMARY_GUILD_ID=$DISCORD_PRIMARY_GUILD_ID
DASHBOARD_PORT=3000
DASHBOARD_URL=$PROTOCOL://$DASHBOARD_DOMAIN
SESSION_SECRET=$SESSION_SECRET
YOUTUBE_POLL_INTERVAL_SECONDS=$YOUTUBE_POLL_INTERVAL
MODERATION_ENABLED=$MODERATION_ENABLED
MODERATION_LOG_CHANNEL_ID=$MODERATION_LOG_CHANNEL_ID
DATABASE_URL=sqlite:///app/data/database.sqlite
EOF
    chmod 600 .env
    echo "Configuration saved securely!"
fi

echo "Step 5: Setting up Nginx and HTTPS (if requested)..."
if [[ "$SETUP_NGINX" =~ ^[Yy]$ ]]; then
    apt-get install -y nginx certbot python3-certbot-nginx
    
    cat <<EOF > /etc/nginx/sites-available/pb-hero
server {
    server_name $DASHBOARD_DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_addrs;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF
    ln -sf /etc/nginx/sites-available/pb-hero /etc/nginx/sites-enabled/
    nginx -t && systemctl reload nginx
    
    echo "Requesting SSL Certificate via Certbot..."
    certbot --nginx -d $DASHBOARD_DOMAIN --non-interactive --agree-tos -m admin@$DASHBOARD_DOMAIN || echo "Certbot SSL failed, falling back to HTTP. Please check your DNS."
fi

echo "Step 6: Firewall Setup..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
echo "y" | ufw enable || true

echo "Step 7: Building and starting PB HERO Bot..."
docker compose up -d --build

echo "========================================="
echo " SETUP COMPLETE!"
echo "========================================="
echo "Bot Containers are running in the background."
echo "You can access your Dashboard at: $PROTOCOL://$DASHBOARD_DOMAIN"
echo "To check bot logs, run: cd DC-BOT- && docker compose logs -f"
echo "========================================="
