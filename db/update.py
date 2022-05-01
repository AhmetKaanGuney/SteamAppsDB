import os
import sys
import time
import math
import datetime
import traceback
import json
import logging
import re

import requests

try:
    from errors import (
        FetchError, RequestTimeoutError, TooManyRequestsError,
        UnauthorizedError, ForbiddenError, NotFoundError,
        ServerError, RequestFailedWithUnknownError
    )
    from update_logger import UpdateLogger
    from appdata import AppDetails
    from database import (
        APPS_DB_PATH, Connection,
        insert_app, insert_non_game_app,
        insert_failed_request, insert_app_over_million,
        get_non_game_apps, get_failed_requests
    )
except ImportError:
    from .errors import (
        FetchError, RequestTimeoutError, TooManyRequestsError,
        UnauthorizedError, ForbiddenError, NotFoundError,
        ServerError, RequestFailedWithUnknownError
    )
    from .update_logger import UpdateLogger
    from .appdata import AppDetails
    from .database import (
        APPS_DB_PATH, Connection,
        insert_app, insert_non_game_app,
        insert_failed_request, insert_app_over_million,
        get_non_game_apps, get_failed_requests
    )

logging.debug(f"Apps Database Path: {APPS_DB_PATH}")

# Dirs
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
DEBUG_LOG = os.path.join(current_dir, "./debug.log")
UPDATE_LOG_PATH = os.path.join(current_dir, "update_log.json")
UPDATE_HISTORY_LOG_PATH = os.path.join(current_dir, "update_history.log")

# Init Loggers
logging.basicConfig(level=logging.DEBUG)

update_logger = UpdateLogger(UPDATE_LOG_PATH)
update_log = update_logger.log

OWNER_LIMIT = 1_000_000
REQUEST_TIMEOUT = 15
# Time to wait in between request in seconds
RATE_LIMIT = 1
STEAM_REQUEST_LIMIT = 100_000

# File paths
APPLIST_FILE = os.path.join(current_dir, "applist.json")
APPLIST_FILTERED_FILE = os.path.join(current_dir, "applist_filtered.json")

# API's
# Append appid to app details API to get app details
APPLIST_API = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
STEAM_APP_DETAILS_API_BASE = "https://store.steampowered.com/api/appdetails/?appids="
STEAMSPY_APP_DETAILS_API_BASE = "https://steamspy.com/api.php?request=appdetails&appid="

# Format
DATETIME_FORMAT = "%Y-%m-%d %H:%M"

tracker = {
    "last_index": 0,
    "steam_request_count": 0,
    "updated_apps": 0,
    "non_game_apps": 0,
    "ignored_apps": 0,
    "failed_requests": 0,
    "apps_over_million": 0
}


def main():
    print("||===            UPDATE             ===||")
    print(f"||=== Start Date : {get_datetime_str()} ===||")

    # Get App List from Steam
    applist = load_applist()
    applist_index = update_log["applist_index"]
    remaining_apps = applist[applist_index:]

    applist_length = len(applist)
    remaining_length = len(remaining_apps)

    update_log["applist_length"] = applist_length
    update_log["remaining_length"] = remaining_length

    apps_to_ignore = get_apps_to_ignore()

    print(f"Applist: {applist_length:,} items")
    print(f"Starting from: {applist_index}")
    print(f"Apps to be ignored: {len(apps_to_ignore):,} items")
    print("Fetching apps:")

    for i, app in enumerate(remaining_apps):
        print(f"Progress: {i:,} / {remaining_length:,}", end="\r")

        tracker["last_index"] = i
        app_id = app["app_id"]

        # If app is not a game skip
        if app_id in apps_to_ignore:
            update_log["ignored_apps"] += 1
            tracker["ignored_apps"] += 1
            continue

        # Save log every 100th iteration
        if i % 100 == 0:
            update_logger.save()

        # Wait Before Making Any Request
        time.sleep(RATE_LIMIT)

        # Create Appdetails
        app_details = AppDetails({"name": app["name"], "app_id": app_id})

        # FETCH FROM STEAMSPY
        steamspy_response = fetchProxy("steamspy", app_id)
        if steamspy_response is None:
            update_log["failed_requests"] += 1
            tracker["failed_requests"] += 1
            continue

        # Check minimum owner
        min_owner_count = get_min_owner_count(steamspy_response)

        if min_owner_count > OWNER_LIMIT:
            with Connection(APPS_DB_PATH) as db:
                insert_app_over_million(app_id, db)
                update_log["apps_over_million"] += 1
                tracker["apps_over_million"] += 1
            continue

        # Update app info
        app_details_from_steamspy = map_steamspy_response(steamspy_response)
        app_details.update(app_details_from_steamspy)

        # FETCH FROM STEAM
        if tracker["steam_request_count"] + 1 > STEAM_REQUEST_LIMIT:
            print("\nSteam request limit reached!")
            break

        steam_response = fetchProxy("steam", app_id)

        update_log["last_request_to_steam"] = get_datetime_str()
        update_log["steam_request_count"] += 1
        tracker["steam_request_count"] += 1

        if steam_response is None:
            update_log["failed_requests"] += 1
            tracker["failed_requests"] += 1
            continue

        result = handle_steam_response(app_id, steam_response, app_details)
        if result == "non_game_app":
            update_log["non_game_apps"] += 1
            tracker["non_game_apps"] += 1
        elif result == "failed_request":
            update_log["failed_requests"] += 1
            tracker["failed_requests"] += 1
        elif result == "updated":
            update_log["updated_apps"] += 1
            tracker["updated_apps"] += 1
        else:
            raise ValueError(f"Unexpected return value {result}, from handle_steam_response")


def fetchProxy(api_provider: str, app_id: int) -> dict:
    if api_provider == "steam":
        api_base = STEAM_APP_DETAILS_API_BASE
    elif api_provider == "steamspy":
        api_base = STEAMSPY_APP_DETAILS_API_BASE
    else:
        raise ValueError(f"{api_provider} isn't a valid api provider.")

    api = api_base + str(app_id)

    try:
        response = fetch(api)
        if api_provider == "steam":
            return response[str(app_id)]

        return response

    except Exception as e:
        error_name = type(e).__name__

        with Connection(APPS_DB_PATH) as db:
            if issubclass(type(e), FetchError) and not isinstance(e, RequestTimeoutError):
                status_code = e.response.status_code
            else:
                status_code = None
                debug_log({
                    "error": error_name,
                    "url": api,
                    "traceback": traceback.format_exc()
                })

            insert_failed_request(app_id, api_provider, error_name, status_code, db)

        print(f"\nError: {error_name} | Code: {status_code} | URL: {api}\nSkipping...")
        return None


def fetch(api: str) -> dict:
    """Makes a request to an API and returns JSON. If request fails will raise Exeception."""
    attempt = 0
    while attempt < 2:
        response = attempt_request(api)
        msg = {
            "status_code": response.status_code,
            "url": response.url,
            "headers": response.headers,
            "text": response.text
        }

        if response.status_code == requests.codes.ok:
            return response.json()
        elif 400 <= response.status_code < 500:
            debug_log(msg)

            if response.status_code == 401:
                raise UnauthorizedError(response, update_log)
            elif response.status_code == 403:
                raise ForbiddenError(response, update_log)
            elif response.status_code == 404:
                raise NotFoundError(response, update_log)
            elif response.status_code == 429:
                attempt += 1
                print(f"\nHTTPError: 429 - Too Many Requests | URL: {response.url}")
                print("Waiting 30 secs...")
                time.sleep(30)
                print("Trying again...")
                continue
        elif 500 <= response.status_code < 600:
            debug_log(msg)
            # Raise error cuz dont know how to handle it
            raise ServerError(response, update_log)
        else:
            debug_log(msg)
            raise RequestFailedWithUnknownError(response, update_log)

    # If tried 3 times
    raise TooManyRequestsError(response, update_log)


def attempt_request(api: str):
    """
    Tries 3 times before raising TimeoutError
    If a connection error occurs tries to connect infinitely
    """
    attempt = 1
    attempt_wait = 5
    connection_wait = 10
    connection_errors = 0
    # 60 sec * 10 = 10 mins
    connection_error_limit = 60

    while attempt <= 3:
        try:
            response = requests.get(api, timeout=REQUEST_TIMEOUT)
            return response
        except requests.Timeout:
            logging.debug(f"Request Timed Out: {api}")
            logging.debug(f"Attempt: {attempt}")
            time.sleep(attempt * attempt_wait)
            attempt += 1
        except requests.exceptions.ConnectionError as connection_error:
            if connection_errors == 0:
                print("")
            connection_errors += 1
            if connection_errors >= connection_error_limit:
                print(f"Couldn't connect for {connection_wait * connection_errors // 60} mins...")
                raise connection_error
            else:
                print(f"Connection Error! Error Count: {connection_errors} | Waiting for {connection_wait} secs...")
                time.sleep(connection_wait)
                print("Attempting again...")
                continue
    # If reached attempt limit
    raise RequestTimeoutError(update_log)


def handle_steam_response(app_id, steam_response, app_details):
    """Handles Steam Response and inserts app"""
    if steam_response["success"]:
        steam_data = steam_response["data"]
        # Check if app is a game
        if steam_data["type"] != "game":
            with Connection(APPS_DB_PATH) as db:
                insert_non_game_app(app_id, db)
            return "non_game_app"
        else:
            app_details_from_steam = map_steam_data(steam_data)
            # Update the app info
            app_details.update(app_details_from_steam)

            # Save to db
            with Connection(APPS_DB_PATH) as db:
                insert_app(app_details, db)
                db.execute("DELETE FROM failed_requests WHERE app_id == ?", (app_id, ))
            return "updated"
    else:
        with Connection(APPS_DB_PATH) as db:
            insert_failed_request(app_id, "steam", "failed", None, db)
        return "failed_request"


def fetch_applist(api: str):
    """Steam's response format: {
        'applist': {
            'apps': [
                {appid: int, name: str}
            ]
        }"""

    update_log["last_request_to_steam"] = get_datetime_str()
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


def load_applist() -> dict:
    print("Checking if applist already fetched...")
    if update_log["applist_fetched"]:
        print("Applist alredy fetched!")
    else:
        print(f"Fetching applist from: {APPLIST_API}")

        applist = fetch_applist(APPLIST_API)

        # Save to File
        print("Saving applist...")
        save_json(applist, APPLIST_FILE)
        update_log["applist_fetched"] = True

    with open(APPLIST_FILE, "r") as f:
        applist = json.load(f)

    return applist


def get_apps_to_ignore() -> list:
    apps_to_ignore = []

    with Connection(APPS_DB_PATH) as db:
        non_game_apps = get_non_game_apps(db)
        failed_requests = get_failed_requests("WHERE error == 'failed'", db)

    if failed_requests:
        # Get only app_ids
        failed_list = [i["app_id"] for i in failed_requests]
        for _id in failed_list:
            apps_to_ignore.append(_id)

    if non_game_apps:
        for _id in non_game_apps:
            apps_to_ignore.append(_id)

    return apps_to_ignore


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
    app_details = {k: v for k, v in steam_data.items() if k in available_keys}

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
    release_info = steam_data.get("release_date", None)
    release_date = None
    coming_soon = False

    if release_info:
        date = release_info.get("date", None)
        coming_soon = release_info.get("coming_soon", False)
        if date:
            release_date = format_date(date)

    # Languages
    languages = steam_data.get("supported_languages", "")
    # if string is in HTML format
    # check if it contains English then don't bother with parsing it
    if languages and ("<" in languages):
        if "English" in languages:
            languages = "English"
        else:
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


def map_steamspy_response(response: dict) -> dict:
    """Parses SteamSpy response and returns it in a better format
    returns: {
        'price': [int, None],
        'owner_count: int',
        'positive_reviews: int',
        'negative_reviews': int
        'tags': list,
    }"""
    if response["price"]:
        response["price"] = int(response["price"])

    app_details = {
        "price": response["price"],
        "owner_count": get_average(response["owners"]),
        "rating": calculate_reviews(response["positive"], response["negative"]),
        "positive_reviews": response["positive"],
        "negative_reviews": response["negative"],
        "tags": response["tags"]
    }
    return app_details


def format_date(date: str) -> str:
    """Returns formatted date: YYYY-MM-DD"""
    # input pattern example "8 Feb, 2022"
    pattern = r"\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec), \d{4}"
    test = re.match(pattern, date)

    if test is None:
        return None

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


def calculate_reviews(positive, negative) -> [int, None]:
    rating = 0
    if positive == 0:
        if negative != 0:
            return rating
        return None

    total = positive + negative
    positive_percentage = positive / total * 100
    rating = round(positive_percentage)
    return rating


def get_id_from_url(url: str):
    _id = url.split("=")[-1]
    return int(_id)


def save_json(data: any, file_path: str, indent=None):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=indent)


def get_datetime_str():
    return datetime.datetime.utcnow().strftime(DATETIME_FORMAT)


def subtract_times(end, start) -> float:
    return (end - start) / (60 * 60)


def debug_log(msg: dict):
    """Append to log"""
    try:
        if "<!DOCTYPE html>" in msg["text"]:
            msg["text"] = "<--- HTML Error Response --->"
    except KeyError:
        pass

    with open(DEBUG_LOG, "a") as f:
        f.write(",\n".join(str(k) + " : " + str(msg[k]) for k in msg))
        f.write("\n||======================================================||\n")


def update_history(msg: str):
    with open(UPDATE_HISTORY_LOG_PATH, "a") as f:
        f.write(msg)
        f.write("\n||======================================================||\n")


def create_output(update_log, run_time, traceback=None):
    ul = update_log
    applist_length = ul["applist_length"]
    remaining_length = ul["remaining_length"]

    if traceback:
        state = "Update Failed"
        traceback_section = f"\nUpdate failed due to an error:\n{traceback.format_exc()}"
    else:
        state = "Update Successful"
        traceback_section = ""

    return f"""\
State: {state}
Date : {get_datetime_str()} UTC
Run Time          : {run_time:.1f} hours
All Apps          : {applist_length:,}
Steam Requests    : {tracker["steam_request_count"]:,}
---
Updated Apps      : {tracker["updated_apps"]:,} / {remaining_length:,}
Non-Game Apps     : {tracker["non_game_apps"]:,}
Ignored Apps      : {tracker["ignored_apps"]:,}
Failed Requests   : {tracker["failed_requests"]:,}
Apps Over Million : {tracker["apps_over_million"]:,}
---------------------------------------------
Total Iterations: {tracker["updated_apps"] + tracker["non_game_apps"] + tracker["failed_requests"] + tracker["apps_over_million"] + tracker["ignored_apps"]:,}
{traceback_section}"""


if __name__ == "__main__":
    # Check time passed since last request
    now = datetime.datetime.utcnow()
    last_request_to_steam = datetime.datetime.strptime(update_log["last_request_to_steam"], DATETIME_FORMAT)
    time_passed = now - last_request_to_steam
    a_day = datetime.timedelta(hours=24)

    ignore_timer = False
    if len(sys.argv) == 2:
        if sys.argv[1] == "-h":
            print("Use '--ignore-timer' to skip safety check for last request to Steam.\n")
            exit(0)
        elif sys.argv[1] == "--ignore-timer":
            ignore_timer = True
        else:
            print("Use '--ignore-timer' to skip safety check for last request to Steam.\n")
            exit(0)

    if not ignore_timer:
        if time_passed.days < 1:
            print("1 day hasn't passed since the last update.")
            print(f"Now                    : {now.strftime(DATETIME_FORMAT)}")
            print(f"Last Request to Steam  : {last_request_to_steam.strftime(DATETIME_FORMAT)}")
            print(f"Time Passed            : {str(time_passed).split('.')[0]}")
            print(f"Retry After            : {str(a_day - time_passed).split('.')[0]}\n")
            exit(0)
    else:
        print("Ignoring timer!")

    # =================== #
    #         RUN         #
    # =================== #
    ul = update_log
    start_time = time.time()
    output = ""
    try:
        main()
        run_time = subtract_times(time.time(), start_time)
        output = create_output(ul, run_time)
        ul["reset_log"] = True

    except Exception as e:
        run_time = subtract_times(time.time(), start_time)
        output = create_output(ul, run_time, traceback=traceback)

    except KeyboardInterrupt:
        run_time = subtract_times(time.time(), start_time)
        output = create_output(ul,  run_time)

    finally:
        update_history(output)
        print(f"\n\n{output}")

        run_time = subtract_times(time.time(), start_time)
        ul["applist_index"] += tracker["last_index"]
        ul["remaining_length"] = ul["applist_length"] - ul["remaining_length"]
        update_logger.save()

        print(f"||=== End Date  : {get_datetime_str()} ===||")
        print(f"--> Run Time            : {run_time:.1f} hours")
        print(f"--> Total Steam Requests: {ul['steam_request_count']}")
        print(f"--> Total Apps Ignored  : {ul['ignored_apps']}")
        print(f"--> Recording applist_index as : {ul['applist_index']}")
        print()
