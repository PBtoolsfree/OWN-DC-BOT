# PB HERO Discord Bot

A complete, production-ready personal Discord bot with a web dashboard, YouTube multi-channel notifications (without API key), and advanced moderation.

## Architecture
- **Backend:** Node.js, Fastify, discord.js
- **Frontend:** React, Vite, Tailwind CSS
- **Database:** SQLite
- **Deployment:** Docker, Docker Compose

## Features
- ✅ **YouTube Notifications:** Polls YouTube Atom feeds without needing the YouTube Data API. Supports multiple channels. Prevents duplicate notifications.
- ✅ **Moderation:** Banned words, spam protection, and more.
- ✅ **Web Dashboard:** Manage everything from a beautiful web UI.
- ✅ **Monitoring:** Real-time stats on Bot health, database, and moderation status.
- ✅ **Easy Setup:** One-script interactive installer for Oracle Cloud VPS.

## Oracle Cloud Setup
1. Create an Ubuntu/Debian instance.
   - **Recommended**: Ubuntu 24.04 LTS
   - **Supported**: Ubuntu 22.04 LTS, Ubuntu 24.04 LTS, Ubuntu 26.04 LTS
   - *(Note: Ubuntu 20.04 is explicitly NOT supported by the automated installer)*
2. Open ports 22 (SSH), 80 (HTTP), and 443 (HTTPS) in the Oracle Cloud Security List.
3. Configure your local Linux firewall for ports 22, 80, and 443 (no inbound Discord port is required).

## Installation
Run the automated setup script directly in your terminal:
```bash
curl -s https://raw.githubusercontent.com/PBtoolsfree/DC-BOT-/main/setup.sh | sudo bash
```
The script will automatically install dependencies, clone the repository, and guide you through the bot configuration.

## Discord Developer Portal Setup
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a new application and add a Bot.
3. Enable the **Message Content Intent** under the Bot tab. *(Note: Guild Members Intent and Presence Intent are NOT required for Phase 1)*
4. Copy your Bot Token, Client ID, and Client Secret.

## Commands
- `/ping`: Check bot latency.
- `/status`: View bot status.
- Add YouTube channels via the Web Dashboard.

## Dashboard
Access your dashboard via the domain or IP you configured during installation. 
Login requires Discord OAuth2, restricted to the `DISCORD_OWNER_ID`.

## Configuration
The bot uses a `.env` file for configuration. Notable options:
- `YOUTUBE_POLL_INTERVAL_SECONDS`: The interval at which the bot checks YouTube channels for new videos.
  - **Default**: `120`
  - **Minimum**: `30`
  - **Maximum**: `600`

## Why no YouTube Data API?
To avoid rate limits and quota issues, this bot uses YouTube's public Atom Feeds (XML) and robust polling mechanisms.
*(Note: Because the YouTube Data API is not used, detecting the difference between a normal video upload and a livestream state has limitations. All new videos and livestreams are pushed identically through the Atom feed.)*

## Troubleshooting
- `sudo bash health-check.sh`: Checks system health.
- `sudo bash repair.sh`: Attempts to repair the installation by rebuilding containers.
- `sudo bash update.sh`: Pulls the latest code and updates the bot.
- `sudo bash backup.sh`: Creates a manual database backup.

## License
MIT
