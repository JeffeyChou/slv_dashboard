# Silver Market Intelligence Dashboard

Real-time tracking system for silver market squeeze indicators with 17/20 P0 metrics, time-series storage, and hybrid data strategy.

## Table of Contents
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Data Sources](#data-sources)
- [P0 Indicators](#p0-indicators)
- [Maintenance](#maintenance)
- [Development](#development)

## Quick Start

### Prerequisites
- Python 3.13+
- Chrome/Chromium (for Selenium scraper)
- metals.dev API key (optional but recommended)

### Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variable (optional)
export METALS_DEV_KEY="your_key_here"

# Run SHFE scraper (first time)
python scrape_shfe_selenium.py

# Start dashboard
python app.py
```

Access dashboard at: **http://localhost:5000**

## Project Structure

```
SLV_PRICE/
├── app.py                      # Flask web server (main entry)
├── data_fetcher.py             # Core data retrieval & P0 calculations
├── p0_storage.py               # Time-series CSV manager
├── cme_pdf_parser.py           # COMEX delivery PDF parser
│
├── scrape_shfe_selenium.py     # SHFE data scraper (Selenium)
│
├── requirements.txt            # Python dependencies
├── p0_timeseries.csv          # Historical P0 data (auto-generated)
│
├── templates/
│   └── index.html             # Dashboard UI
│
├── static/
│   ├── script.js              # Frontend logic & Chart.js
│   └── style.css              # Dashboard styling
│
├── cache/                     # API response cache (auto-created)
│   ├── cme_data.json         # 24-hour CME inventory cache
│   ├── lbma_data.json        # 24-hour LBMA cache
│   ├── metals_dev_prices.json # 8-hour metals.dev cache
│   ├── cme_delivery_daily.json
│   └── cme_delivery_mtd.json
│
└── shfe_market_data.json     # SHFE scraped data (30-min validity)
```

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────┐
│                    Flask App (app.py)                    │
│                  Port 5000, /api/data                    │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              SilverDataFetcher (data_fetcher.py)         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Real-time (every request)                      │   │
│  │  - yfinance: Futures, Options                   │   │
│  │  - FRED: USD/CNY, Real Yield                    │   │
│  │  - yfinance: DX-Y.NYB (USD Index)               │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Cached (TTL-based)                             │   │
│  │  - SHFE JSON: 30 min (from scraper)             │   │
│  │  - CME Inventory: 24 hours                      │   │
│  │  - CME Delivery PDFs: 24 hours                  │   │
│  │  - metals.dev: 8 hours (baseline)               │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  P0 Calculations (17 indicators)                │   │
│  └─────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│         P0TimeSeriesStorage (p0_storage.py)              │
│         Appends to p0_timeseries.csv                     │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Frontend (index.html + script.js)           │
│  - Real-time updates (5-min intervals possible)          │
│  - Chart.js visualizations                               │
│  - P0 indicators dashboard                               │
└─────────────────────────────────────────────────────────┘
```

### Hybrid Data Strategy

**Problem**: metals.dev has 100 calls/month limit  
**Solution**: Dual-layer approach

| Layer | Source | Frequency | Purpose |
|-------|--------|-----------|---------|
| **Baseline** | metals.dev API | 8 hours | LBMA prices, calibration |
| **Real-time** | yfinance futures | Every request | Live spot proxy |

**Result**: Real-time dashboard with ~90 API calls/month (well under limit)

## Data Sources

### Primary APIs

| Source | Type | Update Frequency | Cache TTL | Authentication |
|--------|------|------------------|-----------|----------------|
| **yfinance** | Free | Real-time | None | No |
| **metals.dev** | Free (100/mo) | 8 hours | 480 min | API Key |
| **FRED** | Free | Daily | None | No |
| **CME Group** | Free | Daily | 1440 min | No |
| **SHFE** | Free | 30 min | Manual scrape | No |

### Data Endpoints

#### Real-time (yfinance)
- `SI=F` - Silver Futures
- `GC=F` - Gold Futures  
- `DX-Y.NYB` - USD Index
- `SLV` - Options chains

#### Cached
- `https://api.metals.dev/v1/latest` - Spot prices, LBMA
- `https://www.cmegroup.com/delivery_reports/Silver_stocks.xls` - Inventory
- `https://www.cmegroup.com/delivery_reports/MetalsIssuesAndStopsReport.pdf` - Deliveries
- `https://www.shfe.com.cn/reports/marketdata/delayedquotes/` - SHFE (via Selenium)

## P0 Indicators

### Implemented (17/20)

#### SHFE Contract Metrics (7)
1. **OI_ag2603** - Main contract Open Interest
2. **VOL_ag2603** - Daily Volume
3. **Turnover_ag2603** - VOL/OI ratio
4. **ΔOI_ag2603** - Daily OI change
5. **Front6_OI_sum_SHFE** - Sum of nearest 6 months OI
6. **OI_concentration_2603** - Main contract concentration
7. **Curve_slope_SHFE_3m6m** - ag2606 - ag2603 spread

#### COMEX Inventory (4)
8. **COMEX_Silver_Registered** - Deliverable stocks
9. **COMEX_Silver_Eligible** - Potential supply
10. **ΔCOMEX_Registered** - Daily change tracking
11. **Registered_to_Total** - Reg/(Reg+Elig) ratio

#### COMEX Delivery (2)
12. **COMEX_IssuesStops_Silver** - Daily issued/stopped contracts
13. **COMEX_Deliveries_MTD** - Month-to-date cumulative

#### Basis & Premium (4)
14. **Paper_to_Physical** - COMEX OI / Registered
15. **Basis_USD_COMEX** - Futures - Spot
16. **Shanghai_Premium_Implied** - SHFE vs Overseas
17. **XAGUSD_Spot** - Real-time spot price

### Not Implemented (3)
- **SHFE_Daily_Warrant_Ag** - Exchange API unavailable
- **SHFE_Weekly_Inventory_Ag** - Exchange API unavailable
- **SGE_SHAG_vs_Overseas** - Requires SGE API integration

## Maintenance

### Daily Tasks
None (fully automated)

### Periodic Tasks

#### SHFE Data Refresh (Every 30 minutes)
```bash
python scrape_shfe_selenium.py
```

**Automation Option** (cron):
```bash
# Add to crontab -e
*/30 * * * * cd /home/jeffey/vscode/SLV_PRICE && python scrape_shfe_selenium.py
```

#### Clear Old Time-Series Data (Weekly)
```bash
# Keep last 7 days only
python -c "import pandas as pd; from datetime import datetime, timedelta; df = pd.read_csv('p0_timeseries.csv'); df['timestamp'] = pd.to_datetime(df['timestamp']); cutoff = datetime.now() - timedelta(days=7); df[df['timestamp'] >= cutoff].to_csv('p0_timeseries.csv', index=False)"
```

### Monitoring

#### Check API Usage (metals.dev)
Look for this log message:
```
[metals.dev] API call successful - cached for 8 hours
```
Should appear ~3 times per day

#### Verify Data Freshness
```bash
curl -s http://localhost:5000/api/data | python -m json.tool | grep "source"
```

Expected:
- `"source": "Real-time"` - Futures, Options
- `"source": "Cache"` - CME, metals.dev
- `"source": "Cached JSON"` - SHFE

## Development

### Adding New P0 Indicators

1. **Update `data_fetcher.py`**:
```python
# In get_all_data_and_store():
if condition:
    p0_data['New_Indicator_Name'] = calculation
```

2. **Update `p0_storage.py`**:
```python
# Add to self.columns list:
'New_Indicator_Name',
```

3. **Update `static/script.js`**:
```javascript
// In updateDashboard():
document.getElementById('new-metric').textContent = 
    formatValue(p0.New_Indicator_Name);

// In renderP0Chart():
{ label: 'New', value: p0.New_Indicator_Name, color: 'rgba(...)' }
```

4. **Update `templates/index.html`**:
```html
<div id="new-metric">N/A</div>
```

### Running Tests
```bash
# Test data fetcher
python data_fetcher.py

# Test SHFE scraper
python scrape_shfe_selenium.py

# Test PDF parser
python cme_pdf_parser.py

# Test time-series storage
python p0_storage.py
```

### Key Configuration

#### Environment Variables
- `METALS_DEV_KEY` - metals.dev API key (required for accurate spot prices)

#### Cache TTLs (in `data_fetcher.py`)
- SHFE: 1800 seconds (30 min)
- CME: 86400 seconds (24 hours)
- metals.dev: 28800 seconds (8 hours)
- CME PDFs: 86400 seconds (24 hours)

### Troubleshooting

#### P0 Indicators Show N/A
1. Check SHFE data: `cat shfe_market_data.json`
2. Run scraper: `python scrape_shfe_selenium.py`
3. Check backend: `curl http://localhost:5000/api/data | grep p0_indicators`
4. Verify field names match between `data_fetcher.py` and `script.js`

#### USD Index Incorrect
- Should use `DX-Y.NYB` ticker, not FRED `DTWEXBGS`

#### metals.dev Quota Exceeded
- Check cache: `ls -lh cache/metals_dev_prices.json`
- Verify 8-hour TTL in code
- Fallback to futures proxy automatically

## API Rate Limits

| Service | Limit | Current Usage | Safety Margin |
|---------|-------|---------------|---------------|
| metals.dev | 100/month | ~90/month | ✅ 10% buffer |
| yfinance | Unlimited | High | ✅ No limit |
| FRED | Unlimited | Low | ✅ No limit |
| CME | Fair use | Daily | ✅ Cached |

## Version History

- **v1.0** - Initial dashboard with basic futures/inventory
- **v2.0** - Added P0 indicators, SHFE integration, PDF parsing, hybrid data strategy

## License

Internal use only

## Support

For issues or questions, contact: [Your Contact Info]
