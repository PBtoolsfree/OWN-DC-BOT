# ==============================================================================
# PB HERO Personal Discord Bot - Windows Installation Script
# ==============================================================================

[CmdletBinding()]
param(
    [switch]$NonInteractive = $false,
    [string]$BotToken = "",
    [string]$GuildId = "",
    [string]$AdminUsername = "admin",
    [string]$AdminPassword = "",
    [string]$DashboardPort = "8000",
    [switch]$SkipFrontendBuild = $false
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  PB HERO PERSONAL DISCORD BOT - WINDOWS INSTALLER" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Detect Python
Write-Host "[1/8] Detecting Python installation..." -ForegroundColor Yellow
$PythonCmd = $null
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    $PythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($PythonVersion -and ([version]$PythonVersion -ge [version]"3.11")) {
        $PythonCmd = "python"
        Write-Host "  Found Python $PythonVersion" -ForegroundColor Green
    }
}

if (-not $PythonCmd -and (Get-Command "py" -ErrorAction SilentlyContinue)) {
    $PythonVersion = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($PythonVersion -and ([version]$PythonVersion -ge [version]"3.11")) {
        $PythonCmd = "py -3"
        Write-Host "  Found Python (py launcher) $PythonVersion" -ForegroundColor Green
    }
}

if (-not $PythonCmd) {
    Write-Host "ERROR: Python 3.11 or higher is required. Please install it from python.org or Microsoft Store." -ForegroundColor Red
    exit 1
}

# 2. Virtual Environment
Write-Host "[2/8] Setting up Python virtual environment..." -ForegroundColor Yellow
$VenvDir = Join-Path $PSScriptRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "  Creating virtual environment in $VenvDir..."
    & $PythonCmd -m venv $VenvDir
} else {
    Write-Host "  Virtual environment already exists." -ForegroundColor Gray
}

# 3. Create required directories
Write-Host "[3/8] Creating required data directories..." -ForegroundColor Yellow
$Dirs = @("data", "logs", "backups")
foreach ($Dir in $Dirs) {
    $DirPath = Join-Path $PSScriptRoot $Dir
    if (-not (Test-Path $DirPath)) {
        New-Item -ItemType Directory -Path $DirPath -Force | Out-Null
        Write-Host "  Created $Dir/" -ForegroundColor Gray
    }
}

# 4. Install Dependencies
Write-Host "[4/8] Installing Python dependencies..." -ForegroundColor Yellow
& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt") --quiet
Write-Host "  Dependencies installed successfully." -ForegroundColor Green

# 5. Configuration & .env
Write-Host "[5/8] Configuring environment (.env)..." -ForegroundColor Yellow
$EnvPath = Join-Path $PSScriptRoot ".env"

if (-not $NonInteractive -and -not (Test-Path $EnvPath)) {
    if (-not $BotToken) {
        $BotToken = Read-Host "Enter Discord Bot Token (leave blank to configure later)"
    }
    if (-not $GuildId) {
        $GuildId = Read-Host "Enter Discord Server (Guild) ID (leave blank to configure later)"
    }
    if (-not $AdminPassword) {
        $AdminPassword = Read-Host "Enter Dashboard Admin Password [default: AdminPass123!]"
        if (-not $AdminPassword) { $AdminPassword = "AdminPass123!" }
    }
} else {
    if (-not $AdminPassword) { $AdminPassword = "AdminPass123!" }
}

# Generate random session secret
$SessionSecretBytes = New-Object byte[] 32
$RandomGen = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$RandomGen.GetBytes($SessionSecretBytes)
$SessionSecret = [System.BitConverter]::ToString($SessionSecretBytes).Replace("-", "").ToLower()

if (-not (Test-Path $EnvPath)) {
    $EnvContent = @"
# ========================================
# PB HERO PERSONAL DISCORD BOT
# Environment Configuration
# ========================================

DISCORD_BOT_TOKEN=$BotToken
DISCORD_GUILD_ID=$GuildId

ADMIN_USERNAME=$AdminUsername
ADMIN_PASSWORD=

DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=$DashboardPort

SESSION_SECRET=$SessionSecret
DATABASE_URL=sqlite+aiosqlite:///./data/pbhero.db

YOUTUBE_POLL_INTERVAL=60
YOUTUBE_LIVE_CHECK_INTERVAL=30

LOG_LEVEL=INFO
TIMEZONE=Asia/Kolkata
"@
    Set-Content -Path $EnvPath -Value $EnvContent -Encoding UTF8
    Write-Host "  Created .env file." -ForegroundColor Green
} else {
    Write-Host "  .env already exists, preserving existing configuration." -ForegroundColor Gray
}

# 6. Database Initialization & Admin Setup
Write-Host "[6/8] Initializing database and admin account..." -ForegroundColor Yellow
& $VenvPython -m app.main init-db
if ($AdminUsername -and $AdminPassword) {
    & $VenvPython -m app.main create-admin --username $AdminUsername --password $AdminPassword
}
Write-Host "  Database and admin initialized." -ForegroundColor Green

# 7. Frontend Build (if Node.js is available and dist is missing)
Write-Host "[7/8] Checking web dashboard bundle..." -ForegroundColor Yellow
$WebDistIndex = Join-Path $PSScriptRoot "web\dist\index.html"

if (-not $SkipFrontendBuild) {
    if (Get-Command "npm" -ErrorAction SilentlyContinue) {
        if (-not (Test-Path $WebDistIndex)) {
            Write-Host "  Building dashboard frontend..." -ForegroundColor Gray
            Push-Location (Join-Path $PSScriptRoot "web")
            try {
                & npm install --quiet
                & npm run build
            } finally {
                Pop-Location
            }
            Write-Host "  Dashboard frontend built successfully." -ForegroundColor Green
        } else {
            Write-Host "  Dashboard production bundle ready." -ForegroundColor Green
        }
    } else {
        Write-Host "  Node.js/npm not found. Existing frontend bundle will be used if present." -ForegroundColor Yellow
    }
}

# 8. Create Startup Script
Write-Host "[8/8] Creating start.ps1 shortcut..." -ForegroundColor Yellow
$StartScriptPath = Join-Path $PSScriptRoot "start.ps1"
$StartScriptContent = @"
# PB HERO Bot & Dashboard Runner
`$ErrorActionPreference = 'Stop'
`$VenvPython = Join-Path `$PSScriptRoot '.venv\Scripts\python.exe'
Write-Host 'Starting PB HERO Personal Discord Bot & Dashboard...' -ForegroundColor Cyan
& `$VenvPython -m app.main
"@
Set-Content -Path $StartScriptPath -Value $StartScriptContent -Encoding UTF8
Write-Host "  Created start.ps1" -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  INSTALLATION COMPLETED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "To start PB HERO, run:" -ForegroundColor White
Write-Host "  .\start.ps1" -ForegroundColor Cyan
Write-Host "Dashboard will be accessible at: http://localhost:$DashboardPort" -ForegroundColor White
Write-Host "Admin User: $AdminUsername" -ForegroundColor White
