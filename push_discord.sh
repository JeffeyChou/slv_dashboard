#!/bin/bash
cd /home/ubuntu/project/slv_dashboard
source venv_scraper/bin/activate
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/1461832507271024781/LdVh7-0cS8FXICL4fvh-Lep3gfzSOhSTKENhQ6I3arUcQwJEqT9K2ZutoACWCJS9XAPf"

echo "Silver Market Discord Push"
echo "=========================="
echo "1) Push with cached data (fast)"
echo "2) Force refresh all data then push"
echo ""
read -p "Choose [1/2]: " choice

case $choice in
    2) python3 task_hourly.py --force ;;
    *) python3 task_hourly.py ;;
esac
