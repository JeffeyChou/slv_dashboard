import yfinance as yf
import requests
import pandas as pd
from datetime import datetime
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def test_shfe():
    print("\n--- Testing SHFE Data ---")
    # SHFE Delayed Quotes URL pattern from PDF
    # https://www.shfe.com.cn/eng/reports/delayedMarketData/DelayedQuotes/?query_params=delaymarket_f&query_product_code=ag_f
    # But that's a page, we probably need the JSON endpoint if it exists, or scrape the page.
    # Let's try to hit the page first.
    url = "https://www.shfe.com.cn/eng/reports/delayedMarketData/DelayedQuotes/"
    # Often these sites load data via AJAX.
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            print("Fetched SHFE page")
            # In a real browser this might load data. 
            # Let's see if we can find a direct JSON endpoint or if we need to parse HTML.
            # Searching for 'ag' or 'Silver'
            if "Silver" in response.text:
                print("Found 'Silver' in text")
            else:
                print("Did not find 'Silver' in initial text (might be dynamic)")
    except Exception as e:
        print(f"SHFE Error: {e}")

def test_fred_macro():
    print("\n--- Testing FRED Macro Data ---")
    # We don't have an API key, so we'll try to scrape the series page for the latest value.
    # Series: DTWEXBGS (USD Index), DFII10 (Real Yield), DEXCHUS (USD/CNY)
    series_ids = ['DTWEXBGS', 'DFII10', 'DEXCHUS']
    
    for series_id in series_ids:
        url = f"https://fred.stlouisfed.org/series/{series_id}"
        try:
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                # The value is usually in a span with class "series-meta-observation-value"
                # <span class="series-meta-observation-value">102.45</span>
                match = re.search(r'class="series-meta-observation-value">([\d\.]+)<', response.text)
                if match:
                    print(f"{series_id}: {match.group(1)}")
                else:
                    print(f"{series_id}: Could not parse value")
            else:
                print(f"{series_id}: Failed to fetch page")
        except Exception as e:
            print(f"{series_id} Error: {e}")

def test_options():
    print("\n--- Testing SLV Options ---")
    try:
        slv = yf.Ticker("SLV")
        # Get nearest expiration
        expirations = slv.options
        if expirations:
            expiry = expirations[0]
            print(f"Expiration: {expiry}")
            opts = slv.option_chain(expiry)
            calls = opts.calls
            puts = opts.puts
            
            # Calculate Put/Call Ratio (Volume based)
            call_vol = calls['volume'].sum()
            put_vol = puts['volume'].sum()
            print(f"Call Vol: {call_vol}, Put Vol: {put_vol}")
            if call_vol > 0:
                print(f"P/C Ratio: {put_vol/call_vol:.2f}")
        else:
            print("No options found")
    except Exception as e:
        print(f"Options Error: {e}")

def test_cot():
    print("\n--- Testing COT Data ---")
    # CFTC data is usually in a zip file.
    # https://www.cftc.gov/dea/newcot/deafut.txt (Futures only)
    # or https://www.cftc.gov/dea/newcot/deacomb.txt (Futures + Options)
    # Format is CSV-like but fixed width or comma separated? It's usually CSV.
    # We need to look for "SILVER"
    url = "https://www.cftc.gov/dea/newcot/deafut.txt"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            lines = response.text.split('\n')
            for line in lines:
                if "SILVER" in line and "COMEX" in line:
                    # Found it. The columns are standard.
                    # We'll just print the line for now to verify.
                    print("Found Silver COT line:")
                    print(line[:100] + "...")
                    break
        else:
            print(f"Failed to fetch COT: {response.status_code}")
    except Exception as e:
        print(f"COT Error: {e}")

if __name__ == "__main__":
    test_shfe()
    test_fred_macro()
    test_options()
    test_cot()
