import json
import sqlite3
import time

import requests
from db_errors import (
    RequestTimeoutError, RequestFailedError,
    UnauthorizedError, ForbiddenError,
    NotFoundError, ServerError
    )

FAIL_API = "https://store.steampowered.com/api/appdetails/?appids=360032"

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
    # Get App List from Steam and Save It
    if applist_fetched is False:
        try:
            applist = fetch_applist(APPLIST_API, APPLIST_FILE)
        except RequestTimeoutError:
            print("!!! ERROR !!!")
            print("Cannot fetch applist because request timed out. Will wait 5 minutes.")
            time.sleep(60 * 5)
            applist = fetch_applist(APPLIST_API, APPLIST_FILE)

        # Save to File
        write_to_json(applist, APPLIST_FILE)

    # Open App List File
    with open(APPLIST_FILE, "r") as f:
        applist = json.load(f)["applist"]

    # Get App details For each App
    limited_applist = applist[:10]
    for app in limited_applist:
        appid = app["appid"]
        # Fetch from SteamSpy
        resp_from_steamspy = fetch(STEAMSPY_APP_DETAILS_API_BASE + str(app["appid"]))

        # Check minimum owner count
        min_owner_count = get_min_owner_count(resp_from_steamspy)

        if min_owner_count > 1_000_000:
            continue
        else:
            app_details_from_steamspy = {
                "owners": resp_from_steamspy["owners"],
                "price": resp_from_steamspy["price"],
                "positive_reviews": resp_from_steamspy["positive"],
                "negative_reviews": resp_from_steamspy["negative"],
                "tags": resp_from_steamspy["tags"]
            }
            app.update(app_details_from_steamspy)

            # Save App to DB
            with open("./app_details.json") as f:
                app_details = json.load(f)
                app_details["apps"].append(app)

            write_to_json(app_details, "./app_details.json", indent=2)

            # Get App from db
            with open("./app_details.json") as f:
                apps = json.load(f)["apps"]

            app = [i for i in apps if i["appid"] == appid][0]

            print(app)
            # TODO get details from Steam






def fetch_applist(api: str):
    """Steam's return format: {'applist': [{appid: int, name: str}]}"""
    # TODO record fetch date
    print("fetch_applist()")

    response_json = fetch(api)

    applist = {"applist": []}
    # Save each app that has a name
    for app in response_json["applist"]:
        if app["name"]:
            applist["applist"].append(
                {
                    "appid": app["appid"],
                    "name": app["name"]
                }
            )

    print("TODO: Record that applist is fecthed! So it doesn't always fecthes from steam")
    return applist


def fetch(api: str) -> dict:
    """Makes a request to an API and returns JSON. If fails will raise Exeception."""
    response = request_from(api)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 500:   # server error
        raise ServerError(api)
    elif response.status_code == 401:
        raise UnauthorizedError(api)
    elif response.status_code == 403:
        raise ForbiddenError(api)
    elif response.status_code == 404:
        raise NotFoundError(api)
    else:
        raise RequestFailedError(response.status_code)


def request_from(api: str, timeout=1):
    """Tries 3 times before raising TimeoutError"""
    attempt = 1
    while attempt <= 3:
        try:
            response = requests.get(api, timeout=timeout)
            return response
        except requests.Timeout:
            print("Request Timed Out:", api)
            print("Attempt:", attempt)
            time.sleep(10)
            attempt += 1

    raise RequestTimeoutError(api)


def get_min_owner_count(app_details: dict) -> int:
    """Returns minimum owner count"""
    # owners example: "10,000 .. 20,000"
    min_owners_raw = app_details["owners"].split("..")[0].strip()
    min_owners_str = ""
    for i in min_owners_raw.split(","):
        min_owners_str += i

    return int(min_owners_str)


def write_to_json(data: any, file_path: str, indent=0):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=indent)


def clear_file_content(file_path: str):
    with open(file_path, "w") as f:
        f.write("")


def get_app_count():
    with open(APPLIST_FILE, "r") as f:
        applist = json.load(f)["applist"]

    return len(applist)


if __name__ == "__main__":
    main()
