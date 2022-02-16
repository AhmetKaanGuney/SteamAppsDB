import requests
import json

SERVER_IP = "127.0.0.1"
PORT = "5000"

APPLIST = f"http://{SERVER_IP}:{PORT}/GetAppList"
APP_DETAILS = f"http://{SERVER_IP}:{PORT}/GetAppDetails/" + "1678630"
NON_GAME_APPS = f"http://{SERVER_IP}:{PORT}/GetNonGameApps"
FAILED_REQUESTS = f"http://{SERVER_IP}:{PORT}/GetFailedRequests"

query = {
    "filters": None,
    "order": None,
    "index": 0
}
try:
    print("APPLIST: ")
    r = requests.get(APPLIST, json=query)
    print(r.json())
    print("------------------------------------------------------------")

    print("APP DETAILS: ")
    r = requests.get(APP_DETAILS)
    for k, v in r.json().items():
        print(k, " : ", type(v))
    print("------------------------------------------------------------")

    print("NON GAME APPS: ")
    r = requests.get(NON_GAME_APPS)
    print(r.json())
    print("------------------------------------------------------------")

    print("FAILED REQUESTS: ")
    r = requests.get(FAILED_REQUESTS)
    print(r.json())
    print("------------------------------------------------------------")
    print("ATTACKING: ")
    for i in range(1_000_000):
        r = requests.get(FAILED_REQUESTS)
        print(f"Request Count: {i:,}", end="\r")
except json.JSONDecodeError as e:
    print("Error: ")
    print(r.text)