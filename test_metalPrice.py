import requests
from requests.structures import CaseInsensitiveDict
    
url = "https://api.metals.dev/v1/latest?api_key=QJXK5KJ9UDMTHQI3MXUY225I3MXUY&currency=USD&unit=toz"
headers = CaseInsensitiveDict()
headers["Accept"] = "application/json"

resp = requests.get(url, headers=headers)
print(resp.json())