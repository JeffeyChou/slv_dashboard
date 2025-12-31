import requests
from bs4 import BeautifulSoup

def scrape_lbma_page():
    url = "https://www.lbma.org.uk/prices-and-data/london-vault-holdings-data"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # Look for "Silver" and "Tonnes"
            text = soup.get_text()
            if "Silver" in text:
                print("Found 'Silver'")
                # Try to find recent data. It's likely in a table.
                # Let's look for "November" or "October" since we saw those in research
                if "November" in text:
                    print("Found 'November'")
                    idx = text.find("November")
                    print(text[idx:idx+500])
            else:
                print("Did not find 'Silver'")
    except Exception as e:
        print(e)

if __name__ == "__main__":
    scrape_lbma_page()
