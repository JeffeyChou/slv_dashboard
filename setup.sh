#!/bin/bash
set -e

echo "=== Silver Scraper Setup ==="

# 1. Install Python dependencies
echo "Installing dependencies..."
pip install selenium webdriver-manager yfinance matplotlib pandas requests python-dotenv

# 2. Setup environment
echo "Setting up environment..."
if [ ! -f .env ]; then
    cp .env.template .env
    echo "⚠️  Edit .env and add your Discord webhook URL"
fi

# 3. Make scripts executable
chmod +x task_hourly.py task_daily_report.py

# 4. Test database initialization
echo "Initializing database..."
python3 -c "from db_manager import DBManager; DBManager()"

# 5. Setup cron jobs
echo ""
echo "=== Cron Setup ==="
echo "Add these lines to your crontab (crontab -e):"
echo ""
echo "# Load environment variables and run hourly scraper"
echo "0 * * * * cd $(pwd) && export \$(cat .env | xargs) && /usr/bin/python3 task_hourly.py >> scraper.log 2>&1"
echo ""
echo "# Daily report at 16:30 EST (21:30 UTC)"
echo "30 21 * * * cd $(pwd) && export \$(cat .env | xargs) && /usr/bin/python3 task_daily_report.py >> report.log 2>&1"
echo ""
echo "=== Setup Complete ==="
echo "Next steps:"
echo "1. Edit .env with your Discord webhook"
echo "2. Test manually: python3 task_hourly.py"
echo "3. Add cron jobs as shown above"
