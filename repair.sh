#!/bin/bash
echo "Repairing PB HERO installation..."
docker compose down
docker compose up -d --build
echo "Repair complete."
