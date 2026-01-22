# Silver Market Discord Bot

Real-time silver market intelligence bot with OI tracking, delivery data, and Discord notifications.

## Quick Start

```bash
# Set Discord credentials
export DISCORD_BOT_TOKEN="your_bot_token_here"

# Run the bot
python discord_bot.py
```

## Features

- **Slash Commands**:
    - `/update_data`: Force refresh all market data and send report immediately
    - `/update_plot`: Generate and send the latest ETF holdings chart
    - `/autorun_on`: Enable automatic hourly updates (runs every 60 mins) in the current channel
    - `/autorun_off`: Disable automatic updates
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
├── discord_bot.py       # Main Bot with Slash Commands
├── task_hourly.py       # Hourly data fetch logic
├── task_daily_report.py # Daily chart generation logic
├── data_fetcher.py      # SilverDataFetcher class
├── db_manager.py        # Unified database (records, metrics, cache)
├── cme_pdf_parser.py    # CME delivery PDF parser
├── test_system.py       # System test script
├── requirements.txt     # Dependencies
├── .env                 # Environment variables
├── market_data.db       # Unified SQLite database
└── cache/               # Cache directory
```

## Automation

1.  **Run the Bot**:
    *   Run `python discord_bot.py`
    *   Invite the bot to your server.
    *   Type `/autorun_on` in the channel where you want updates.
    *   The bot will run continuously and update data every 60 minutes.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | Yes | Discord Bot Token (for slash commands) |
| `METALS_DEV_KEY` | No | metals.dev API key (100 calls/month) |

## Installation

```bash
# Clone and setup
cd slv_dashboard
pip install -r requirements.txt

# Configure
cp .env.template .env
# Edit .env to add DISCORD_BOT_TOKEN

# Run
python discord_bot.py
```

## Resource Usage

- **RAM**: ~50MB (no browser required)
- **Disk**: ~1MB/week (SQLite)
- **Network**: 2-3 requests/hour
