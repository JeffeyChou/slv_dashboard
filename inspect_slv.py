import requests

def inspect_slv():
    url = "https://www.ishares.com/us/products/239855/ishares-silver-trust-fund/1467271812596.ajax?fileType=csv&fileName=SLV_holdings&dataType=fund"
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        content = response.content.decode('utf-8')
        lines = content.split('\n')
        for i in range(min(20, len(lines))):
            print(lines[i])
    except Exception as e:
        print(e)

if __name__ == "__main__":
    inspect_slv()
