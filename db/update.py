import os
import time
import math
import datetime
import traceback
import json
import sqlite3
import logging
import smtplib, ssl

import requests
from dotenv import dotenv_values

from errors import (
    Error, RequestTimeoutError, RequestFailedError,
    UnauthorizedError, ForbiddenError, NotFoundError,
    ServerError, SteamResponseError
)
from update_logger import UpdateLogger
from appdata import AppData

# Dirs
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)

# Config
config = dotenv_values(os.path.join(parent_dir, ".env"))

# Init Loggers
logging.basicConfig(level=logging.INFO)

u_logger = UpdateLogger(os.path.join(current_dir, "update_log.json"))
update_log = u_logger.log

# Test
FAIL_API = "https://store.steampowered.com/api/appdetails/?appids=360032"

# Max owner limit, if an app's owner count breaks the limit
# that app will be ignored
# MAX_OWNERS = 1_000_000
MAX_OWNERS = 1_000_000

# Time to wait in between request in ms
STEAM_WAIT_DURATION = 1
STEAMSPY_WAIT_DURATION = 1
STEAM_REQUEST_LIMIT = 100_000

# File paths
APPLIST_FILE = os.path.join(current_dir, "applist.json")
APPLIST_FILTERED_FILE = os.path.join(current_dir, "applist_filtered.json")

# API's
# Append appid to app details API to get app details
APPLIST_API = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
STEAM_APP_DETAILS_API_BASE = "https://store.steampowered.com/api/appdetails/?appids="
STEAMSPY_APP_DETAILS_API_BASE = "https://steamspy.com/api.php?request=appdetails&appid="


# TODO email weekly report and errors

def main():
    logging.info("===             DB UPDATE            ===")
    logging.info(f"=== Date: {datetime.datetime.utcnow()} ===")

    applist_fetched = True

    # ========================= #
    #  Get App List from Steam  #
    # ========================= #
    if not applist_fetched:
        logging.debug(f"Fetching applist from: {APPLIST_API}")

        applist = fetch_applist(APPLIST_API, APPLIST_FILE)
        update_log["steam_request_count"] += 1

        # Save to File
        write_to_json(applist, APPLIST_FILE)

    with open(APPLIST_FILE, "r") as f:
        applist = json.load(f)["applist"]

    limited_applist = applist[:30]
    applist_index = update_log["applist_index"]

    logging.info(f"Length of Limited Applist: {len(limited_applist):,}")
    logging.debug(f"Applist Index: {applist_index}")

    update_log["applist_length"] = len(applist)

    apps_data: list[AppData] = []

    # =============================== #
    #  Get App Details for each App   #
    # =============================== #
    logging.debug("Iterating over LIMITED APPLIST...")
    logging.debug(f"Steam Request Count: {update_log['steam_request_count']}")


    for i, app in enumerate(limited_applist[applist_index:]):
        app_id = app["appid"]
        app_data = AppData()
        app_data.update({"name": app["name"], "app_id": app["appid"]})

        # API's
        steamspy_api = STEAMSPY_APP_DETAILS_API_BASE + str(app_id)
        steam_api = STEAM_APP_DETAILS_API_BASE + str(app_id)

        # ====================== #
        #  FETCH FROM STEAMSPY   #
        # ====================== #
        steamspy_data = fetch(steamspy_api)

        # Check minimum owner count to eliminate games over a million owners
        min_owner_count = get_min_owner_count(steamspy_data)

        if min_owner_count > MAX_OWNERS:
            logging.debug(
                f"App: '{app_id}' has {min_owner_count:,} owners. "
                f"Which is over {MAX_OWNERS=:,}. Skipping..."
                )
            continue

        # Update app info
        app_details_from_steamspy = map_steamspy_data(steamspy_data)
        app_data.update(app_details_from_steamspy)

        # =================== #
        #  FETCH FROM STEAM   #
        # =================== #
        # Check for request limit
        if update_log["steam_request_count"] >= STEAM_REQUEST_LIMIT:
            update_log["steam_request_limit_reached"] = True
            logging.info(
                f"Request limit reached! "
                f"Request count: {update_log['steam_request_count']} | "
                f"Request Limit: {STEAM_REQUEST_LIMIT}"
                )
            break

        # Response Example : {"000000": {"success": true, "data": {...}}}
        steam_response = fetch(steam_api)[str(app_id)]

        update_log["last_request_to_steam"] = str(datetime.datetime.utcnow())
        update_log["steam_request_count"] += 1

        if steam_response["success"]:
            steam_data = steam_response["data"]
            # Check if app is a game
            if steam_data["type"] != "game":
                logging.debug(f"App '{app_id}' is not a game. Skipping...")
                update_log["non_game_apps"] += 1
                continue
            else:
                app_details_from_steam = map_steam_data(steam_data)

                # Update the app info
                app_data.update(app_details_from_steam)
                update_log["updated_apps"] += 1

                # Record to apps_data
                apps_data.append(app_data.serialize())

        else:
            logging.debug(f"Steam responded with {steam_response}. AppID: {app_id}")
            update_log["rejected_apps"].append(app_id)
            continue

    if update_log["steam_request_limit_reached"]:
        update_log["applist_index"] += i
        update_log["steam_request_count"] = 0
        update_log["steam_request_limit_reached"] = False
    else:
        # If the last item in the app list is updated, reset the log
        update_log["reset_log"] = True

    write_to_json(apps_data, "./app_details.json", indent=2)


def fetch(api: str) -> dict:
    """Makes a request to an API and returns JSON. If fails will raise Exeception."""
    response = request_from(api)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 500:   # server error
        raise ServerError(api, update_log)
    elif response.status_code == 401:
        raise UnauthorizedError(api, update_log)
    elif response.status_code == 403:
        raise ForbiddenError(api, update_log)
    elif response.status_code == 404:
        raise NotFoundError(api, update_log)
    else:
        raise RequestFailedError(response.status_code, update_log)


def fetch_applist(api: str):
    """Steam's return format: {'applist': [{appid: int, name: str}]}"""

    update_log["last_request_to_steam"] = str(datetime.datetime.utcnow())
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

    raise RequestTimeoutError(api, update_log)


def map_steam_data(steam_data: dict) -> dict:
    """Parses Steam data and returns it in a better format
    returns: {
        'developers': list[str],
        'publishers': list[str],
        'release_date': str,
        'coming_soon': bool,
        'genres': list[dict],
        'categories': list[dict],
        'about_the_game': str,
        'short_description': str,
        'detailed_description': str,
        'header_image': str,
        'screenshots': list[dict],
        'website': str,
        'languages': str,
        'windows': bool,
        'mac': bool,
        'linux': bool
    }"""
    fields = [
        "developers", "publishers", "categories", "genres",
        "about_the_game", "short_description", "detailed_description",
        "header_image", "screenshots", "website"
        ]
    app_details = {k:v for k, v in steam_data.items() if k in fields}

    # Serialize date and languages for DB
    try:
        release_date = format_date(steam_data["release_date"]["date"])
    except (IndexError, KeyError):
        release_date = steam_data["release_date"]["date"]

    try:
        languages = steam_data["supported_languages"]
    except KeyError:
        languages = None

    # TODO parse supported languages
    coming_soon = steam_data["release_date"]["coming_soon"]
    platforms = steam_data["platforms"]

    app_details.update({
        "release_date": release_date,
        "coming_soon": coming_soon,
        "languages": languages,
        "windows": platforms["windows"],
        "mac": platforms["mac"],
        "linux": platforms["linux"]
    })
    return app_details


def map_steamspy_data(steamspy_data: dict) -> dict:
    """Parses SteamSpy data and returns it in a better format
    returns: {
        'price': [int, None],
        'owner_count: int',
        'positive_reviews: int',
        'negative_reviews': int
        'tags': list,
    }"""
    app_details = {
        "price": steamspy_data["price"],
        "owner_count": get_average(steamspy_data["owners"]),
        "positive_reviews": steamspy_data["positive"],
        "negative_reviews": steamspy_data["negative"],
        "tags": steamspy_data["tags"]
    }

    return app_details


def format_date(date: str) -> str:
    """Returns formatted date: YYYY-MM-DD"""
    date = date.replace(",", "")
    date = date.split(" ")
    months = {
    "Jan": "01",
    "Feb": "02",
    "Mar": "03",
    "Apr": "04",
    "May": "05",
    "Jun": "06",
    "Jul": "07",
    "Aug": "08",
    "Sep": "09",
    "Oct": "10",
    "Nov": "11",
    "Dec": "12",
    }
    formatted_date = date[2] + "-" + months[date[1]] + "-" + date[0]
    return formatted_date


def get_average(owner_count: str):
    owner_count_list = owner_count.split("..")
    owner_count_list = [i.strip() for i in owner_count_list]
    min_owners_list = owner_count_list[0]
    max_owners_list = owner_count_list[1]
    min_owners = ""
    max_owners = ""
    for i in min_owners_list.split(","):
        min_owners += i

    for i in max_owners_list.split(","):
        max_owners += i

    average = (int(min_owners) + int(max_owners)) / 2
    return math.floor(average)


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


def email(msg):
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(
        config["SMTP_SERVER"], config["PORT"], context=context) as server:
        server.login(config["SENDER_EMAIL"], config["PASSWORD"])
        server.sendmail(config["SENDER_EMAIL"], config["RECEIVER_EMAIL"], msg)


if __name__ == "__main__":
    try:
        main()
        msg = f"""\
Subject: Update Successful

Updated Apps: {update_log["updated_apps"]:,} / {update_log["applist_length"]:,}
Rejected Apps: {len(update_log["rejected_apps"])}
Non-Game Apps: {update_log["non_game_apps"]}
Steam Request Count: {update_log["steam_request_count"]}
"""
        print("EMAIL: \n")
        print(msg)
        # email(msg)

    except Exception as e:
        msg = f"""\
Subject: Update Failed

Update failed due to an error:
{traceback.format_exc()}"""
        print("EMAIL: \n")
        print(msg +  "\nended")
        # email(msg)
        raise e
    finally:
        u_logger.save()
