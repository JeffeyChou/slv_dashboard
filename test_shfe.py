import requests
from datetime import datetime

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def test_shfe_params():
    print("\n--- Testing SHFE Params ---")
    # Try to get today's date or recent date
    date_str = datetime.now().strftime('%Y%m%d')
    url = f"https://www.shfe.com.cn/eng/reports/delayedMarketData/DelayedQuotes/?query_date={date_str}&query_options=1&query_params=delaymarket_f&query_product_code=ag_f"
    print(f"URL: {url}")
    try:
        response = requests.get(url, headers=HEADERS)
        print(f"Status: {response.status_code}")
        print("First 500 chars:")
        print(response.text[:500])
        
        # Check if it looks like JSON
        try:
            data = response.json()
            print("It is JSON!")
            print(data)
        except:
            print("Not JSON")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_shfe_params()
