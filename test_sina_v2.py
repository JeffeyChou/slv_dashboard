import requests

def test_sina_headers():
    print("\n--- Testing Sina Finance with Headers ---")
    headers = {
        'Referer': 'https://finance.sina.com.cn/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    codes = ['ag0', 'NF_AG0']
    
    for code in codes:
        url = f"http://hq.sinajs.cn/list={code}"
        try:
            response = requests.get(url, headers=headers)
            print(f"Code: {code}")
            # Sina returns GBK encoding usually
            print(response.content.decode('gbk', errors='ignore'))
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_sina_headers()
