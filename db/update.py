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

try:
    from errors import (
        Error, RequestTimeoutError, RequestFailedError,
        UnauthorizedError, ForbiddenError, NotFoundError,
        ServerError, SteamResponseError
    )
    from update_logger import UpdateLogger
    from appdata import AppDetails, AppSnippet
    from database import (
        DATABASE_PATH, Connection,
        insert_app, insert_non_game_app, insert_rejected_app,
        get_non_game_apps, get_rejected_apps)
except:
    from .errors import (
        Error, RequestTimeoutError, RequestFailedError,
        UnauthorizedError, ForbiddenError, NotFoundError,
        ServerError, SteamResponseError
    )
    from .update_logger import UpdateLogger
    from .appdata import AppDetails, AppSnippet
    from .database import (
        DATABASE_PATH, Connection,
        insert_app, insert_non_game_app, insert_rejected_app,
        get_non_game_apps, get_rejected_apps)


logging.debug(f"Database Path: {DATABASE_PATH}")

# Dirs
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)


# Init Loggers
logging.basicConfig(level=logging.INFO)

update_logger = UpdateLogger(os.path.join(current_dir, "update_log.json"))
update_log = update_logger.log

# Config
env = dotenv_values(os.path.join(parent_dir, ".env"))

# Max owner limit
# if an app's owner count breaks this limit
# that app will not be stored into the database
MAX_OWNERS = 1_000_000

# Time to wait in between request in seconds
STEAM_WAIT_DURATION = 2
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


# TODO email weekly report
# TODO check for lastest request to steam
# if two days haven't passed don't excute the script
# check this before main(), in the if __name__ == "__main__" block

def main():
    print("===             DB UPDATE         "   ===")
    print(f"=== Date: {datetime.datetime.utcnow()} ===")

    applist_fetched = update_log["applist_fetched"]

    # ========================= #
    #  Get App List from Steam  #
    # ========================= #
    if not applist_fetched:
        logging.debug(f"Fetching applist from: {APPLIST_API}")

        applist = fetch_applist(APPLIST_API)
        update_log["steam_request_count"] += 1

        # Save to File
        write_to_json(applist, APPLIST_FILE)
        update_log["applist_fetched"] = True


    # Get Saved Applist
    with open(APPLIST_FILE, "r") as f:
        applist = json.load(f)


    applist_index = update_log["applist_index"]

    applist_length = len(applist[applist_index:])
    update_log["applist_length"] = applist_length

    print(f"Length of Applist: {applist_length:,}")
    print(f"Starting From Index: {applist_index}")
    print(f"Current Steam Request Count: {update_log['steam_request_count']}")


    # For testing use limited applist
    # limited_applist = applist[applist_index : applist_index + 30]

    print("Starting to iterate over Applist:")
    # =============================== #
    #  Get App Details for each App   #
    # =============================== #
    global LATEST_INDEX

    with Connection(DATABASE_PATH) as db:
        non_game_apps = get_non_game_apps(db)

    for i, app in enumerate(applist[applist_index:]):
        LATEST_INDEX = i
        print(f"Iteration: {i}", end="\r")


        app_id = app["app_id"]

        # If app is not a game skip
        if app_id in non_game_apps:
            logging.debug(f"App is not a game. AppID: '{app_id}'\nSkipping...")
            continue

        app_details = AppDetails({"name": app["name"], "app_id": app["app_id"]})

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
        app_details.update(app_details_from_steamspy)

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
                logging.debug(f"App '{app_id}' is not a game. Recording app_id then skipping...")

                with Connection(DATABASE_PATH) as db:
                    insert_non_game_app(app_id, db)

                update_log["non_game_apps"] += 1
                continue
            else:
                app_details_from_steam = map_steam_data(steam_data)

                # Update the app info
                app_details.update(app_details_from_steam)

                # Save to db
                with Connection(DATABASE_PATH) as db:
                    insert_app(app_details, db)

                update_log["updated_apps"] += 1
        else:
            logging.debug(f"Steam responded with {steam_response}. AppID: {app_id}")

            with Connection(DATABASE_PATH) as db:
                insert_rejected_app(app_id, db)

            update_log["rejected_apps"] += 1
            continue

    if update_log["steam_request_limit_reached"]:
        update_log["applist_index"] += i
        update_log["steam_request_count"] = 0
        update_log["steam_request_limit_reached"] = False
    else:
        # If the last item in the app list is updated, reset the log
        update_log["reset_log"] = True




def fetch(api: str) -> dict:
    """Makes a request to an API and returns JSON. If request fails will raise Exeception."""
    response = request_from(api)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 432:
        print(f"\n432 Too many requests? API: {api}\nWaiting 30 secs...\n")
        time.sleep(30)
        print("Trying again...")
        return fetch(api)
    elif response.status_code == 429:
        print(f"\n432 Too many requests? API: {api}\nWaiting 1 min...\n")
        time.sleep(60)
        print("Trying again...")
        return fetch(api)
    elif response.status_code == 500:   # server error
        print(f"\n500 Server Error :{api}\nWaiting 30 secs...\n")
        time.sleep(30)
        print("Trying again...")
        raise ServerError(api, update_log)
    elif response.status_code == 502:
        print(f"\n502 Bad Gateway :{api}\nWaiting 30 secs...\n")
        time.sleep(30)
        print("Trying again...")
        return fetch(api)
    elif response.status_code == 401:
        raise UnauthorizedError(api, update_log)
    elif response.status_code == 403:
        raise ForbiddenError(api, update_log)
    elif response.status_code == 404:
        raise NotFoundError(api, update_log)
    else:
        raise RequestFailedError(f"API: {api} failed with {response.status_code} status code.", update_log)


def fetch_applist(api: str):
    """Steam's response format: {
        'applist': {
            'apps': [
                {appid: int, name: str}
            ]
        }"""

    update_log["last_request_to_steam"] = str(datetime.datetime.utcnow())
    response_json = fetch(api)
    applist = []

    # Save each app that has a name
    for app in response_json["applist"]["apps"]:
        if app["name"]:
            applist.append(
                {
                    "app_id": app["appid"],
                    "name": app["name"]
                }
            )
    return applist


def request_from(api: str, timeout=1):
    """Tries 3 times before raising TimeoutError"""
    attempt = 1
    while attempt <= 2:
        try:
            response = requests.get(api, timeout=timeout)
            return response
        except requests.Timeout:
            logging.debug("Request Timed Out:", api)
            logging.debug("Attempt:", attempt)
            time.sleep(10)
            attempt += 1

    raise RequestTimeoutError(api, update_log)


def map_steam_data(steam_data: dict) -> dict:
    """Parses Steam data and returns it in a better format
    returns: {
        developers, publishers,
        release_date, coming_soon,
        genres, categories,
        about_the_game, short_description,
        detailed_description,
        website, header_image, screenshots,
        languages, windows, mac, linux
    }
    """
    keys = [
        "developers", "publishers", "about_the_game",
        "short_description", "detailed_description",
        "website", "header_image", "screenshots"
        ]
    available_keys = [k for k in keys if k in steam_data.keys()]
    app_details = {k:v for k, v in steam_data.items() if k in available_keys}

    # SPECIAL CASES

    # Simplify genres and categories fields. For example:
    # genres: [{'id': 23, 'description': 'Indie'}]
    # Turns into:
    # genres: {'Indie': 23}
    genres_categs = {}
    for key in ["genres", "categories"]:
        try:
            steam_data[key]
        except KeyError:
            genres_categs[key] = {}
            continue

        genres_categs[key] = {}
        for obj in steam_data[key]:
            genres_categs[key].update({obj["description"]: obj["id"]})

    # Release Date
    try:
        release_date = steam_data["release_date"]["date"]
        coming_soon = steam_data["release_date"]["coming_soon"]
        try:
            release_date = format_date(release_date)
        except IndexError:
            pass
    except KeyError:
        release_date = ""
        coming_soon = False

    # Languages
    try:
        languages = steam_data["supported_languages"]
        # if string is in HTML format
        # check if it contains English then don't bother with parsing it
        if "<" in languages:
            if "English" in languages:
                languages = "English"
            else:
                languages = ""
    except KeyError:
        languages = ""

    # Platforms
    try:
        platforms = steam_data["platforms"]
    except KeyError:
        platforms = {"windows": False, "mac": False, "linux": False}

    # UPDATE
    app_details.update({
        "release_date": release_date,
        "coming_soon": coming_soon,
        "genres": genres_categs["genres"],
        "categories": genres_categs["categories"],
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
    if steamspy_data["price"]:
        steamspy_data["price"] = int(steamspy_data["price"])

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


def get_average(owner_count: str) -> int:
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


def write_to_json(data: any, file_path: str, indent=None):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=indent)


def email(msg):
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(
        env["SMTP_SERVER"], env["PORT"], context=context) as server:
        server.login(env["SENDER_EMAIL"], env["PASSWORD"])
        server.sendmail(env["SENDER_EMAIL"], env["RECEIVER_EMAIL"], msg)






if __name__ == "__main__":
	try:
		main()

		success_msg = f"""\
Subject: Update Successful

Updated Apps: {update_log["updated_apps"]:,} / {update_log["applist_length"]:,}
Rejected Apps: {update_log["rejected_apps"]}
Non-Game Apps: {update_log["non_game_apps"]}
Steam Request Count: {update_log["steam_request_count"]}
"""

		print("")
		print("Info: \n")
		print(success_msg)
		email(success_msg)

	except (Exception, KeyboardInterrupt) as e:
		fail_msg = f"""\
Subject: Update Failed

Updated Apps: {update_log["updated_apps"]:,} / {update_log["applist_length"]:,}
Rejected Apps: {update_log["rejected_apps"]}
Non-Game Apps: {update_log["non_game_apps"]}
Steam Request Count: {update_log["steam_request_count"]}

Update failed due to an error:
{traceback.format_exc()}
"""
		print("")
		print(f"--> Current Steam Request Count: {update_log['steam_request_count']}")

		update_log["applist_index"] += LATEST_INDEX
		print(f"--> Recording applist_index as : {update_log['applist_index']}")

		email(fail_msg)
		raise e
	finally:
		update_logger.save()
		print("Update logger saved.\n")
