#!/usr/bin/env bash
# ==============================================================================
# PB HERO Personal Discord Bot - Linux / Debian / Ubuntu Installation Script
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

NON_INTERACTIVE=false
BOT_TOKEN=""
GUILD_ID=""
ADMIN_USERNAME="admin"
ADMIN_PASSWORD=""
DASHBOARD_PORT="8000"
SKIP_FRONTEND=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --non-interactive|-y)
      NON_INTERACTIVE=true
      shift
      ;;
    --bot-token)
      BOT_TOKEN="$2"
      shift 2
      ;;
    --guild-id)
      GUILD_ID="$2"
      shift 2
      ;;
    --admin-user)
      ADMIN_USERNAME="$2"
      shift 2
      ;;
    --admin-pass)
      ADMIN_PASSWORD="$2"
      shift 2
      ;;
    --port)
      DASHBOARD_PORT="$2"
      shift 2
      ;;
    --skip-frontend)
      SKIP_FRONTEND=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

echo "=========================================================="
echo "  PB HERO PERSONAL DISCORD BOT - LINUX INSTALLER"
echo "=========================================================="

# 1. Detect Python
echo "[1/8] Detecting Python installation..."
PYTHON_BIN=""
for cmd in python3.12 python3.11 python3; do
  if command -v "$cmd" &>/dev/null; then
    VER="$($cmd -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    MAJOR=$(echo "$VER" | cut -d. -f1)
    MINOR=$(echo "$VER" | cut -d. -f2)
    if [[ "$MAJOR" -eq 3 && "$MINOR" -ge 11 ]]; then
      PYTHON_BIN="$cmd"
      echo "  Found Python $VER ($cmd)"
      break
    fi
  fi
done

if [[ -z "$PYTHON_BIN" ]]; then
  echo "ERROR: Python 3.11 or higher is required. Please install python3.11 or python3.12."
  exit 1
fi

# 2. Virtual Environment
echo "[2/8] Setting up Python virtual environment..."
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

if [[ ! -f "$VENV_PYTHON" ]]; then
  echo "  Creating virtual environment in $VENV_DIR..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
else
  echo "  Virtual environment already exists."
fi

# 3. Create required directories
echo "[3/8] Creating required data directories..."
mkdir -p data logs backups

# 4. Install Dependencies
echo "[4/8] Installing Python dependencies..."
"$VENV_PYTHON" -m pip install --upgrade pip --quiet
"$VENV_PYTHON" -m pip install -r requirements.txt --quiet
echo "  Dependencies installed successfully."

# 5. Configuration & .env
echo "[5/8] Configuring environment (.env)..."
ENV_FILE="$SCRIPT_DIR/.env"

if [[ "$NON_INTERACTIVE" = false && ! -f "$ENV_FILE" ]]; then
  if [[ -z "$BOT_TOKEN" ]]; then
    read -rp "Enter Discord Bot Token (leave blank to configure later): " BOT_TOKEN || true
  fi
  if [[ -z "$GUILD_ID" ]]; then
    read -rp "Enter Discord Server (Guild) ID (leave blank to configure later): " GUILD_ID || true
  fi
  if [[ -z "$ADMIN_PASSWORD" ]]; then
    read -rsp "Enter Dashboard Admin Password [default: AdminPass123!]: " ADMIN_PASSWORD || true
    echo ""
    if [[ -z "$ADMIN_PASSWORD" ]]; then ADMIN_PASSWORD="AdminPass123!"; fi
  fi
else
  if [[ -z "$ADMIN_PASSWORD" ]]; then ADMIN_PASSWORD="AdminPass123!"; fi
fi

SESSION_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")

if [[ ! -f "$ENV_FILE" ]]; then
  cat <<EOF > "$ENV_FILE"
# ========================================
# PB HERO PERSONAL DISCORD BOT
# Environment Configuration
# ========================================

DISCORD_BOT_TOKEN=$BOT_TOKEN
DISCORD_GUILD_ID=$GUILD_ID

ADMIN_USERNAME=$ADMIN_USERNAME
ADMIN_PASSWORD=

DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=$DASHBOARD_PORT

SESSION_SECRET=$SESSION_SECRET
DATABASE_URL=sqlite+aiosqlite:///./data/pbhero.db

YOUTUBE_POLL_INTERVAL=60
YOUTUBE_LIVE_CHECK_INTERVAL=30

LOG_LEVEL=INFO
TIMEZONE=Asia/Kolkata
EOF
  echo "  Created .env file."
else
  echo "  .env already exists, preserving existing configuration."
fi

# 6. Database Initialization & Admin Setup
echo "[6/8] Initializing database and admin account..."
"$VENV_PYTHON" -m app.main init-db
if [[ -n "$ADMIN_USERNAME" && -n "$ADMIN_PASSWORD" ]]; then
  "$VENV_PYTHON" -m app.main create-admin --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD"
fi
echo "  Database and admin initialized."

# 7. Frontend Build
echo "[7/8] Checking web dashboard bundle..."
if [[ "$SKIP_FRONTEND" = false ]]; then
  if command -v npm &>/dev/null; then
    if [[ ! -f "web/dist/index.html" ]]; then
      echo "  Building dashboard frontend..."
      (cd web && npm install --quiet && npm run build)
      echo "  Dashboard frontend built successfully."
    else
      echo "  Dashboard production bundle ready."
    fi
  else
    echo "  Node.js/npm not found. Using prebuilt bundle if available."
  fi
fi

# 8. Create Startup Script
echo "[8/8] Creating start.sh runner script..."
cat << 'EOF' > start.sh
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec .venv/bin/python -m app.main
EOF
chmod +x start.sh

# Optional systemd template
cat << EOF > pbhero.service.example
[Unit]
Description=PB HERO Personal Discord Bot & Dashboard
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/.venv/bin/python -m app.main
Restart=always
RestartSec=10
EnvironmentFile=$SCRIPT_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

echo "=========================================================="
echo "  INSTALLATION COMPLETED SUCCESSFULLY!"
echo "=========================================================="
echo "To start PB HERO, run:"
echo "  ./start.sh"
echo "Dashboard will be accessible at: http://localhost:$DASHBOARD_PORT"
echo "Admin User: $ADMIN_USERNAME"
