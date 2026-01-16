#!/usr/bin/env python3
"""
SHFE data scraper using direct API (no Chrome needed)
"""
import requests
from datetime import datetime
import json

def fetch_shfe_data():
    """Fetch SHFE silver data via API"""
    today = datetime.now().strftime('%Y%m%d')
    
    # SHFE provides JSON API for daily data
    url = f'https://www.shfe.com.cn/data/dailydata/kx/kx{today}.dat'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Referer': 'https://www.shfe.com.cn/',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Extract silver (ag) contracts
        ag_data = []
        for item in data.get('o_curinstrument', []):
            if item.get('PRODUCTID') == 'ag':
                ag_data.append({
                    'contract': item.get('INSTRUMENTID'),
                    'price': item.get('CLOSEPRICE'),
                    'volume': item.get('VOLUME'),
                    'open_interest': item.get('OPENINTEREST'),
                    'oi_change': item.get('OPENINTERESTCHG')
                })
        
        return ag_data
    
    except Exception as e:
        print(f"SHFE API error: {e}")
        return None

if __name__ == '__main__':
    data = fetch_shfe_data()
    if data:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\nFound {len(data)} silver contracts")
    else:
        print("Failed to fetch SHFE data")
