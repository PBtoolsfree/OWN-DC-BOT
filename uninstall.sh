#!/bin/bash
read -p "Are you sure you want to completely uninstall PB HERO? This will delete all data. [y/N]: " CONFIRM
if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
    docker compose down -v
    echo "Containers removed."
    echo "To remove files, run: rm -rf data logs secrets backup"
    echo "Uninstall complete."
else
    echo "Uninstallation cancelled."
fi
