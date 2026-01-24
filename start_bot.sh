#!/bin/bash
# Quick start script for Discord bot

cd /home/ubuntu/project/slv_dashboard

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Please create .env with DISCORD_BOT_TOKEN"
    exit 1
fi

# Check if bot is already running
if pgrep -f "python.*discord_bot.py" > /dev/null; then
    echo "⚠️  Bot is already running. Stopping it first..."
    pkill -f "python.*discord_bot.py"
    sleep 2
fi

# Start bot
echo "🚀 Starting Discord bot..."
nohup python3 discord_bot.py > bot.log 2>&1 &
echo "✅ Bot started! PID: $!"
echo "📝 Logs: tail -f bot.log"
