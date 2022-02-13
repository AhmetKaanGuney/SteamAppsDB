import requests
import json
params = {"tags": [1, 2], "genres": [1], "categories": [1], "order_by": [{"price": "DESC"}]}
response = requests.get("http://127.0.0.1:5000/GetAppList", params=params)
print(response.url)
print(response.text)