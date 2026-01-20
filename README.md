# Silver Market Discord Bot

Discord bot for real-time silver market intelligence with OI tracking and delivery data.

## Quick Start

```bash
# Activate virtual environment
source venv_scraper/bin/activate

# Set Discord webhook URL
export DISCORD_WEBHOOK_URL="your_webhook_url_here"

# Run bot (hourly update)
python discord_bot.py --force

# Or use the original task
python task_hourly.py --force
```

## Features

- **Real-time Prices**: XAG/USD, COMEX Futures, SHFE Silver
- **OI Change Tracking**: COMEX and SHFE Open Interest deltas
- **Physical Holdings**: COMEX inventory, SLV/GLD trust holdings
- **Delivery Data**: Last 3 days COMEX silver delivery notices
- **Key Metrics**: Paper/Physical ratio, Shanghai Premium, Futures Basis

## Automation

```bash
# Hourly updates (add to crontab)
0 * * * * cd /path/to/slv_dashboard && source venv_scraper/bin/activate && export DISCORD_WEBHOOK_URL="your_url" && python discord_bot.py >> logs/bot.log 2>&1

# SHFE data refresh (every 30 min during market hours)
*/30 * * * * cd /path/to/slv_dashboard && source venv_scraper/bin/activate && python scrape_shfe_selenium.py >> logs/shfe.log 2>&1
```

## Dependencies

Core files needed:
- `discord_bot.py` - Main entry point
- `task_hourly.py` - Data fetching and Discord forwarding
- `data_fetcher.py` - Market data collection
- `cme_pdf_parser.py` - PDF delivery data extraction
- `db_manager.py` - Database operations
- `p0_storage.py` - Time series storage
- `scrape_shfe_selenium.py` - Shanghai futures scraper

## Configuration

Set environment variables:
- `DISCORD_WEBHOOK_URL` - Required for Discord messages
- `METALS_DEV_KEY` - Optional for metals.dev API (100 calls/month limit)
