#!/usr/bin/env python3
import os
import json
import requests
import yfinance as yf
from datetime import datetime
from db_manager import DBManager
import pandas as pd
from io import BytesIO
import pytz
import sys

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
CACHE_DIR = 'cache'
MSG_ID_FILE = os.path.join(CACHE_DIR, 'discord_msg_id.txt')

def get_est_time():
    return datetime.now(pytz.timezone('America/New_York'))

def read_cache(name, ttl_hours=24):
    """Read cache if valid within TTL"""
    path = os.path.join(CACHE_DIR, f'{name}.json')
    try:
        if os.path.exists(path):
            age_hours = (datetime.now().timestamp() - os.path.getmtime(path)) / 3600
            if age_hours < ttl_hours:
                with open(path) as f:
                    return json.load(f), round(age_hours, 1)
    except:
        pass
    return None, None

def write_cache(name, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, f'{name}.json'), 'w') as f:
        json.dump(data, f)

# ============ HOURLY DATA (Real-time) ============

def fetch_xagusd():
    """XAG/USD spot price"""
    try:
        t = yf.Ticker('SI=F')
        return t.info.get('regularMarketPrice')
    except:
        return None

def fetch_shanghai_td():
    """Shanghai Ag T+D"""
    try:
        url = 'https://www.barchart.com/futures/quotes/XOH26/overview'
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=15)
        import re
        
        data = {}
        cny_rate = yf.Ticker('CNY=X').history(period='1d')['Close'].iloc[-1]
        
        price_match = re.search(r'"lastPrice":([0-9,]+)', resp.text)
        if price_match:
            price_cny = float(price_match.group(1).replace(',', ''))
            data['price_cny_kg'] = price_cny
            data['price_usd_oz'] = round((price_cny / cny_rate) / 32.1507, 2)
        
        pct_match = re.search(r'"percentChange":(-?[0-9.]+)', resp.text)
        if pct_match:
            data['change_pct'] = round(float(pct_match.group(1)) * 100, 2)
        
        raw = re.search(r'&quot;raw&quot;:\{[^}]*&quot;volume&quot;:([0-9]+)[^}]*&quot;openInterest&quot;:([0-9]+)', resp.text)
        if raw:
            data['volume'] = int(raw.group(1))
            data['oi'] = int(raw.group(2))
        
        data['cny_rate'] = round(cny_rate, 4)
        return data if data else None
    except Exception as e:
        print(f"⚠ SHFE failed: {e}")
        return None

def fetch_comex_futures():
    """COMEX silver futures"""
    try:
        si = yf.Ticker('SI=F')
        info = si.info
        return {
            'price': info.get('regularMarketPrice'),
            'volume': info.get('volume', 0),
            'oi': info.get('openInterest', 0),
            'prev_close': info.get('previousClose')
        }
    except:
        return None

def fetch_slv_price():
    """SLV ETF price only (hourly)"""
    try:
        slv = yf.Ticker('SLV')
        info = slv.info
        return {
            'price': info.get('regularMarketPrice'),
            'change_pct': round(((info.get('regularMarketPrice', 0) - info.get('previousClose', 1)) / info.get('previousClose', 1)) * 100, 2),
            'volume': info.get('volume', 0)
        }
    except:
        return None

# ============ DAILY DATA (24h cache) ============

def fetch_usdcny(force=False):
    """USD/CNY rate - daily"""
    cached, age = read_cache('usdcny', 24)
    if cached and not force:
        print(f"✓ USD/CNY (cached {age}h)")
        return cached, True
    
    try:
        rate = yf.Ticker('CNY=X').history(period='1d')['Close'].iloc[-1]
        data = {'rate': round(rate, 4), 'ts': datetime.now().isoformat()}
        write_cache('usdcny', data)
        print(f"✓ USD/CNY: {rate:.4f} (fresh)")
        return data, False
    except:
        return cached, True if cached else (None, False)

def fetch_slv_holdings(force=False):
    """SLV ETF holdings - daily"""
    cached, age = read_cache('slv_holdings', 24)
    prev_holdings = cached.get('holdings_oz') if cached else None
    
    if cached and not force:
        print(f"✓ SLV holdings (cached {age}h)")
        return cached, True
    
    try:
        url = 'https://www.ishares.com/us/products/239855/ishares-silver-trust-fund'
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        import re
        match = re.search(r'(\d{3},\d{3},\d{3}\.\d+)', resp.text)
        if match:
            holdings = float(match.group(1).replace(',', ''))
            change = int(holdings - prev_holdings) if prev_holdings else None
            data = {'holdings_oz': holdings, 'change': change, 'ts': datetime.now().isoformat()}
            write_cache('slv_holdings', data)
            print(f"✓ SLV holdings: {holdings:,.0f} oz (fresh)")
            return data, False
    except:
        pass
    return cached, True if cached else (None, False)

def fetch_comex_inventory(force=False):
    """COMEX physical inventory - daily"""
    cached, age = read_cache('comex_inv', 24)
    if cached and not force:
        print(f"✓ COMEX inventory (cached {age}h)")
        return cached, True
    
    try:
        url = 'https://www.cmegroup.com/delivery_reports/Silver_stocks.xls'
        resp = requests.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
        df = pd.read_excel(BytesIO(resp.content), engine='xlrd')
        
        registered = eligible = None
        for _, row in df.iterrows():
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
                'ts': datetime.now().isoformat()
            }
            write_cache('comex_inv', data)
            print(f"✓ COMEX inventory: {registered:,.0f} oz (fresh)")
            return data, False
    except Exception as e:
        print(f"⚠ COMEX inventory failed: {e}")
    
    return cached, True if cached else (None, False)

def send_discord(msg):
    if not WEBHOOK_URL:
        return
    
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    # Try to edit existing message
    if os.path.exists(MSG_ID_FILE):
        with open(MSG_ID_FILE) as f:
            msg_id = f.read().strip()
        if msg_id:
            edit_url = f"{WEBHOOK_URL}/messages/{msg_id}"
            resp = requests.patch(edit_url, json={"content": msg})
            if resp.status_code == 200:
                return
    
    # Send new message and save ID
    resp = requests.post(f"{WEBHOOK_URL}?wait=true", json={"content": msg})
    if resp.status_code == 200:
        data = resp.json()
        with open(MSG_ID_FILE, 'w') as f:
            f.write(data.get('id', ''))

def main():
    force = '--force' in sys.argv
    if force:
        print("Force refresh enabled")
    
    db = DBManager()
    
    # === HOURLY DATA ===
    print("\n=== Hourly Data (Real-time) ===")
    xagusd = fetch_xagusd()
    shfe = fetch_shanghai_td()
    comex = fetch_comex_futures()
    slv = fetch_slv_price()
    
    if xagusd:
        db.insert('XAGUSD', price=xagusd)
        print(f"✓ XAG/USD: ${xagusd}")
    if comex:
        db.insert('COMEX', price=comex['price'], raw_data=json.dumps(comex))
        print(f"✓ COMEX: ${comex['price']}")
    if shfe:
        db.insert('SHFE', raw_data=json.dumps(shfe))
        print(f"✓ SHFE: ${shfe.get('price_usd_oz')}/oz")
    if slv:
        db.insert('SLV', price=slv['price'], raw_data=json.dumps(slv))
        print(f"✓ SLV: ${slv['price']}")
    
    # === DAILY DATA (24h cache) ===
    print("\n=== Daily Data (24h cache) ===")
    usdcny, usdcny_cached = fetch_usdcny(force)
    slv_hold, slv_hold_cached = fetch_slv_holdings(force)
    comex_inv, comex_inv_cached = fetch_comex_inventory(force)
    
    if comex_inv:
        db.insert('COMEX_INV', raw_data=json.dumps(comex_inv))
    
    # === DISCORD MESSAGE ===
    est = get_est_time()
    ts = est.strftime('%Y-%m-%d %I:%M %p EST')
    
    msg = f"**📊 Silver Market Update** - {ts}\n\n"
    
    # Spot & Futures (30min)
    msg += "**💹 Real-time Prices** `[30min]`\n"
    if xagusd:
        msg += f"• XAG/USD Spot: **${xagusd:.2f}**/oz\n"
    if comex:
        msg += f"• COMEX Futures: **${comex['price']:.2f}**/oz"
        if comex.get('oi'):
            msg += f" (OI: {comex['oi']:,})"
        msg += "\n"
    if shfe:
        msg += f"• SHFE Ag: **${shfe.get('price_usd_oz')}**/oz (¥{shfe.get('price_cny_kg', 0):,.0f}/kg)"
        if shfe.get('change_pct') is not None:
            msg += f" {shfe['change_pct']:+.2f}%"
        msg += "\n"
        if comex and shfe.get('price_usd_oz'):
            premium = shfe['price_usd_oz'] - comex['price']
            msg += f"  └ Shanghai Premium: **${premium:+.2f}**\n"
    if slv:
        arrow = "🔺" if slv['change_pct'] > 0 else "🔻"
        msg += f"• SLV ETF: **${slv['price']:.2f}** {arrow}{slv['change_pct']:+.2f}%\n"
    
    # Daily data
    msg += f"\n**📦 Physical Holdings** `[Daily{'*' if not force else ' ✓'}]`\n"
    if comex_inv:
        msg += f"• COMEX Registered: **{comex_inv['registered']:,.0f}** oz\n"
        msg += f"• COMEX Eligible: **{comex_inv['eligible']:,.0f}** oz\n"
        msg += f"  └ Reg/Total: {comex_inv['reg_ratio']}%\n"
    if slv_hold:
        msg += f"• SLV Trust: **{slv_hold['holdings_oz']:,.0f}** oz"
        if slv_hold.get('change') is not None:
            msg += f" ({slv_hold['change']:+,} oz)"
        msg += "\n"
    
    msg += f"\n**💱 FX Rate** `[Daily{'*' if not force else ' ✓'}]`\n"
    if usdcny:
        msg += f"• USD/CNY: **{usdcny['rate']}**\n"
    
    # Metrics
    if comex and comex_inv and comex_inv.get('registered'):
        oi = comex.get('oi', 0)
        if oi:
            paper_oz = oi * 5000
            ratio = round(paper_oz / comex_inv['registered'], 2)
            msg += f"\n**📈 Key Metrics**\n"
            msg += f"• Paper/Physical: **{ratio}x**\n"
            if xagusd and comex:
                basis = round(comex['price'] - xagusd, 3)
                msg += f"• Futures Basis: **${basis:+.3f}**\n"
    
    msg += "\n─────────────────────────────\n"
    msg += "`*` cached (24h) │ `Paper/Physical` = (OI×5000oz) / Registered │ `Basis` = Futures - Spot"
    
    send_discord(msg)
    print("\n✓ Discord notification sent")

if __name__ == '__main__':
    main()
