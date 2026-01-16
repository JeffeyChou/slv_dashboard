# Enhanced Silver Scraper - Data Fields

## Data Sources & Metrics

### 1. COMEX Futures Price
- **Source**: yfinance (SI=F)
- **Field**: `XAGUSD_Spot` / Real-time spot price
- **Update**: Every hour
- **Reliability**: ✅ High

### 2. COMEX Inventory
- **Source**: CME Group delivery reports
- **Fields**:
  - `COMEX_Silver_Registered` - Deliverable stocks (oz)
  - `COMEX_Silver_Eligible` - Potential supply (oz)
  - `Registered_to_Total` - Reg/(Reg+Elig) ratio (%)
- **Update**: Daily (cached 24h)
- **Reliability**: ⚠️ Medium (CME may timeout, uses cache)

### 3. SLV ETF Data
- **Source**: yfinance (SLV)
- **Fields**:
  - Price (current)
  - Previous close
  - Change percentage
  - Volume
  - Holdings (approximate oz)
- **Update**: Every hour
- **Reliability**: ✅ High

### 4. Calculated Metrics
- **Basis_USD_COMEX**: Futures - Spot (COMEX - SLV)
- **Paper_to_Physical**: COMEX OI / Registered inventory
- **ΔCOMEX_Registered**: Daily change (requires historical data)

### 5. SHFE Data (Optional)
- **Source**: SHFE API
- **Fields**: Contract prices, volume, open interest
- **Update**: Best effort (often delayed 1 day)
- **Reliability**: ⚠️ Low (API restrictions)

## Discord Notification Format

```
📊 Silver Market Update - 2026-01-16 21:45 UTC

Prices:
💰 COMEX Futures: $89.72
🔻 SLV ETF: $81.02 (-2.76%)

COMEX Inventory:
📦 Registered: 278,500,000 oz
📦 Eligible: 42,300,000 oz
📊 Reg/Total: 86.82%

Metrics:
📈 Basis: $8.70
⚖️ Paper/Physical: 45.2x

SLV Holdings:
🏦 550,000,000 oz
```

## Database Storage

All data stored in `silver_data.db`:
- Timestamp
- Source (COMEX, SLV, COMEX_INV, SHFE)
- Price (if applicable)
- Raw JSON data

## Caching Strategy

| Data | Cache Duration | Fallback |
|------|----------------|----------|
| COMEX Price | None (real-time) | - |
| SLV Data | None (real-time) | - |
| COMEX Inventory | 24 hours | Stale cache |
| SHFE | Best effort | Skip if unavailable |

## Missing Metrics (Require Additional Work)

### COMEX Delivery Data
- **COMEX_IssuesStops_Silver** - Requires PDF parsing
- **COMEX_Deliveries_MTD** - Requires PDF parsing
- **Source**: CME delivery reports PDFs
- **Implementation**: See `cme_pdf_parser.py` in main repo

### Accurate SLV Holdings
- **Current**: Estimated from shares outstanding
- **Accurate**: Requires scraping iShares product page
- **URL**: https://www.ishares.com/us/products/239855/

### Delta Calculations
- **ΔCOMEX_Registered**: Requires storing previous day's value
- **Implementation**: Query database for yesterday's inventory

## Testing

```bash
# Test full scraper
./run_hourly.sh

# View database
python3 -c "import sqlite3; conn = sqlite3.connect('silver_data.db'); 
cur = conn.cursor(); 
rows = cur.execute('SELECT * FROM silver_data ORDER BY timestamp DESC LIMIT 5').fetchall(); 
print('\n'.join([str(r) for r in rows]))"
```

## Next Steps

1. ✅ COMEX price - Working
2. ✅ SLV data - Working
3. ✅ COMEX inventory - Working (with cache)
4. ✅ Basic metrics - Working
5. ⏳ PDF parsing for delivery data - Optional
6. ⏳ Accurate SLV holdings - Optional
7. ⏳ Historical delta calculations - Optional
