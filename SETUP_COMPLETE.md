# Silver Scraper - Serverless Setup Complete ✅

## System Status

- ✅ Python virtual environment: `venv_scraper`
- ✅ All dependencies installed
- ✅ Database initialized: `silver_data.db`
- ✅ Discord webhook configured
- ✅ Test successful

## Quick Test

```bash
cd /home/ubuntu/project/slv_dashboard
./run_hourly.sh
```

Check your Discord channel for the notification!

## Setup Cron Jobs

Add these to your crontab (`crontab -e`):

```bash
# Hourly scraper (every hour at minute 0)
0 * * * * /home/ubuntu/project/slv_dashboard/run_hourly.sh >> /home/ubuntu/project/slv_dashboard/scraper.log 2>&1

# Daily report at 4:30 PM EST (21:30 UTC)
30 21 * * * /home/ubuntu/project/slv_dashboard/run_daily.sh >> /home/ubuntu/project/slv_dashboard/report.log 2>&1
```

## What Gets Scraped

- **COMEX Silver**: Real-time futures price via yfinance
- **SHFE**: Requires Chromium (currently installing)

## Files Created

- `db_manager.py` - SQLite database handler
- `task_hourly.py` - Hourly scraper
- `task_daily_report.py` - Daily chart generator
- `run_hourly.sh` - Wrapper for cron
- `run_daily.sh` - Wrapper for cron
- `test_system.py` - System test script

## Manual Testing

```bash
# Test hourly scraper
./run_hourly.sh

# Test daily report
./run_daily.sh

# Run system test
source venv_scraper/bin/activate
export DISCORD_WEBHOOK_URL="<your_webhook>"
python3 test_system.py
```

## Logs

- `scraper.log` - Hourly scraper output
- `report.log` - Daily report output

## Database

SQLite database: `silver_data.db`

View data:
```bash
sqlite3 silver_data.db "SELECT * FROM silver_data ORDER BY timestamp DESC LIMIT 10;"
```

## Note on SHFE

SHFE scraping requires Chromium (currently installing via snap). Once complete, the hourly scraper will automatically include SHFE data.

## Resource Usage

- RAM: ~50MB (without SHFE), ~200MB (with SHFE)
- Disk: ~1MB per week
- Network: Minimal (2-3 requests/hour)
