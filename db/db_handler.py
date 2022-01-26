import json
import sqlite3
import time

import requests


# Get app list from Steam
# For each app:
#     get app details from SteamSpy
#     If app has more than 2 million owners:
#         continue
#     Else:
#         get more app details from Steam
#         record to db
applist_fetched = True

# Time to wait in between request in ms 
STEAM_WAIT_DURATION = 1
STEAMSPY_WAIT_DURATION = 1

APPLIST_FILE = "./applist.json"
APPLIST_FILTERED_FILE = "./applist_filtered.json"

APPLIST_API = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
# Just append appid to these strings to make a request
STEAM_APP_DETAILS_API_BASE = "https://store.steampowered.com/api/appdetails/?appids="
STEAMSPY_APP_DETAILS_API_BASE = "https://steamspy.com/api.php?request=appdetails&appid="

def main():
    # Get App List from Steam
    if applist_fetched is False:
        fetch_applist(APPLIST_API, APPLIST_FILE, applist_fetched)
        # TODO write data (make a function)
    # with open(APPLIST_FILE, "r") as f:
    #     applist = json.load(f)["applist"]
    
    # clear_file_content(APPLIST_FILTERED_FILE)
    # app_details = get_app_details_from_steamspy(applist[:10], STEAMSPY_APP_DETAILS_API_BASE, STEAMSPY_WAIT_DURATION)

    # # Append to filtered list
    # with open(APPLIST_FILTERED_FILE, "a") as f:
    #     json.dump(app_details, f, indent=2)



def fetch_applist(api, applist_file, applist_fetched: bool):
    if applist_fetched is False:
        response = requests.get(api)

        if response.status_code == 200:
            applist = response.json()["applist"]["apps"]
            data = {"applist": []}
            # Save each app that has a name
            for app in applist:
                if not app["name"]:
                    continue
                else:
                    data["applist"].append(
                        {
                            "appid": app["appid"],
                            "name": app["name"]
                        }
                    )
            with open(applist_file, "w") as f:
                json.dump(data, f)
        else:
            print("RequestFailed: ", response.status_code)
        applist_fetched = True


def get_app_details_from_steamspy(applist: [], steamspy_api_base: str, wait_duration: int):
    process = ""
    data = {"applist": []}

    print("Getting app details:")

    for app in applist:
        response = requests.get(steamspy_api_base + str(app["appid"]))
        if response.status_code == 200:
            response_data = response.json()
            data["applist"].append(
                {
                "appid": app["appid"],
                "owners": response_data["owners"],
                "price": response_data["price"],
                "positive_reviews": response_data["positive"],
                "negative_reviews": response_data["negative"],
                "tags": response_data["tags"]
                }
            )
        else:
            print("Request Failed: ", response.status_code)
            print("App ID: ", app["appid"])
            process += "#"
            continue
        time.sleep(wait_duration)
        process += "#"
        print(process, end="\r")
    
    print("Finished!")
    return data

     
def clear_file_content(file_path: str):
    with open(file_path, "w") as f:
        f.write("")


def get_app_count():
    with open(APPLIST_FILE, "r") as f:
        applist = json.load(f)["applist"]
    
    return len(applist)


if __name__ == "__main__":
    main()
