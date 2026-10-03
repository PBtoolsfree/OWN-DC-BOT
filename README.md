# PB HERO — Personal Discord Bot & Dashboard

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3+-5865F2.svg)](https://discordpy.readthedocs.io/)
[![React](https://img.shields.io/badge/React-18.2+-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.2+-3178C6.svg)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**PB HERO** is a dedicated, private Discord bot and real-time administrative web dashboard engineered specifically for **single-server operation**. Built with modern Python (FastAPI + discord.py + SQLAlchemy async) and a sleek React/TypeScript dark dashboard, PB HERO delivers zero-quota YouTube monitoring, granular per-channel moderation rules, and unified system telemetry without SaaS complexity.

---

## Key Highlights

- **🔒 Single-Server Architecture**: Dedicated strictly to a single Discord guild (`DISCORD_GUILD_ID`). No multi-tenant complexity, no guild-switching UI, and zero cross-server data leaks.
- **📺 Zero-Quota YouTube Monitoring**: Monitors multiple YouTube channels concurrently using high-efficiency XML feeds and direct live-stream detectors. **Does NOT require a Google/YouTube API key or API quotas.**
- **🎯 Multi-Channel Discord Dispatching**: Route uploads and live notifications to discrete channels within the server (e.g., Channel A → `#youtube`, Channel B → `#videos`, Channel C → `#live`).
- **🛡️ 3-State Channel Policy Engine**: Channel-level message filters with distinct `ALLOW`, `DENY`, and `INHERIT` states for links, media, files, text, mentions, and stickers.
- **⚡ Interactive Web Dashboard**: Dark Discord-inspired dashboard featuring live latency indicators, preset policy profiles, moderation case auditing, and policy simulators.
- **🔐 Hardened Security**: HttpOnly secure cookie sessions, IP allowlisting, rate limiting, and brute-force mitigation for administrative control panel access.

---

## Architecture Overview

```
                      ┌──────────────────────────────────────┐
                      │          PB HERO SERVER              │
                      │        (DISCORD_GUILD_ID)            │
                      └──────────────────┬───────────────────┘
                                         │ discord.py
┌────────────────────────┐    ┌──────────▼───────────┐    ┌────────────────────────┐
│  YouTube Channels      │    │                      │    │   Admin Web Dashboard  │
│  - RSS XML Feed Poller │───>│      Core Engine     │<───│   - React 18 + TS SPA  │
│  - Live State Detector │    │  (FastAPI + SQLite)  │    │   - Centralized Client │
│  (No API Key Required) │    │                      │    │   - HttpOnly Sessions  │
└────────────────────────┘    └──────────────────────┘    └────────────────────────┘
```

---

## Features

### 1. YouTube Monitoring
- Supports multiple YouTube channels with `@handle`, channel ID (`UC...`), or direct channel URL.
- Independent notification toggles: New Uploads, Scheduled Streams, Live Started, and Premieres.
- Discord role mentions configurable per channel feed.
- Live Discord embed template editor with real-time preview.

### 2. Channel-Specific Moderation
- 3-state permission model (`ALLOW` / `DENY` / `INHERIT`) per channel.
- Filters: text, links, images, videos, files, stickers, `@everyone`, `@here`, role mentions, and user mentions.
- Reusable Policy Presets: *General Chat*, *No Links*, *Media Only*, *Announcements*, etc.
- In-dashboard Policy Simulator to test and verify policy rules against sample messages and roles before enforcement.

### 3. Administrative Control Panel
- **Overview**: Real-time status cards (Discord connection, gateway latency, database health, uptime), telemetry counters, and recent activity timeline.
- **YouTube**: Channel cards, live health status, feed testers, and stream trigger verification.
- **Moderator**: Incident metrics, active cases, case details dossier, and audit trail.
- **Channel Policies**: Interactive split-screen tree navigation with live rule editor.
- **Security**: Password change with strength validation, active sessions, and client IP protection.
- **System Diagnostics**: Telemetry metrics, memory/CPU diagnostics, configuration reload, and bot restart controls.

---

## Installation & Setup

### Prerequisites

- **Python**: 3.11 or 3.12
- **Node.js**: LTS (v20+ recommended) & npm
- **Discord Bot**: Application and bot token from the [Discord Developer Portal](https://discord.com/developers/applications) with `Message Content Intent` and `Server Members Intent` enabled.

---

### 1. Environment Configuration

Clone the repository and copy the environment template:

```bash
git clone https://github.com/PBtoolsfree/OWN-DC-BOT.git
cd OWN-DC-BOT
cp .env.example .env
```

Configure your `.env` file with appropriate values:

```env
# Discord Configuration
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_single_server_guild_id

# Dashboard Authentication
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=pbkdf2_sha256$... # Or plaintext during initial bootstrap

# Dashboard Server
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8000

# Session Security (32+ random characters)
SESSION_SECRET=change_this_to_a_secure_random_string_in_production

# Database
DATABASE_URL=sqlite+aiosqlite:///./data/pbhero.db

# YouTube Poller
YOUTUBE_POLL_INTERVAL=60
YOUTUBE_LIVE_CHECK_INTERVAL=30

# System Settings
LOG_LEVEL=INFO
TIMEZONE=Asia/Kolkata
```

---

### 2. Windows Installation (Automated)

Run the automated PowerShell installer:

```powershell
.\install.ps1
```

Or for non-interactive / headless setup:

```powershell
.\install.ps1 -NonInteractive -BotToken "your_bot_token" -GuildId "your_guild_id" -AdminPassword "YourPassword123!"
```

To start the bot and dashboard:
```powershell
.\start.ps1
```

---

### 3. Linux / Ubuntu / Debian Installation (Automated)

Run the automated Bash installer:

```bash
chmod +x install.sh
./install.sh
```

Or for non-interactive setup:

```bash
./install.sh --non-interactive --bot-token "your_bot_token" --guild-id "your_guild_id" --admin-pass "YourPassword123!"
```

To start the bot and dashboard:
```bash
./start.sh
```

---

### 4. Running with Docker

```bash
# Build and start container
docker build -t pbhero-bot .
docker run -d \
  --name pbhero \
  --restart unless-stopped \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  pbhero-bot
```

---

## Development & Testing

### Backend Verification
```bash
# Compile and check all Python modules
python -m compileall app
```

### Frontend Validation & Tests
```bash
cd web

# Linting
npm run lint

# TypeScript and Vite Production Build
npm run build

# Unit & Component Tests (Vitest)
npm test

cd ..
```

---

## Security Best Practices

1. **Keep `.env` Private**: Never commit `.env` or share your bot token. Only commit `.env.example`.
2. **Reverse Proxy & HTTPS**: In production, deploy behind Nginx or Caddy with TLS/SSL certificates and set `secure=True` for session cookies.
3. **IP Allowlisting**: Restrict web dashboard access using `DASHBOARD_ALLOWED_IPS` in `.env` if desired.
4. **Strong Credentials**: Use unique administrator passwords containing uppercase, lowercase, numbers, and special symbols.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
