import requests
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def debug_cot():
    print("\n--- Debugging COT ---")
    url = "https://www.cftc.gov/dea/newcot/deafut.txt"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            print("First 500 chars:")
            print(response.text[:500])
            # Search case insensitive
            if "SILVER" in response.text:
                print("Found SILVER (case sensitive)")
            elif "Silver" in response.text:
                print("Found Silver (Title case)")
            elif "silver" in response.text.lower():
                print("Found silver (lower case)")
            else:
                print("SILVER not found in any case")
    except Exception as e:
        print(f"COT Error: {e}")

def debug_shfe():
    print("\n--- Debugging SHFE ---")
    url = "https://www.shfe.com.cn/eng/reports/delayedMarketData/DelayedQuotes/"
    try:
        response = requests.get(url, headers=HEADERS)
        # We need to find the price for Silver (ag)
        # It's likely in a table row.
        # Let's print a chunk around "Silver"
        text = response.text
        idx = text.find("Silver")
        if idx != -1:
            print("Context around Silver:")
            print(text[idx:idx+500])
        else:
            print("Silver not found")
    except Exception as e:
        print(f"SHFE Error: {e}")

if __name__ == "__main__":
    debug_cot()
    debug_shfe()
