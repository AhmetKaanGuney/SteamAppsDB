import json
import sqlite3
import time

import requests
from errors import (
    Error,
    RequestTimeoutError, RequestFailedError,
    UnauthorizedError, ForbiddenError,
    NotFoundError, ServerError,
    SteamResponseError
    )
from update_logger import UpdateLogger

# Init Logger
ulogger = UpdateLogger("./update_log.json")

FAIL_API = "https://store.steampowered.com/api/appdetails/?appids=360032"


# Time to wait in between request in ms
STEAM_WAIT_DURATION = 1
STEAMSPY_WAIT_DURATION = 1
STEAM_REQUEST_LIMIT = 100_000

# File paths
APPLIST_FILE = "./applist.json"
APPLIST_FILTERED_FILE = "./applist_filtered.json"

# API's
APPLIST_API = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
# Just append appid to these strings to make a request
STEAM_APP_DETAILS_API_BASE = "https://store.steampowered.com/api/appdetails/?appids="
STEAMSPY_APP_DETAILS_API_BASE = "https://steamspy.com/api.php?request=appdetails&appid="


# TODO record latest request date

def main():
    applist_fetched = True

    # Get App List from Steam and Save It
    if not applist_fetched:
        applist = fetch_applist(APPLIST_API, APPLIST_FILE)
        ulogger.log["steam_request_count"] += 1

        # Save to File
        write_to_json(applist, APPLIST_FILE)

    # Open App List File
    with open(APPLIST_FILE, "r") as f:
        applist = json.load(f)["applist"]

    # Get App details For each App
    limited_applist = applist[:10]

    # DB
    apps_data = {}

    reached_steam_request_limit = False

    for app in limited_applist:
        appid = app["appid"]
        applist_index = ulogger.log["applist_index"]

        # TODO POTENTIAL BUG HERE
        # Skip to the lastest app that was last updated
        if  applist_index != -1 and appid != applist_index:
            continue

        # API's
        steamspy_api = STEAMSPY_APP_DETAILS_API_BASE + str(appid)
        steam_api = STEAM_APP_DETAILS_API_BASE + str(appid)

        # Remove appid from field of the app becuse it'll be used as an index in the DB
        app.pop("appid")

        # FETCH FORM STEAMSPY
        steamspy_data = fetch(steamspy_api)

        # Check minimum owner count to eliminate games over a million owners
        min_owner_count = get_min_owner_count(steamspy_data)

        if min_owner_count > 1_000_000:
            continue

        # update app info
        steamspy_keys = ["owners", "price", "positive", "negative", "tags"]
        app_details_from_steamspy = {k:v for k, v in steamspy_data.items() if k in steamspy_keys}
        app.update(app_details_from_steamspy)

        # Check for request limit
        if ulogger.log["steam_request_count"] > STEAM_REQUEST_LIMIT:
            reached_steam_request_limit = True

        if reached_steam_request_limit:
            print("Request limit reached!")
            break

        # FETCH FROM STEAM
        # Steam Response Example
        # {"000000": {"success": true, "data": {...}}}

        steam_response = fetch(steam_api)[str(appid)]
        ulogger.log["steam_request_count"] += 1

        if steam_response["success"]:
            steam_data = steam_response["data"]
            # Check if app is a game
            if steam_data["type"] != "game":
                print("App is not a game. AppID: ", appid)
                continue
            else:
                steam_keys = ["release_date", "developers", "publishers", "header_image",
                        "screenshots", "categories", "genres", "short_description",
                        "about_the_game", "detailed_description", "platforms",
                        "supported_languages", "website"]
                app_details_from_steam = {k:v for k, v in steam_data.items() if k in steam_keys}

                # Update the app oinfo
                app.update(app_details_from_steam)
                # Record to apps_data
                apps_data[appid] = app
        else:
            print("ERROR! Steam responded with 'success: False'. API: ", steam_api)
            ulogger.log["rejected_apps"].append(appid)
            continue

    # If the last app in the app list is updated without breaking the
    # steam request limit reset applist index
    if reached_steam_request_limit:
        ulogger.log["applist_index"] = appid
        ulogger.log["steam_request_count"] = 0
    else:
        ulogger.log["applist_index"] = -1

    write_to_json(apps_data, "./app_details.json", indent=2)


def fetch(api: str) -> dict:
    """Makes a request to an API and returns JSON. If fails will raise Exeception."""
    response = request_from(api)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 500:   # server error
        raise ServerError(api, ulogger.log)
    elif response.status_code == 401:
        raise UnauthorizedError(api, ulogger.log)
    elif response.status_code == 403:
        raise ForbiddenError(api, ulogger.log)
    elif response.status_code == 404:
        raise NotFoundError(api, ulogger.log)
    else:
        raise RequestFailedError(response.status_code, ulogger.log)


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

    raise RequestTimeoutError(api, ulogger.log)


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
    try:
        main()
    except Error as e:
        raise e
    finally:
        ulogger.save()
