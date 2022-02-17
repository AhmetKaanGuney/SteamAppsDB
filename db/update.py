import os
import sys
import time
import math
import datetime
import traceback
import json
import logging
import smtplib, ssl

import requests
from dotenv import dotenv_values

try:
    from errors import (
        FetchError, RequestTimeoutError, RequestFailedWithUnknownError,
        UnauthorizedError, ForbiddenError, NotFoundError,
        ServerError, SteamResponseError
    )
    from update_logger import UpdateLogger
    from appdata import AppDetails, AppSnippet
    from database import (
        APPS_DB_PATH, Connection,
        insert_app, insert_non_game_app, insert_failed_request,
        get_non_game_apps, get_failed_requests)
except:
    from .errors import (
        FetchError, RequestTimeoutError, RequestFailedWithUnknownError,
        UnauthorizedError, ForbiddenError, NotFoundError,
        ServerError, SteamResponseError
    )
    from .update_logger import UpdateLogger
    from .appdata import AppDetails, AppSnippet
    from .database import (
        APPS_DB_PATH, Connection,
        insert_app, insert_non_game_app, insert_failed_request,
        get_non_game_apps, get_failed_requests)


logging.debug(f"Apps Database Path: {APPS_DB_PATH}")

# Dirs
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
DEBUG_LOG = "./debug.log"


# Init Loggers
logging.basicConfig(level=logging.DEBUG)

update_logger = UpdateLogger(os.path.join(current_dir, "update_log.json"))
update_log = update_logger.log

# Config
env = dotenv_values(os.path.join(parent_dir, ".env"))

# Max owner limit
# if an app's owner count breaks this limit
# that app will not be stored into the database
MAX_OWNERS = 1_000_000

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

# TODO email weekly report

def main():
    global start_time
    start_time = time.time()
    print("===           DB UPDATE          ===")
    print(f"=== Start Date: {get_datetime_str()} ===")

    # ========================= #
    #  Get App List from Steam  #
    # ========================= #
    print("Checking if applist already fetched...")
    if update_log["applist_fetched"]:
        print("Applist alredy fetched!")
    else:
        print(f"Fetching applist from: {APPLIST_API}")

        applist = fetch_applist(APPLIST_API)
        update_log["steam_request_count"] += 1

        # Save to File
        write_to_json(applist, APPLIST_FILE)
        update_log["applist_fetched"] = True


    # Get Saved Applist starting from where it's left off
    applist_index = update_log["applist_index"]
    with open(APPLIST_FILE, "r") as f:
        applist = json.load(f)

    remaining_apps = applist[applist_index:]

    applist_length = len(applist)
    remaining_length = len(remaining_apps)

    update_log["applist_length"] = applist_length
    update_log["remaining_apps"] = remaining_length

    print(f"Applist Length: {applist_length:,}")
    print(f"Starting From Index: {applist_index}")
    print(f"Current Steam Request Count: {update_log['steam_request_count']}")


    # For testing use limited applist
    # limited_applist = applist[applist_index : applist_index + 30]

    # =============================== #
    #     Get Apps to be Ignored      #
    # =============================== #
    apps_to_ignore = []

    with Connection(APPS_DB_PATH) as db:
        non_game_apps = get_non_game_apps(db)
        failed_requests = get_failed_requests(f"WHERE cause == 'failed'", db)

    if failed_requests:
        # Get only app_ids
        failed_list = [i["app_id"] for i in failed_requests]
        for _id in failed_list:
            apps_to_ignore.append(_id)

    if non_game_apps:
        for _id in non_game_apps:
            apps_to_ignore.append(_id)

    print(f"Apps to be ignored: {len(apps_to_ignore):,}")


    # =============================== #
    #  Get App Details for each App   #
    # =============================== #
    global LAST_INDEX

    print(f"Fetching apps:")

    for i, app in enumerate(remaining_apps):
        print(f"Progress: {i:,} / {remaining_length:,}", end="\r")
        LAST_INDEX = i

        app_id = app["app_id"]

        # Save log every 100th iteration
        if i % 100 == 0:
            update_logger.save()

        # If app is not a game skip
        if app_id in apps_to_ignore:
            continue

        # ================================= #
        #   Wait Before Making Any Request  #
        # ================================= #
        time.sleep(RATE_LIMIT)

        # Create Appdetails
        app_details = AppDetails({"name": app["name"], "app_id": app["app_id"]})

        # API's
        steamspy_api = STEAMSPY_APP_DETAILS_API_BASE + str(app_id)
        steam_api = STEAM_APP_DETAILS_API_BASE + str(app_id)

        # ====================== #
        #  FETCH FROM STEAMSPY   #
        # ====================== #
        try:
            steamspy_data = fetch(steamspy_api)
        except FetchError as e:
            # Record failed request and skip to next app
            error_name = type(e).__name__
            print(f"\n{error_name}: {e.response.status_code} | URL: {e.response.url}\nSkipping...")

            with Connection(APPS_DB_PATH) as db:
                insert_failed_request(app_id, "steamspy", error_name, e.response.status_code, db)

            update_log["failed_requests"] += 1
            continue


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
            print(
                f"Request limit reached! "
                + f"Request count: {update_log['steam_request_count']} | "
                + f"Request Limit: {STEAM_REQUEST_LIMIT}"
                )
            break

        try:
            # Response Example : {"000000": {"success": true, "data": {...}}}
            steam_response = fetch(steam_api)[str(app_id)]
        except FetchError as e:
            error_name = type(e).__name__
            print(f"\n{error_name}: {e.response.status_code} | URL: {e.response.url}\nSkipping...")

            with Connection(APPS_DB_PATH) as db:
                insert_failed_request(app_id, "steam", error_name, e.response.status_code, db)

            update_log["last_request_to_steam"] = get_datetime_str()
            update_log["steam_request_count"] += 1
            update_log["failed_requests"] += 1
            continue

        update_log["last_request_to_steam"] = get_datetime_str()
        update_log["steam_request_count"] += 1

        if steam_response["success"]:
            steam_data = steam_response["data"]
            # Check if app is a game
            if steam_data["type"] != "game":
                logging.debug(f"App '{app_id}' is not a game. Recording app_id then skipping...")

                # Record non-game_apps so they aren't requested for in the future
                with Connection(APPS_DB_PATH) as db:
                    insert_non_game_app(app_id, db)

                update_log["non_game_apps"] += 1
                continue
            else:
                app_details_from_steam = map_steam_data(steam_data)

                # Update the app info
                app_details.update(app_details_from_steam)

                # Save to db
                with Connection(APPS_DB_PATH) as db:
                    insert_app(app_details, db)

                update_log["updated_apps"] += 1
        else:
            with Connection(APPS_DB_PATH) as db:
                insert_failed_request(app_id, "steam", "failed", None, db)

            update_log["failed_requests"] += 1
            continue



def fetch(api: str) -> dict:
    """Makes a request to an API and returns JSON. If request fails will raise Exeception."""
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
        else:
            if response.status_code == 429:
                print(f"\nHTTPError: 429 - Too Many Requests | URL: {response.url}")
            print("Waiting 30 secs...")
            time.sleep(30)

        print("Trying again...")
        return fetch(api)

    elif 500 <= response.status_code < 600:
        print(f"\nServer Error: {response.status_code} | URL: {response.url}")
        debug_log(msg)
        # Raise error cuz dont know how to handle it
        raise ServerError(response, update_log)
    else:
        print(f"\nUnknownHTTPError {response.status_code} | URL: {response.url}")
        debug_log(msg)
        raise RequestFailedWithUnknownError(response, update_log)


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
            logging.debug("Request Timed Out:", api)
            logging.debug("Attempt:", attempt)
            # Wait for 5 then for 10 secs
            time.sleep(attempt * attempt_wait)
            attempt += 1
        except requests.exceptions.ConnectionError as e:
            if connection_errors == 0:
                print("")
            connection_errors += 1
            if connection_errors >= connection_error_limit:
                print(f"Couldn't connect for {connection_wait * connection_errors // 60} mins...")
                raise e
            else:
                print(f"Connection Error! Error Count: {connection_errors} | Waiting for {connection_wait} secs...")
                time.sleep(connection_wait)
                print("Attempting again...")
                continue
    # If reached attempt limit
    raise RequestTimeoutError(response, update_log)


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

def get_datetime_str():
    return datetime.datetime.utcnow().strftime(DATETIME_FORMAT)

def subtract_times(end, start) -> float:
    return (end - start) // (60 * 60)

def debug_log(msg: dict):
    """Append to log"""
    with open(DEBUG_LOG, "a") as f:
        f.write("\n======================================================\n")
        f.write(",\n".join(str(k) + " : " + str(msg[k]) for k in msg))


def email(msg):
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        env["SMTP_SERVER"], env["PORT"], context=context) as server:
        server.login(env["SENDER_EMAIL"], env["PASSWORD"])
        server.sendmail(env["SENDER_EMAIL"], env["RECEIVER_EMAIL"], msg)


def create_msg(update_log, run_time, traceback=None):
    ul = update_log
    updated_apps = ul["updated_apps"]
    applist_length = ul["applist_length"]
    old_index = ul["applist_index"]
    failed_requests = ul["failed_requests"]
    non_game_apps = ul["non_game_apps"]
    steam_request_count = ul["steam_request_count"]

    if traceback:
        subject = "Update Failed"
        traceback_section = f"\nUpdate failed due to an error:\n{traceback.format_exc()}"
    else:
        subject = "Update Successful"
        traceback_section = ""

    return f"""\
Subject: {subject}

Run Time        : {run_time:.1f} hours
Updated Apps    : {updated_apps:,} / {applist_length:,}
Remaning Apps   : {applist_length - (old_index + LAST_INDEX):,}
Non-Game Apps   : {non_game_apps:,}
Failed Requests : {failed_requests:,}
Steam Requests  : {steam_request_count:,}
{traceback_section}"""


if __name__ == "__main__":

    # Check time passed since last request
    now = datetime.datetime.utcnow()
    last_request_to_steam = datetime.datetime.strptime(update_log["last_request_to_steam"], DATETIME_FORMAT)
    time_passed = now - last_request_to_steam
    a_day = datetime.timedelta(hours=24)

    ignore_timer = False
    if len(sys.argv) == 2:
        if sys.argv[1] == "--ignore-timer":
            ignore_timer = True
        if sys.argv[1] == "-h":
            print("Use '--ignore-timer' to skip safety check for last request to Steam.\n")
            exit(0)

    if not ignore_timer:
        if time_passed.days < 1:
            print("1 day hasn't passed since the last update.")
            print(f"Now                    : {now.strftime(DATETIME_FORMAT)}")
            print(f"Last Request to Steam  : {last_request_to_steam.strftime(DATETIME_FORMAT)}")
            print(f"Time Passed            : {str(time_passed).split('.')[0]}")
            print(f"Retry After            : {str(a_day - time_passed).split('.')[0]}")
            print("")
            exit(0)
    else:
        print("Ignoring timer!")


    # =================== #
    #         RUN         #
    # =================== #
    ul = update_log
    try:
        main()

        run_time = subtract_times(time.time(), start_time)
        success_msg = create_msg(ul, run_time)
        print(f"\n{success_msg}")
        email(success_msg)

        # After emailing reset steam request count
        if ul["steam_request_limit_reached"]:
            ul["steam_request_count"] = 0
            ul["steam_request_limit_reached"] = False
        else:
            # If the last item in the app list is updated
            # without reaching steam_request_limit
            # that means update finished so reset the log
            ul["reset_log"] = True

    except (Exception, KeyboardInterrupt) as e:
        run_time = subtract_times(time.time(), start_time)
        fail_msg = create_msg(ul, run_time, traceback=traceback)
        print("")

        # Don't email if there is a connection error
        if not isinstance(e, requests.exceptions.ConnectionError):
            email(fail_msg)
        raise e

    finally:
        run_time = subtract_times(time.time(), start_time)
        print(f"=== End Date  : {get_datetime_str()} ===")

        print(f"Run Time: {run_time:.1f} hours")

        ul["applist_index"] += LAST_INDEX
        ul["remaining_apps"] = ul["applist_length"] - ul["applist_index"]

        print(f"--> Current Steam Request Count: {ul['steam_request_count']}")
        print(f"--> Recording applist_index as : {ul['applist_index']}")
        update_logger.save()
        print("\nUpdate logger saved.\n")
