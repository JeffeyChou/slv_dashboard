import yfinance as yf
import requests
import pandas as pd
import io
from datetime import datetime

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def test_futures():
    print("--- Testing Futures Data ---")
    ticker = 'SIH26.CMX'
    try:
        future = yf.Ticker(ticker)
        info = future.info
        print(f"Success with {ticker}")
        print(f"Price: {info.get('regularMarketPrice')}")
        print(f"Open Interest: {info.get('openInterest')}")
        print(f"Volume: {info.get('volume')}")
    except Exception as e:
        print(f"Error with {ticker}: {e}")

def test_slv():
    print("\n--- Testing SLV Data ---")
    url = "https://www.ishares.com/us/products/239855/ishares-silver-trust-fund/1467271812596.ajax?fileType=csv&fileName=SLV_holdings&dataType=fund"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            print("Successfully fetched SLV CSV")
            content = response.content.decode('utf-8')
            lines = content.split('\n')
            print("First 10 lines:")
            for i in range(min(10, len(lines))):
                print(lines[i])
        else:
            print(f"Failed to fetch SLV CSV. Status: {response.status_code}")
    except Exception as e:
        print(f"Error fetching SLV: {e}")

def test_cme():
    print("\n--- Testing CME Stocks Data ---")
    url = "https://www.cmegroup.com/delivery_reports/Silver_Stocks.xls"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            print("Successfully fetched CME Excel")
            # We won't parse it yet, just check if we got it
            print(f"Content length: {len(response.content)}")
        else:
            print(f"Failed to fetch CME Excel. Status: {response.status_code}")
    except Exception as e:
        print(f"Error fetching CME: {e}")

def test_lbma():
    print("\n--- Testing LBMA Data ---")
    url = "https://www.lbma.org.uk/prices-and-data/london-vault-holdings-data"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            print("Successfully fetched LBMA Page")
        else:
            print(f"Failed to fetch LBMA Page. Status: {response.status_code}")
    except Exception as e:
        print(f"Error fetching LBMA: {e}")

if __name__ == "__main__":
    test_futures()
    test_slv()
    test_cme()
    test_lbma()
