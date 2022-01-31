import time
import datetime
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

# Config
config = dotenv_values("../.env")

# TODO finish email
# E-mail
context = ssl.create_default_context()
message = """\
Subject: Test for SMTP

This is a message from Python."""

with smtplib.SMTP_SSL(
    config["SMTP_SERVER"], config["PORT"], context=context) as server:
    server.login(config["SENDER_EMAIL"], config["PASSWORD"])
    server.sendmail(config["SENDER_EMAIL"], config["RECEIVER_EMAIL"], message)

exit(0)


# Init Loggers
logging.basicConfig(level=logging.DEBUG)
u_logger = UpdateLogger("./update_log.json")
update_log = u_logger.log

FAIL_API = "https://store.steampowered.com/api/appdetails/?appids=360032"

# Max owner limit, if an app's owner count breaks the limit
# that app will be ignored
# MAX_OWNERS = 1_000_000
MAX_OWNERS = 1_000_000

# Time to wait in between request in ms
STEAM_WAIT_DURATION = 1
STEAMSPY_WAIT_DURATION = 1
# STEAM_REQUEST_LIMIT = 100_000
STEAM_REQUEST_LIMIT = 3

# File paths
APPLIST_FILE = "./applist.json"
APPLIST_FILTERED_FILE = "./applist_filtered.json"

# API's
# Append appid to app details API to get app details
APPLIST_API = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
STEAM_APP_DETAILS_API_BASE = "https://store.steampowered.com/api/appdetails/?appids="
STEAMSPY_APP_DETAILS_API_BASE = "https://steamspy.com/api.php?request=appdetails&appid="


# TODO record latest request date
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

    limited_applist = applist[:10]
    applist_index = update_log["applist_index"]

    logging.info(f"Length of Limited Applist: {len(limited_applist):,}")
    logging.debug(f"Applist Index: {applist_index}")

    apps_data = {}

    if applist_index == -1:
        skip = False
    else:
        skip = True

    # =============================== #
    #  Get App Details for each App   #
    # =============================== #
    logging.debug("Iterating over LIMITED APPLIST...")
    for app in limited_applist:
        appid = app["appid"]

        if skip:
            # skip to where the last iteration ended
            if applist_index != appid:
                continue
            else:
                skip = False

        # API's
        steamspy_api = STEAMSPY_APP_DETAILS_API_BASE + str(appid)
        steam_api = STEAM_APP_DETAILS_API_BASE + str(appid)

        # Remove redundant appid from field of the app
        # becuse it'll be used as an index in the DB
        app.pop("appid")

        # ====================== #
        #  FETCH FROM STEAMSPY   #
        # ====================== #
        steamspy_data = fetch(steamspy_api)

        # Check minimum owner count to eliminate games over a million owners
        min_owner_count = get_min_owner_count(steamspy_data)

        if min_owner_count > MAX_OWNERS:
            logging.debug(f"App: '{appid}' has {min_owner_count:,} owners which is over {MAX_OWNERS=:,}. Skipping...")
            logging.debug("Skipping...")
            continue

        # Update app info
        steamspy_keys = ["owners", "price", "positive", "negative", "tags"]
        app_details_from_steamspy = {k:v for k, v in steamspy_data.items() if k in steamspy_keys}
        app.update(app_details_from_steamspy)


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
        steam_response = fetch(steam_api)[str(appid)]
        update_log["last_request_to_steam"] = str(datetime.datetime.utcnow())
        update_log["steam_request_count"] += 1

        if steam_response["success"]:
            steam_data = steam_response["data"]
            # Check if app is a game
            if steam_data["type"] != "game":
                logging.debug(f"App '{appid}' is not a game. Skipping...")
                continue
            else:
                steam_keys = ["release_date", "developers", "publishers", "header_image",
                        "screenshots", "categories", "genres", "short_description",
                        "about_the_game", "detailed_description", "platforms",
                        "supported_languages", "website"]
                app_details_from_steam = {k:v for k, v in steam_data.items() if k in steam_keys}

                # Update the app info
                app.update(app_details_from_steam)
                update_log["updated_apps"] += 1
                # Record to apps_data
                apps_data[appid] = app
        else:
            logging.debug(f"Steam responded with {steam_response}. AppID: {appid}")
            update_log["rejected_apps"].append(appid)
            continue

    if update_log["steam_request_limit_reached"]:
        update_log["applist_index"] = appid
        update_log["steam_request_count"] = 0
        update_log["steam_request_limit_reached"] = False
    else:
        # If the last item in the app list is updated
        # without breaking the steam's request limit
        # reset applist index to -1
        update_log["applist_index"] = -1

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


if __name__ == "__main__":
    try:
        main()
    except Error as e:
        raise e
    finally:
        u_logger.save()
