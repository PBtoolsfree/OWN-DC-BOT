#!/bin/bash
set -e
TIMESTAMP=$(date +"%Y-%m-%d-%H%M")
mkdir -p backup
if [ -f data/database.sqlite ]; then
    cp data/database.sqlite backup/pb-hero-$TIMESTAMP.db
    echo "Backup created at backup/pb-hero-$TIMESTAMP.db"
    
    # Keep only last 10 backups
    ls -tp backup/pb-hero-*.db | grep -v '/$' | tail -n +11 | xargs -I {} rm -- {} 2>/dev/null || true
else
    echo "No database found to backup."
fi
