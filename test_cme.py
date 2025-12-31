from curl_cffi import requests

def test_cme_impersonate():
    print("\n--- Testing CME Stocks Data with curl_cffi ---")
    url = "https://www.cmegroup.com/delivery_reports/Silver_Stocks.xls"
    try:
        response = requests.get(url, impersonate="chrome110")
        if response.status_code == 200:
            print("Successfully fetched CME Excel")
            print(f"Content length: {len(response.content)}")
        else:
            print(f"Failed to fetch CME Excel. Status: {response.status_code}")
    except Exception as e:
        print(f"Error fetching CME: {e}")

if __name__ == "__main__":
    test_cme_impersonate()
