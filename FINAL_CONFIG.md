# Silver Scraper - Final Configuration

## ✅ Complete Data Sources

### Spot Prices
- **XAG/USD**: $90.13/oz (Barchart ^XAGUSD)
- **Shanghai Ag T+D**: $101.06/oz (goldsilver.ai)

### Futures (Mar '26)
- **COMEX**: $89.95/oz
  - Volume, Open Interest
  - vs Spot spread
- **SHFE**: $97.06/oz (¥22,623/kg)
  - Volume: 42,866
  - Open Interest: 21,249
  - Relative Strength (14): 80.26
  - Daily Change: -0.62%
  - Premium vs COMEX: +$7.11

### ETF & Physical Holdings
- **SLV ETF**: $81.02 (-2.76%)
  - Holdings: ~30.7M oz
  - Daily change: Calculated from database
- **COMEX Inventory**: 278.5M oz registered (cached daily)
- **LBMA Holdings**: Not available (no public API)

## Discord Message Format

```
📊 Silver Market Update - 2026-01-16 05:26 PM EST

Spot Prices:
💎 XAG/USD: $90.13/oz
🇨🇳 Shanghai Ag T+D: $101.06/oz

Futures (Mar '26):
💰 COMEX: $89.95/oz
   vs Spot: -$0.18
   Vol: 12,345
   OI: 156,789

🇨🇳 SHFE: $97.06/oz (¥22,623/kg)
   Vol: 42,866
   OI: 21,249
   RS(14): 80.26
   Change: -0.62%
   Premium vs COMEX: +$7.11

SLV ETF:
🔻 $81.02 (-2.76%)
🏦 Holdings: 30,730,498 oz (+12,345)

Physical Holdings:
📦 COMEX Registered: 278,500,000 oz
📦 COMEX Eligible: 42,300,000 oz
   Reg/Total: 86.82%

Metrics:
📈 Futures-Spot Spread (COMEX-SLV): $8.93
⚖️ Paper/Physical Ratio: 1.78x
```

## Data Update Frequency

| Data | Frequency | Cache |
|------|-----------|-------|
| XAG/USD Spot | Hourly | No |
| Shanghai Ag T+D | Hourly | No |
| COMEX Futures | Hourly | No |
| SHFE Futures | Hourly | No |
| SLV ETF | Hourly | No |
| COMEX Inventory | Daily | 24h |
| LBMA Holdings | Daily | 24h |

## Setup Cron

```bash
crontab -e
```

Add:
```bash
# Hourly silver scraper
0 * * * * /home/ubuntu/project/slv_dashboard/run_hourly.sh >> /home/ubuntu/project/slv_dashboard/scraper.log 2>&1

# Daily report at 4:30 PM EST (21:30 UTC)
30 21 * * * /home/ubuntu/project/slv_dashboard/run_daily.sh >> /home/ubuntu/project/slv_dashboard/report.log 2>&1
```

## Test

```bash
cd /home/ubuntu/project/slv_dashboard
./run_hourly.sh
```

Check Discord for the complete formatted message!
