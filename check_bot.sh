#!/bin/bash
# Bot health check and monitoring script

LOG_FILE="/home/ubuntu/project/slv_dashboard/bot.log"
SERVICE_NAME="slv-bot.service"

echo "=== Bot Health Check ==="
echo "Time: $(date)"
echo ""

# Check service status
echo "Service Status:"
sudo systemctl is-active $SERVICE_NAME
echo ""

# Check memory usage
echo "Memory Usage:"
ps aux | grep discord_bot.py | grep -v grep | awk '{print "  CPU: "$3"% | Memory: "$4"% | RSS: "$6" KB"}'
echo ""

# Check recent errors
echo "Recent Errors (last 10):"
grep -i "error\|exception\|critical" $LOG_FILE | tail -10 || echo "  No errors found"
echo ""

# Check last activity
echo "Last Log Entry:"
tail -1 $LOG_FILE
