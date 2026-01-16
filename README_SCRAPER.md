# Serverless Silver Scraper

Lightweight data scraping system with Discord notifications for resource-constrained VPS.

## Quick Start

```bash
# Run setup
bash setup.sh

# Configure webhook
nano .env  # Add your Discord webhook URL

# Test manually
python3 task_hourly.py
python3 task_daily_report.py

# Install cron jobs (copy from setup.sh output)
crontab -e
```

## Architecture

- **db_manager.py** - SQLite database handler
- **task_hourly.py** - Scrapes SHFE/COMEX every hour, sends Discord update
- **task_daily_report.py** - Generates 7-day trend chart at 16:30 EST (21:30 UTC)

## Data Sources

- SHFE: Selenium scraper (headless Chrome)
- COMEX: yfinance futures proxy

## Resource Usage

- RAM: ~200MB per scrape (headless Chrome)
- Disk: ~1MB per week (SQLite)
- Network: Minimal (2-3 requests/hour)

## Cron Schedule

```
0 * * * *    # Hourly scraper (top of every hour)
30 21 * * *  # Daily report (16:30 EST = 21:30 UTC)
```
