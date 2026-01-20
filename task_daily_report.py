#!/usr/bin/env python3
import os
import json
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from db_manager import DBManager
from data_fetcher import SilverDataFetcher
import pandas as pd

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

def get_daily_data(days=30):
    """Get daily aggregated data from database"""
    db = DBManager()
    data = db.get_recent(days=days)
    
    # Group by date and get latest values per day
    daily_data = {}
    
    for record in data:
        date = datetime.fromisoformat(record['timestamp']).date()
        if date not in daily_data:
            daily_data[date] = {}
        
        # Parse raw_data if available
        if record['raw_data']:
            try:
                raw = json.loads(record['raw_data'])
                daily_data[date][record['source']] = {
                    'price': record['price'],
                    'raw': raw,
                    'timestamp': record['timestamp']
                }
            except:
                pass
    
    return daily_data

def generate_price_chart(daily_data):
    """Generate price trends chart with subplots"""
    fig, axes = plt.subplots(3, 2, figsize=(15, 12))
    fig.suptitle('Silver Market - Daily Price Trends (30 Days)', fontsize=16, fontweight='bold')
    
    dates = sorted(daily_data.keys())
    
    # XAU/USD (Gold Spot)
    gold_prices = []
    for date in dates:
        if 'GOLD' in daily_data[date]:
            gold_prices.append(daily_data[date]['GOLD']['price'])
        else:
            gold_prices.append(None)
    
    axes[0,0].plot(dates, gold_prices, 'o-', color='gold', linewidth=2, markersize=4)
    axes[0,0].set_title('XAU/USD Gold Spot')
    axes[0,0].set_ylabel('Price (USD/oz)')
    axes[0,0].grid(True, alpha=0.3)
    
    # XAG/USD (Silver Spot)
    silver_prices = []
    for date in dates:
        if 'SILVER' in daily_data[date]:
            silver_prices.append(daily_data[date]['SILVER']['price'])
        else:
            silver_prices.append(None)
    
    axes[0,1].plot(dates, silver_prices, 'o-', color='silver', linewidth=2, markersize=4)
    axes[0,1].set_title('XAG/USD Silver Spot')
    axes[0,1].set_ylabel('Price (USD/oz)')
    axes[0,1].grid(True, alpha=0.3)
    
    # COMEX Futures
    comex_prices = []
    for date in dates:
        if 'COMEX' in daily_data[date]:
            comex_prices.append(daily_data[date]['COMEX']['price'])
        else:
            comex_prices.append(None)
    
    axes[1,0].plot(dates, comex_prices, 'o-', color='blue', linewidth=2, markersize=4)
    axes[1,0].set_title('COMEX Silver Futures')
    axes[1,0].set_ylabel('Price (USD/oz)')
    axes[1,0].grid(True, alpha=0.3)
    
    # SHFE Ag Price
    shfe_prices = []
    for date in dates:
        if 'SHFE' in daily_data[date]:
            raw = daily_data[date]['SHFE']['raw']
            if raw and 'price_usd_oz' in raw:
                shfe_prices.append(raw['price_usd_oz'])
            else:
                shfe_prices.append(None)
        else:
            shfe_prices.append(None)
    
    axes[1,1].plot(dates, shfe_prices, 'o-', color='red', linewidth=2, markersize=4)
    axes[1,1].set_title('SHFE Ag Price (USD/oz)')
    axes[1,1].set_ylabel('Price (USD/oz)')
    axes[1,1].grid(True, alpha=0.3)
    
    # SLV ETF
    slv_prices = []
    for date in dates:
        if 'SLV' in daily_data[date]:
            slv_prices.append(daily_data[date]['SLV']['price'])
        else:
            slv_prices.append(None)
    
    axes[2,0].plot(dates, slv_prices, 'o-', color='purple', linewidth=2, markersize=4)
    axes[2,0].set_title('SLV ETF Price')
    axes[2,0].set_ylabel('Price (USD)')
    axes[2,0].grid(True, alpha=0.3)
    
    # GLD ETF
    gld_prices = []
    for date in dates:
        if 'GLD' in daily_data[date]:
            gld_prices.append(daily_data[date]['GLD']['price'])
        else:
            gld_prices.append(None)
    
    axes[2,1].plot(dates, gld_prices, 'o-', color='orange', linewidth=2, markersize=4)
    axes[2,1].set_title('GLD ETF Price')
    axes[2,1].set_ylabel('Price (USD)')
    axes[2,1].grid(True, alpha=0.3)
    
    # Format x-axis for all subplots
    for ax in axes.flat:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    chart_path = '/tmp/silver_prices_daily.png'
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    return chart_path

def generate_holdings_chart(daily_data):
    """Generate holdings trends chart with subplots"""
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('Silver Market - Daily Holdings Trends (30 Days)', fontsize=16, fontweight='bold')
    
    dates = sorted(daily_data.keys())
    
    # COMEX Registered
    comex_reg = []
    for date in dates:
        if 'COMEX_INV' in daily_data[date]:
            raw = daily_data[date]['COMEX_INV']['raw']
            if raw and 'registered' in raw:
                comex_reg.append(raw['registered'] / 1_000_000)  # Convert to millions
            else:
                comex_reg.append(None)
        else:
            comex_reg.append(None)
    
    axes[0,0].plot(dates, comex_reg, 'o-', color='blue', linewidth=2, markersize=4)
    axes[0,0].set_title('COMEX Registered Silver')
    axes[0,0].set_ylabel('Million oz')
    axes[0,0].grid(True, alpha=0.3)
    
    # COMEX Eligible
    comex_elig = []
    for date in dates:
        if 'COMEX_INV' in daily_data[date]:
            raw = daily_data[date]['COMEX_INV']['raw']
            if raw and 'eligible' in raw:
                comex_elig.append(raw['eligible'] / 1_000_000)  # Convert to millions
            else:
                comex_elig.append(None)
        else:
            comex_elig.append(None)
    
    axes[0,1].plot(dates, comex_elig, 'o-', color='green', linewidth=2, markersize=4)
    axes[0,1].set_title('COMEX Eligible Silver')
    axes[0,1].set_ylabel('Million oz')
    axes[0,1].grid(True, alpha=0.3)
    
    # SLV Trust Holdings
    slv_holdings = []
    for date in dates:
        if 'SLV_HOLDINGS' in daily_data[date]:
            raw = daily_data[date]['SLV_HOLDINGS']['raw']
            if raw and 'holdings_oz' in raw:
                slv_holdings.append(raw['holdings_oz'] / 1_000_000)  # Convert to millions
            else:
                slv_holdings.append(None)
        else:
            slv_holdings.append(None)
    
    axes[1,0].plot(dates, slv_holdings, 'o-', color='purple', linewidth=2, markersize=4)
    axes[1,0].set_title('SLV Trust Holdings')
    axes[1,0].set_ylabel('Million oz')
    axes[1,0].grid(True, alpha=0.3)
    
    # GLD Trust Holdings
    gld_holdings = []
    for date in dates:
        if 'GLD_HOLDINGS' in daily_data[date]:
            raw = daily_data[date]['GLD_HOLDINGS']['raw']
            if raw and 'holdings_oz' in raw:
                gld_holdings.append(raw['holdings_oz'] / 1_000_000)  # Convert to millions
            else:
                gld_holdings.append(None)
        else:
            gld_holdings.append(None)
    
    axes[1,1].plot(dates, gld_holdings, 'o-', color='orange', linewidth=2, markersize=4)
    axes[1,1].set_title('GLD Trust Holdings')
    axes[1,1].set_ylabel('Million oz')
    axes[1,1].grid(True, alpha=0.3)
    
    # Format x-axis for all subplots
    for ax in axes.flat:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    chart_path = '/tmp/silver_holdings_daily.png'
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    return chart_path

def send_discord_images(price_chart, holdings_chart):
    if not WEBHOOK_URL:
        print("No webhook URL configured")
        return
    
    # Send price chart
    with open(price_chart, 'rb') as f:
        files = {'file': ('silver_prices_daily.png', f, 'image/png')}
        payload = {
            'content': f"**📊 Daily Silver Report** - {datetime.utcnow().strftime('%Y-%m-%d')}\n\n**Price Trends (30 Days)**"
        }
        requests.post(WEBHOOK_URL, data=payload, files=files)
    
    # Send holdings chart
    with open(holdings_chart, 'rb') as f:
        files = {'file': ('silver_holdings_daily.png', f, 'image/png')}
        payload = {
            'content': f"**Holdings Trends (30 Days)**"
        }
        requests.post(WEBHOOK_URL, data=payload, files=files)

def main():
    print("Generating daily silver report...")
    
    # Get 30 days of data
    daily_data = get_daily_data(days=30)
    
    if not daily_data:
        print("No data available")
        return
    
    print(f"Found data for {len(daily_data)} days")
    
    # Generate charts
    price_chart = generate_price_chart(daily_data)
    holdings_chart = generate_holdings_chart(daily_data)
    
    # Send to Discord
    send_discord_images(price_chart, holdings_chart)
    
    print("✅ Daily report charts sent to Discord")

if __name__ == '__main__':
    main()
