#!/usr/bin/env python3
import os
import json
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
from db_manager import DBManager

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

def generate_chart(data):
    comex_data = [d for d in data if d['source'] == 'COMEX' and d['price']]
    if not comex_data:
        return None
    
    timestamps = [datetime.fromisoformat(d['timestamp']) for d in comex_data]
    prices = [d['price'] for d in comex_data]
    
    plt.figure(figsize=(10, 5))
    plt.plot(timestamps, prices, marker='o', linewidth=2)
    plt.title('Silver Price - 7 Day Trend', fontsize=14, fontweight='bold')
    plt.xlabel('Date')
    plt.ylabel('Price (USD)')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    chart_path = '/tmp/silver_trend.png'
    plt.savefig(chart_path, dpi=100)
    plt.close()
    return chart_path

def send_discord_image(chart_path):
    if not WEBHOOK_URL:
        print("No webhook URL configured")
        return
    
    with open(chart_path, 'rb') as f:
        files = {'file': ('silver_trend.png', f, 'image/png')}
        payload = {
            'content': f"**Daily Silver Report** - {datetime.utcnow().strftime('%Y-%m-%d')}\n7-day price trend chart"
        }
        requests.post(WEBHOOK_URL, data=payload, files=files)

def main():
    db = DBManager()
    data = db.get_recent(days=7)
    
    if not data:
        print("No data available")
        return
    
    chart_path = generate_chart(data)
    if chart_path:
        send_discord_image(chart_path)
        print(f"✓ Chart sent to Discord")
    else:
        print("No COMEX data to chart")

if __name__ == '__main__':
    main()
