#!/bin/bash
cd /home/ubuntu/project/slv_dashboard
source venv_scraper/bin/activate
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/1461832507271024781/LdVh7-0cS8FXICL4fvh-Lep3gfzSOhSTKENhQ6I3arUcQwJEqT9K2ZutoACWCJS9XAPf"
python3 task_daily_report.py
