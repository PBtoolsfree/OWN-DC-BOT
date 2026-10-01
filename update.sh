#!/bin/bash
set -e

echo "========================================="
echo " PB HERO Discord Bot Updater"
echo "========================================="

echo "Pulling latest changes from git..."
git pull origin main

echo "Rebuilding and restarting Docker containers..."
docker compose up -d --build

echo "Update complete!"
