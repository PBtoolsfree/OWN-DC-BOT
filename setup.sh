#!/bin/bash
set -euo pipefail

# Helper functions
log_info() { echo -e "\e[34m[INFO]\e[0m $1"; }
log_success() { echo -e "\e[32m[SUCCESS]\e[0m $1"; }
log_warning() { echo -e "\e[33m[WARNING]\e[0m $1"; }
log_error() { echo -e "\e[31m[ERROR]\e[0m $1"; }
die() { log_error "$1"; exit 1; }

prompt_confirm() {
    local prompt_text="$1"
    local default_ans="${2:-N}"
    local ans
    read -p "$prompt_text [$default_ans]: " ans < /dev/tty
    if [[ -z "$ans" ]]; then ans="$default_ans"; fi
    if [[ "$ans" =~ ^[Yy]$ ]]; then return 0; else return 1; fi
}

prompt_input() {
    local prompt_text="$1"
    local var_name="$2"
    local default_val="${3:-}"
    local ans
    while true; do
        read -p "$prompt_text" ans < /dev/tty
        if [[ -z "$ans" && -n "$default_val" ]]; then
            eval "$var_name=\"\$default_val\""
            break
        elif [[ -n "$ans" ]]; then
            eval "$var_name=\"\$ans\""
            break
        else
            log_error "This field cannot be empty."
        fi
    done
}

echo "========================================="
echo " PB HERO Discord Bot - Automated Setup"
echo "========================================="

if [ "$EUID" -ne 0 ]; then
  die "Please run this script as root (e.g., sudo bash setup.sh)"
fi

# Step 1: OS and Version Detection
log_info "Detecting Operating System..."
if [ ! -f /etc/os-release ]; then
    die "Cannot determine OS. /etc/os-release is missing."
fi

. /etc/os-release
if [ "$ID" != "ubuntu" ]; then
    die "This installer only supports Ubuntu."
fi

UBUNTU_VERSION=$VERSION_ID
UBUNTU_CODENAME=$VERSION_CODENAME
log_info "Detected Ubuntu $UBUNTU_VERSION ($UBUNTU_CODENAME)"

if [ "$UBUNTU_VERSION" == "20.04" ]; then
    echo "================================================"
    echo "                    WARNING                     "
    echo "================================================"
    echo "Ubuntu 20.04 (Focal) is no longer in standard"
    echo "support and is not a supported target for this"
    echo "installation."
    echo ""
    echo "Please use Ubuntu 22.04 or Ubuntu 24.04 LTS."
    echo ""
    echo "Recommended: Ubuntu 24.04 LTS"
    echo "================================================"
    die "Installation aborted safely."
fi

# Check if supported
if [[ "$UBUNTU_VERSION" != "22.04" && "$UBUNTU_VERSION" != "24.04" && "$UBUNTU_VERSION" != "26.04" ]]; then
    log_warning "Ubuntu $UBUNTU_VERSION is not officially supported, but the installer will attempt to proceed."
fi

# Step 2: Update Packages
log_info "Updating package lists..."
apt-get update -y

log_info "Installing basic required dependencies..."
apt-get install -y ca-certificates curl gnupg git wget ufw

# Step 3: Docker Installation
log_info "Checking Docker installation..."
if command -v docker &> /dev/null && docker compose version &> /dev/null && systemctl is-active --quiet docker; then
    log_success "Docker is already installed and healthy."
    log_info "Docker Engine: Running"
    log_info "Docker Compose: Available"
else
    log_info "Detecting conflicting Docker packages..."
    CONFLICTS="docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc"
    FOUND_CONFLICTS=""
    for pkg in $CONFLICTS; do
        if dpkg -l | grep -q "^ii  $pkg "; then
            FOUND_CONFLICTS="$FOUND_CONFLICTS $pkg"
        fi
    done

    if [ -n "$FOUND_CONFLICTS" ]; then
        log_warning "Found conflicting packages:$FOUND_CONFLICTS"
        if prompt_confirm "Do you want to remove these conflicting packages?" "N"; then
            log_info "Removing conflicting packages..."
            for pkg in $FOUND_CONFLICTS; do
                apt-get remove -y "$pkg" || true
            done
        else
            die "Cannot proceed with conflicting Docker packages installed."
        fi
    fi

    log_info "Configuring Docker official repository..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc

    ARCH=$(dpkg --print-architecture)
    if [[ "$ARCH" != "amd64" && "$ARCH" != "arm64" && "$ARCH" != "armhf" ]]; then
        die "Unsupported architecture: $ARCH"
    fi

    echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $UBUNTU_CODENAME stable" > /etc/apt/sources.list.d/docker.sources

    apt-get update -y

    log_info "Installing Docker packages..."
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    log_info "Enabling and starting Docker service..."
    systemctl enable docker
    systemctl start docker

    if ! command -v docker &> /dev/null; then die "Docker CLI is missing after installation."; fi
    if ! docker compose version &> /dev/null; then die "Docker Compose is missing after installation."; fi
    if ! systemctl is-active --quiet docker; then die "Docker service failed to start."; fi

    log_info "Verifying Docker installation with hello-world..."
    if ! docker run --rm hello-world &> /dev/null; then
        die "Docker hello-world verification failed. Check your Docker installation."
    fi
    log_success "Docker installed successfully."
fi

# Step 4: Installation Directory and Cloning
INSTALL_DIR="/opt/pb-hero-discord-bot"
log_info "Setting up project in $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

if [ -d ".git" ]; then
    log_info "Repository already exists. Pulling latest changes..."
    git pull origin main
else
    log_info "Cloning repository..."
    git clone https://github.com/PBtoolsfree/DC-BOT-.git .
fi

mkdir -p data backup logs secrets

# Step 5: Configuration
if [ -f .env ]; then
    log_info ".env file found. Loading existing configuration..."
    set -a
    source .env
    set +a
    
    # Ensure some vars have defaults if loaded from an old env
    DASHBOARD_DOMAIN=$(echo "${DASHBOARD_URL:-}" | sed -e 's|^[^/]*//||' -e 's|/.*$||')
    PROTOCOL=$(echo "${DASHBOARD_URL:-http://}" | grep -o '^[^:]*')
    SETUP_NGINX="n"
    if [[ "$PROTOCOL" == "https" ]]; then SETUP_NGINX="y"; fi
else
    log_info "Starting interactive configuration..."
    
    prompt_input "Discord Bot Token: " DISCORD_BOT_TOKEN
    prompt_input "Discord Client ID: " DISCORD_CLIENT_ID
    prompt_input "Discord Client Secret: " DISCORD_CLIENT_SECRET
    prompt_input "Discord Owner ID (Your personal Discord ID): " DISCORD_OWNER_ID
    prompt_input "Discord Primary Guild ID (Server ID): " DISCORD_PRIMARY_GUILD_ID
    prompt_input "Dashboard Domain (e.g., panel.example.com or your Server IP): " DASHBOARD_DOMAIN
    
    if prompt_confirm "Do you want to setup HTTPS with Nginx for this domain? (Requires valid DNS)" "N"; then
        SETUP_NGINX="y"
        PROTOCOL="https"
    else
        SETUP_NGINX="n"
        PROTOCOL="http"
    fi
    
    prompt_input "YouTube Poll Interval in seconds [120]: " YOUTUBE_POLL_INTERVAL "120"
    
    if prompt_confirm "Enable Moderation features by default?" "Y"; then
        MODERATION_ENABLED="true"
    else
        MODERATION_ENABLED="false"
    fi
    
    prompt_input "Moderation Log Channel ID (Leave empty to skip): " MODERATION_LOG_CHANNEL_ID " "
    
    # Strip space if it was default
    if [[ "$MODERATION_LOG_CHANNEL_ID" == " " ]]; then MODERATION_LOG_CHANNEL_ID=""; fi
    
    SESSION_SECRET=$(head -c 32 /dev/urandom | base64)

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
    log_success "Configuration saved securely!"
fi

# Step 6: Setup Nginx
if [[ "$SETUP_NGINX" =~ ^[Yy]$ ]]; then
    log_info "Setting up Nginx and HTTPS..."
    apt-get install -y nginx certbot python3-certbot-nginx
    
    NGINX_CONF="/etc/nginx/sites-available/pb-hero"
    
    if [ ! -f "$NGINX_CONF" ]; then
        cat <<EOF > "$NGINX_CONF"
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
        ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/
    fi
    
    if nginx -t; then
        systemctl reload nginx
        log_info "Requesting SSL Certificate via Certbot..."
        certbot --nginx -d "$DASHBOARD_DOMAIN" --non-interactive --agree-tos -m "admin@$DASHBOARD_DOMAIN" || log_warning "Certbot SSL failed. Check your DNS. Falling back to HTTP."
    else
        log_error "Nginx configuration test failed. Skipping Nginx reload."
    fi
fi

# Step 7: Firewall rules
log_info "Configuring Firewall (UFW)..."
ufw allow 22/tcp || true
ufw allow 80/tcp || true
ufw allow 443/tcp || true
# We don't enable UFW forcefully if it's disabled, we just add the rules. If they want to enable it they can.

# Step 8: Build and Start Project
log_info "Building and starting PB HERO Bot with Docker Compose..."
docker compose up -d --build

log_info "Running Health Check..."
echo "-----------------------------------------"
docker info > /dev/null && echo "Docker:              ✅" || echo "Docker:              ❌"
docker compose version > /dev/null && echo "Docker Compose:      ✅" || echo "Docker Compose:      ❌"
if docker compose ps | grep -q "pb-hero-bot"; then
    echo "Bot Container:       ✅"
else
    echo "Bot Container:       ❌"
fi
echo "-----------------------------------------"

echo "========================================="
echo " SETUP COMPLETE!"
echo "========================================="
echo "Project Directory: $INSTALL_DIR"
echo "You can access your Dashboard at: $PROTOCOL://$DASHBOARD_DOMAIN"
echo "To check bot logs, run: cd $INSTALL_DIR && docker compose logs -f"
echo "========================================="
