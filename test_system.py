#!/usr/bin/env python3
import os
import requests
import yfinance as yf
from datetime import datetime
from db_manager import DBManager

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

def test_system():
    print("=== Testing Silver Scraper System ===\n")
    
    # Test 1: Database
    print("1. Testing database...")
    db = DBManager()
    print("   ✓ Database initialized\n")
    
    # Test 2: COMEX data
    print("2. Fetching COMEX data...")
    si = yf.Ticker('SI=F')
    price = si.info.get('regularMarketPrice')
    print(f"   ✓ COMEX Silver: ${price}\n")
    
    # Test 3: Store data
    print("3. Storing to database...")
    db.insert('COMEX', price=price)
    print("   ✓ Data stored\n")
    
    # Test 4: Discord webhook
    print("4. Testing Discord webhook...")
    if WEBHOOK_URL:
        msg = f"**Test Message** - {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\nCOMEX: ${price}"
        response = requests.post(WEBHOOK_URL, json={"content": msg})
        if response.status_code == 204:
            print("   ✓ Discord notification sent\n")
        else:
            print(f"   ✗ Discord failed: {response.status_code}\n")
    else:
        print("   ⚠ No webhook URL configured\n")
    
    print("=== All Tests Complete ===")

if __name__ == '__main__':
    test_system()
