import requests

def inspect_lbma():
    url = "https://www.lbma.org.uk/prices-and-data/london-vault-holdings-data"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        print(response.text[:2000]) 
    except Exception as e:
        print(e)

if __name__ == "__main__":
    inspect_lbma()
