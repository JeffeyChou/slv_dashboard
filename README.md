# Silver Market Discord Bot

Real-time silver market intelligence bot with OI tracking, delivery data, and Discord notifications.

## Quick Start

```bash
# Activate virtual environment
source venv_scraper/bin/activate

# Set Discord webhook URL
export DISCORD_WEBHOOK_URL="your_webhook_url_here"

# Run hourly update
python discord_bot.py --force

# Or run directly
python task_hourly.py --force
```

## Features

- **Real-time Prices**: XAG/USD, COMEX Futures, SHFE Silver, SLV/GLD ETF
- **OI Change Tracking**: COMEX and SHFE Open Interest deltas
- **Physical Holdings**: COMEX inventory, SLV/GLD trust holdings
- **Delivery Data**: COMEX silver delivery notices (PDF parsing)
- **Key Metrics**: Paper/Physical ratio, Shanghai Premium, Futures Basis
- **Daily Charts**: 30-day trend visualization

## Data Sources

| Data | Source | Update Frequency | Cache |
|------|--------|------------------|-------|
| XAG/USD Spot | yfinance | Hourly | None |
| Shanghai Ag T+D | goldsilver.ai | Hourly | None |
| COMEX Futures | yfinance (SI=F) | Hourly | None |
| SHFE Futures | barchart.com | Hourly | None |
| SLV/GLD ETF | yfinance | Hourly | None |
| COMEX Inventory | CME PDF | Daily | 24h |
| ETF Holdings | yfinance | Daily | 24h |
| USD/CNY Rate | yfinance | Daily | 24h |

## Discord Message Format

```
📊 Silver Market Update - 2026-01-16 05:26 PM EST

Spot Prices:
💎 XAG/USD: $90.13/oz
🇨🇳 Shanghai Ag T+D: $101.06/oz

Futures (Mar '26):
💰 COMEX: $89.95/oz
   vs Spot: -$0.18
   Vol: 12,345 | OI: 156,789

🇨🇳 SHFE: $97.06/oz (¥22,623/kg)
   Vol: 42,866 | OI: 21,249
   Premium vs COMEX: +$7.11

SLV ETF:
🔻 $81.02 (-2.76%)
🏦 Holdings: 30,730,498 oz

Physical Holdings:
📦 COMEX Registered: 278,500,000 oz
📦 COMEX Eligible: 42,300,000 oz

Metrics:
📈 Futures-Spot Spread: $8.93
⚖️ Paper/Physical Ratio: 1.78x
```

## File Structure

```
slv_dashboard/
├── discord_bot.py       # Entry point
├── task_hourly.py       # Hourly data fetch + Discord posting
├── task_daily_report.py # Daily chart generation
├── data_fetcher.py      # SilverDataFetcher class
├── db_manager.py        # Unified database (records, metrics, cache)
├── cme_pdf_parser.py    # CME delivery PDF parser
├── test_system.py       # System test script
├── requirements.txt     # Dependencies
├── .env                 # Environment variables
├── run_hourly.sh        # Cron wrapper (hourly)
├── run_daily.sh         # Cron wrapper (daily)
├── market_data.db       # Unified SQLite database
└── cache/               # Discord message ID file
```

## Cron Setup

```bash
crontab -e
```

Add:
```bash
# Hourly updates (every hour at minute 0)
0 * * * * /path/to/slv_dashboard/run_hourly.sh >> /path/to/scraper.log 2>&1

# Daily report at 4:30 PM EST (21:30 UTC)
30 21 * * * /path/to/slv_dashboard/run_daily.sh >> /path/to/report.log 2>&1
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_WEBHOOK_URL` | Yes | Discord webhook URL |
| `METALS_DEV_KEY` | No | metals.dev API key (100 calls/month) |

## API Limits

| API | Limit | Strategy |
|-----|-------|----------|
| metals.dev | 100/month | 8-hour cache |
| CME PDF | May timeout | 24h cache + stale fallback |
| SHFE | IP restricted | Best effort |
| yfinance | Generous | Normal use |

## Installation

```bash
# Clone and setup
cd slv_dashboard
python -m venv venv_scraper
source venv_scraper/bin/activate
pip install -r requirements.txt

# Configure
cp .env.template .env
nano .env  # Add DISCORD_WEBHOOK_URL

# Test
python test_system.py
```

## Resource Usage

- **RAM**: ~50MB (no browser required)
- **Disk**: ~1MB/week (SQLite)
- **Network**: 2-3 requests/hour
