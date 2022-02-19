import requests
import json

filters = {
    "tags": [2],
    "genres": [2],
    "categories": []
}
order = {
    "price": "ASC",
    "release_date": "DESC"
}
data = {"filters": filters, "order": order, "index": 0}
response = requests.get("http://127.0.0.1:5000/GetAppList", json=json.dumps(data))
print(response.url)
print(json.loads(response.text))