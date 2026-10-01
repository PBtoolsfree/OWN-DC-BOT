#!/bin/bash
echo "========================================="
echo " PB HERO Discord Bot Health Check"
echo "========================================="

if docker compose ps | grep -q "pb-hero-bot"; then
    STATUS=$(docker inspect -f '{{.State.Health.Status}}' pb-hero-bot 2>/dev/null || echo "unknown")
    if [ "$STATUS" = "healthy" ]; then
        echo "Discord Bot: ✅"
        echo "Dashboard API: ✅"
    else
        echo "Discord Bot / API: ❌ (Container status: $STATUS)"
    fi
else
    echo "Discord Bot: ❌ (Container not running)"
fi
