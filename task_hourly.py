#!/usr/bin/env python3
import os
import json
import requests
import yfinance as yf
from datetime import datetime, timedelta
from db_manager import DBManager
import pandas as pd
from io import BytesIO
from bs4 import BeautifulSoup
import pytz

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

def get_est_time():
    """Get current time in EST"""
    return datetime.now(pytz.timezone('America/New_York'))

def scrape_shfe():
    """Fetch SHFE silver data from Barchart with real-time USD/CNY"""
    try:
        # Get real-time USD/CNY rate
        usdcny = yf.Ticker('CNY=X')
        cny_rate = usdcny.history(period='1d')['Close'].iloc[-1]
        
        url = 'https://www.barchart.com/futures/quotes/XOH26/overview'
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        import re
        data = {}
        
        # Extract price from raw JSON
        price_match = re.search(r'"lastPrice":([0-9,]+)', response.text)
        if price_match:
            price_cny_per_kg = float(price_match.group(1).replace(',', ''))
            data['price_cny_per_kg'] = price_cny_per_kg
            data['price_usd_per_oz'] = round((price_cny_per_kg / cny_rate) / 32.1507, 2)
        
        pct_match = re.search(r'"percentChange":(-?[0-9.]+)', response.text)
        if pct_match:
            data['change_pct'] = round(float(pct_match.group(1)) * 100, 2)
        
        # Extract volume, OI, RS from HTML-encoded raw object
        raw_obj = re.search(r'&quot;raw&quot;:\{[^}]*&quot;volume&quot;:([0-9]+)[^}]*&quot;openInterest&quot;:([0-9]+)[^}]*&quot;relativeStrength14d&quot;:([0-9.]+)[^}]*\}', response.text)
        if raw_obj:
            data['volume'] = int(raw_obj.group(1))
            data['open_interest'] = int(raw_obj.group(2))
            data['relative_strength'] = float(raw_obj.group(3))
        
        if data:
            print(f"✓ SHFE Mar'26: ${data.get('price_usd_per_oz', 'N/A')}/oz (CNY: {cny_rate:.2f})")
            return data
        
        return None
    except Exception as e:
        print(f"⚠ SHFE data failed: {str(e)[:60]}")
        return None

def fetch_xagusd_spot():
    """Fetch XAG/USD spot price from Barchart"""
    try:
        url = 'https://www.barchart.com/forex/quotes/%5EXAGUSD'
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        import re
        # Extract price from JSON data
        price_match = re.search(r'"lastPrice":"([0-9,.]+)"', response.text)
        if price_match:
            return float(price_match.group(1).replace(',', ''))
        return None
    except Exception as e:
        print(f"XAG/USD failed: {str(e)[:60]}")
        return None

def fetch_shanghai_spot():
    """Fetch Shanghai Ag T+D from goldsilver.ai"""
    try:
        url = 'https://goldsilver.ai/metal-prices/shanghai-silver-price'
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        
        import re
        # Extract Shanghai price in USD
        price_match = re.search(r'(\d+\.\d+)</p><p[^>]*>USD/OZ', response.text)
        if price_match:
            return float(price_match.group(1))
        return None
    except:
        return None

def fetch_lbma_holdings():
    """Fetch LBMA silver holdings - cached daily"""
    cache_file = 'cache_lbma.json'
    
    # Check cache (24 hour TTL)
    try:
        if os.path.exists(cache_file):
            mtime = os.path.getmtime(cache_file)
            age_hours = (datetime.now().timestamp() - mtime) / 3600
            if age_hours < 24:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    print(f"✓ LBMA (cached {age_hours:.1f}h ago)")
                    return data.get('holdings')
    except:
        pass
    
    # LBMA doesn't have a public API - return placeholder
    # In production, you'd scrape from LBMA website or use a data provider
    print("⚠ LBMA: No live API available")
    return None

def fetch_comex():
    """Fetch COMEX silver Mar'26 futures data"""
    try:
        # Use generic silver futures (front month)
        si = yf.Ticker('SI=F')
        info = si.info
        
        data = {
            'price': info.get('regularMarketPrice'),
            'volume': info.get('volume', 0),
            'open_interest': info.get('openInterest', 0),
            'prev_close': info.get('previousClose'),
        }
        
        return data
    except Exception as e:
        print(f"COMEX data failed: {e}")
        return None
    """Fetch COMEX silver Mar'26 futures data"""
    try:
        # Use generic silver futures (front month)
        si = yf.Ticker('SI=F')
        info = si.info
        
        data = {
            'price': info.get('regularMarketPrice'),
            'volume': info.get('volume', 0),
            'open_interest': info.get('openInterest', 0),
            'prev_close': info.get('previousClose'),
        }
        
        return data
    except Exception as e:
        print(f"COMEX data failed: {e}")
        return None

def fetch_comex_inventory():
    """Fetch COMEX silver inventory from CME XLS file"""
    cache_file = 'cache_comex_inv.json'
    
    # Try cache first (valid for 24 hours)
    try:
        if os.path.exists(cache_file):
            mtime = os.path.getmtime(cache_file)
            age_hours = (datetime.now().timestamp() - mtime) / 3600
            if age_hours < 24:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    print(f"✓ Inventory (cached {age_hours:.1f}h ago)")
                    return data
    except:
        pass
    
    # Try live fetch
    try:
        url = 'https://www.cmegroup.com/delivery_reports/Silver_stocks.xls'
        response = requests.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
        df = pd.read_excel(BytesIO(response.content), engine='xlrd')
        
        # Find TOTAL REGISTERED and TOTAL ELIGIBLE rows
        registered = eligible = None
        for i, row in df.iterrows():
            label = str(row.iloc[0]).strip()
            if label == 'TOTAL REGISTERED':
                registered = float(row.iloc[7])
            elif label == 'TOTAL ELIGIBLE':
                eligible = float(row.iloc[7])
        
        if registered and eligible:
            data = {
                'registered': registered,
                'eligible': eligible,
                'total': registered + eligible,
                'reg_ratio': round(registered / (registered + eligible) * 100, 2),
                'timestamp': datetime.now().isoformat()
            }
            
            with open(cache_file, 'w') as f:
                json.dump(data, f)
            
            print(f"✓ Inventory: {registered:,.0f} oz registered (fresh)")
            return data
    except Exception as e:
        print(f"⚠ COMEX inventory fetch failed: {str(e)[:50]}")
    
    # Fallback to old cache
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            data = json.load(f)
            print(f"⚠ Using stale inventory cache")
            return data
    
    return None

def fetch_slv_data():
    """Fetch iShares SLV ETF data"""
    try:
        slv = yf.Ticker('SLV')
        info = slv.info
        hist = slv.history(period='3d')
        
        current_price = info.get('regularMarketPrice') or hist['Close'].iloc[-1]
        prev_close = info.get('previousClose') or hist['Close'].iloc[-2]
        change_pct = ((current_price - prev_close) / prev_close) * 100
        
        # Scrape actual holdings from iShares
        current_holdings = None
        try:
            url = 'https://www.ishares.com/us/products/239855/ishares-silver-trust-fund'
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=15)
            
            import re
            # Extract holdings in ounces (format: 516,398,256.40)
            holdings_match = re.search(r'(\d{3},\d{3},\d{3}\.\d+)', response.text)
            if holdings_match:
                current_holdings = float(holdings_match.group(1).replace(',', ''))
        except:
            pass
        
        # Calculate holdings change from database
        holdings_change = None
        try:
            import sqlite3
            conn = sqlite3.connect('silver_data.db')
            cur = conn.cursor()
            # Get yesterday's holdings
            yesterday = cur.execute(
                "SELECT raw_data FROM silver_data WHERE source='SLV' AND date(timestamp) = date('now', '-1 day') ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            if yesterday:
                prev_data = json.loads(yesterday[0])
                prev_holdings = prev_data.get('holdings_oz')
                if prev_holdings and current_holdings:
                    holdings_change = current_holdings - prev_holdings
            conn.close()
        except:
            pass
        
        return {
            'price': round(current_price, 2),
            'prev_close': round(prev_close, 2),
            'change_pct': round(change_pct, 2),
            'volume': info.get('volume', 0),
            'holdings_oz': current_holdings,
            'holdings_change': holdings_change
        }
    except Exception as e:
        print(f"SLV data failed: {e}")
        return None

def calculate_metrics(comex_price, inventory, slv_data, xagusd_price=None):
    """Calculate derived metrics"""
    metrics = {}
    
    if xagusd_price and comex_price:
        # Basis: XAG/USD Spot - COMEX Futures
        metrics['basis'] = round(xagusd_price - comex_price, 3)
    
    if inventory and comex_price:
        # Paper to Physical ratio (simplified - needs actual OI data)
        si = yf.Ticker('SI=F')
        try:
            oi = si.info.get('openInterest', 0)
            if oi and inventory['registered']:
                # Each contract = 5000 oz
                paper_oz = oi * 5000
                metrics['paper_to_physical'] = round(paper_oz / inventory['registered'], 2)
        except:
            pass
    
    return metrics

def send_discord(message):
    if not WEBHOOK_URL:
        print("No webhook URL configured")
        return
    requests.post(WEBHOOK_URL, json={"content": message})

def main():
    db = DBManager()
    
    # Fetch all data
    xagusd_spot = fetch_xagusd_spot()
    shanghai_spot = fetch_shanghai_spot()
    comex_data = fetch_comex()
    inventory = fetch_comex_inventory()  # Already has daily cache
    lbma_holdings = fetch_lbma_holdings()
    slv_data = fetch_slv_data()
    shfe_data = scrape_shfe()
    
    comex_price = comex_data['price'] if comex_data else None
    metrics = calculate_metrics(comex_price, inventory, slv_data, xagusd_spot)
    
    # Store in database
    if xagusd_spot:
        db.insert('XAGUSD', price=xagusd_spot)
        print(f"✓ XAG/USD Spot: ${xagusd_spot}")
    
    if shanghai_spot:
        db.insert('SHANGHAI_SPOT', price=shanghai_spot)
        print(f"✓ Shanghai Ag T+D: ${shanghai_spot}")
    
    if comex_data:
        db.insert('COMEX', price=comex_price, raw_data=json.dumps(comex_data))
        print(f"✓ COMEX Mar'26: ${comex_price}")
    
    if inventory:
        db.insert('COMEX_INV', raw_data=json.dumps(inventory))
    
    if slv_data:
        db.insert('SLV', price=slv_data['price'], raw_data=json.dumps(slv_data))
        print(f"✓ SLV: ${slv_data['price']} ({slv_data['change_pct']:+.2f}%)")
    
    if shfe_data:
        db.insert('SHFE', raw_data=json.dumps(shfe_data))
    
    # Discord notification with EST time
    est_time = get_est_time()
    timestamp = est_time.strftime('%Y-%m-%d %I:%M %p EST')
    msg = f"**📊 Silver Market Update** - {timestamp}\n\n"
    
    # Spot Prices
    msg += "**Spot Prices:**\n"
    if xagusd_spot:
        msg += f"💎 XAG/USD: ${xagusd_spot}/oz"
        if shfe_data:
            cny_rate = yf.Ticker('CNY=X').history(period='1d')['Close'].iloc[-1]
            msg += f" (USD/CNY: {cny_rate:.4f})"
        msg += "\n"
    if shanghai_spot:
        msg += f"🇨🇳 Shanghai Ag T+D: ${shanghai_spot}/oz\n"
    
    # Futures Prices
    msg += f"\n**Futures (Mar '26):**\n"
    if comex_data:
        msg += f"💰 COMEX: ${comex_price}/oz\n"
        if xagusd_spot:
            futures_premium = comex_price - xagusd_spot
            msg += f"   vs Spot: ${futures_premium:+.2f}\n"
        if comex_data.get('volume'):
            msg += f"   Vol: {comex_data['volume']:,}\n"
        if comex_data.get('open_interest'):
            msg += f"   OI: {comex_data['open_interest']:,}\n"
    
    if shfe_data:
        msg += f"🇨🇳 SHFE: ${shfe_data.get('price_usd_per_oz', 'N/A')}/oz (¥{shfe_data.get('price_cny_per_kg', 'N/A'):,.0f}/kg)\n"
        if shfe_data.get('change_pct') is not None:
            msg += f"   Change: {shfe_data['change_pct']:+.2f}%\n"
        if shfe_data.get('volume'):
            msg += f"   Vol: {shfe_data['volume']:,}\n"
        if shfe_data.get('open_interest'):
            msg += f"   OI: {shfe_data['open_interest']:,}\n"
        if shfe_data.get('relative_strength'):
            msg += f"   RS(14): {shfe_data['relative_strength']}\n"
        
        # Calculate SHFE vs COMEX premium
        if comex_price and shfe_data.get('price_usd_per_oz'):
            premium = shfe_data['price_usd_per_oz'] - comex_price
            msg += f"   Premium vs COMEX: ${premium:+.2f}\n"
    
    # SLV ETF
    if slv_data:
        msg += f"\n**SLV ETF:**\n"
        arrow = "🔺" if slv_data['change_pct'] > 0 else "🔻"
        msg += f"{arrow} ${slv_data['price']} ({slv_data['change_pct']:+.2f}%)\n"
        if slv_data.get('holdings_oz'):
            msg += f"🏦 Holdings: {slv_data['holdings_oz']:,.0f} oz"
            if slv_data.get('holdings_change'):
                msg += f" ({int(slv_data['holdings_change']):+,})"
            msg += "\n"
    
    # Inventory
    msg += f"\n**Physical Holdings:**\n"
    if inventory:
        msg += f"📦 COMEX Registered: {inventory['registered']:,.0f} oz\n"
        msg += f"📦 COMEX Eligible: {inventory['eligible']:,.0f} oz\n"
        msg += f"   Reg/Total: {inventory['reg_ratio']}%\n"
    if lbma_holdings:
        msg += f"🏛️ LBMA: {lbma_holdings:,.0f} oz\n"
    
    # Metrics
    if metrics:
        msg += f"\n**Metrics:**\n"
        if 'basis' in metrics:
            msg += f"📈 Futures-Spot Spread (XAG/USD - COMEX): ${metrics['basis']}\n"
        if 'paper_to_physical' in metrics:
            msg += f"⚖️ Paper/Physical Ratio: {metrics['paper_to_physical']}x\n"
    
    send_discord(msg)

if __name__ == '__main__':
    main()
