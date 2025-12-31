import requests

def test_sina():
    print("\n--- Testing Sina Finance ---")
    # Try different codes for Silver
    # ag0: Dominant contract
    # ag2602: Specific contract
    codes = ['ag0', 'ag2602', 'ag2606', 'NF_AG0'] 
    # NF_AG0 might be the code for internal futures
    
    for code in codes:
        url = f"http://hq.sinajs.cn/list={code}"
        try:
            response = requests.get(url)
            print(f"Code: {code}")
            print(response.text)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_sina()
