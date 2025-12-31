import requests
from bs4 import BeautifulSoup

def scrape_slv_page():
    url = "https://www.ishares.com/us/products/239855/ishares-silver-trust-fund"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # Look for "Tonnes in Trust" or similar
            # It might be in a specific div or table
            text = soup.get_text()
            if "Tonnes in Trust" in text:
                print("Found 'Tonnes in Trust'")
                # Try to find the value near it
                # This is a bit rough, but let's see context
                index = text.find("Tonnes in Trust")
                print(text[index:index+200])
            else:
                print("Did not find 'Tonnes in Trust'")
        else:
            print(f"Failed to fetch page: {response.status_code}")
    except Exception as e:
        print(e)

if __name__ == "__main__":
    scrape_slv_page()
