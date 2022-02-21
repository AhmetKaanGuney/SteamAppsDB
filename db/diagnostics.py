"""
Diagnostics tool for apps database
Usage: diagnostics.py [action]
Actions:
status      : Shows db status
freeze      : Writes non_game_apps and failed_requests to files
merge       : saves diagnosis files to database
pull        : fetches diagnosis data from remote server and stores into apps.db
fix         : try to refetch failed requests
"""
import os
import sys
import json
import time
import traceback

from update_logger import UpdateLogger
from errors import FetchError
from appdata import AppDetails, AppSnippet
from update import (
    fetch, RATE_LIMIT, UPDATE_LOG_PATH, STEAM_REQUEST_LIMIT,
    STEAM_APP_DETAILS_API_BASE, STEAMSPY_APP_DETAILS_API_BASE,
    map_steam_data, map_steamspy_data, get_min_owner_count,
    MAX_OWNERS, get_datetime_str

)
from database import (
    APPS_DB_PATH, Connection,
    get_failed_requests, get_non_game_apps,
    insert_failed_request, insert_non_game_app,
    insert_app_over_million, insert_app
)

ARGS = sys.argv

current_dir = os.path.dirname(__file__)
write_to_json = False

SERVER_IP = "192.168.1.119"
PORT = "5000"
NON_GAME_APPS_API = f"http://{SERVER_IP}:{PORT}/GetNonGameApps"
FAILED_REQUESTS_API = f"http://{SERVER_IP}:{PORT}/GetFailedRequests"

DIAGNOSIS_DIR = os.path.join(current_dir, "diagnosis")
FAILED_REQUESTS_PATH = os.path.join(current_dir, "diagnosis/failed_requests.json")
NON_GAME_APPS_PATH = os.path.join(current_dir, "diagnosis/non_game_apps.json")
SPLIT_DIR = os.path.join(current_dir, "db_split")

update_logger = UpdateLogger(UPDATE_LOG_PATH)
update_log = update_logger.log

def main():
    if len(ARGS) == 2:
        if ARGS[1] == "-h":
            print(__doc__)
            exit(0)
        elif ARGS[1] == "status":
            status()
            exit(0)
        elif ARGS[1] == "freeze":
            freeze()
            exit(0)
        elif ARGS[1] == "merge":
            merge()
            exit(0)
        elif ARGS[1] == "pull":
            pull()
            exit(0)
        elif ARGS[1] == "fix":
            fix()
        else:
            print(__doc__)
            exit(0)
    else:
        print(__doc__)
        exit(0)


def status():
    where = "WHERE error != 'failed'"
    with Connection(APPS_DB_PATH) as db:
        failed_requests = get_failed_requests(where, db)

    print(f"Failed Requests ({len(failed_requests)}) - without error: 'failed': ")
    for i in failed_requests:
        print(f"Error: {i['error']} | Status Code: {i['status_code']} | AppID: {i['app_id']} | Api Provider: {i['api_provider']}")

    print()

    with Connection(APPS_DB_PATH) as db:
        non_game_apps = get_non_game_apps(db)

    print(f"Non-Game Apps: {len(non_game_apps):,}")
    print()


def freeze():
    # Create dir if it doesnt exists
    if not os.path.exists(DIAGNOSIS_DIR):
        os.mkdir(DIAGNOSIS_DIR)

    with Connection(APPS_DB_PATH) as db:
        print("Loading failed requests...")
        failed_requests: list[dict] = get_failed_requests("", db)
        print("Loading non-game apps...")
        non_game_apps: list[int] = get_non_game_apps(db)

    print("Writing failed requests...")
    with open(FAILED_REQUESTS_PATH, "w") as failed_file:
        json.dump(failed_requests, failed_file)

    print("Writing non-game apps...")
    with open(NON_GAME_APPS_PATH, "w") as non_game_file:
        json.dump(non_game_apps, non_game_file)


def merge():
    print("Reading failed requests...")
    if os.path.exists(FAILED_REQUESTS_PATH):
        failed_size = os.path.getsize(FAILED_REQUESTS_PATH)
        if failed_size == 0:
            print(f"{FAILED_REQUESTS_PATH} is empty!\nSkipping...")
        else:
            with open(FAILED_REQUESTS_PATH, "r") as failed_file:
                failed_requests = json.load(failed_file)

            print("Saving failed requests:")
            with Connection(APPS_DB_PATH) as db:
                for i, request in enumerate(failed_requests):
                    print(f"Progress: {i:,}", end="\r")
                    try:
                        insert_failed_request(request["app_id"], request["api_provider"], request["error"], request["status_code"], db)
                    except KeyError:
                        insert_failed_request(request["app_id"], request["api_provider"], request["cause"], request["status_code"], db)

            print("\nCompleted!")
    else:
        print("File not found! Skipping failed requests...")


    print("Reading non-game apps...")
    if os.path.exists(NON_GAME_APPS_PATH):
        non_game_size = os.path.getsize(NON_GAME_APPS_PATH)
        if non_game_size == 0:
            print(f"{NON_GAME_APPS_PATH} is empty!\nSkipping...")
        else:
            with open(NON_GAME_APPS_PATH, "r") as non_game_file:
                non_game_apps = json.load(non_game_file)

            print("Saving non-game apps:")
            with Connection(APPS_DB_PATH) as db:
                for i, app_id in enumerate(non_game_apps):
                    print(f"Progress: {i:,}", end="\r")
                    insert_non_game_app(app_id, db)
            print("\nCompleted!")
    else:
        print("File not found! Skipping non-game apps...")

    print("Merge Finished!\n")


def pull():
    print("Fetching non_game_apps...")
    non_game_apps = fetch(NON_GAME_APPS_API)
    print("Fetching failed_requests...")
    failed_requests = fetch(FAILED_REQUESTS_API)

    with Connection(APPS_DB_PATH) as db:
        print("Inserting non_game_apps...")
        for app_id in non_game_apps:
            insert_non_game_app(app_id, db)

        print("Inserting failed_requests...")
        for i in failed_requests:
            insert_failed_request(
                i["app_id"], i["api_provider"], i["error"], i["status_code"], db
            )


def fix():
    with Connection(APPS_DB_PATH) as db:
        failed_requests = get_failed_requests("WHERE error != 'failed'", db)

    failed_length = len(failed_requests)
    fixed_apps = 0
    print("Refetching Failed Requests...")
    for i, row in enumerate(failed_requests):
        print(f"Progress: {i:,} / {failed_length}", end="\r")

        app_id = row["app_id"]

        time.sleep(RATE_LIMIT)

        # Create Appdetails
        app_details = AppDetails({"app_id": app_id})

        # API's
        steamspy_api = STEAMSPY_APP_DETAILS_API_BASE + str(app_id)
        steam_api = STEAM_APP_DETAILS_API_BASE + str(app_id)

        # ====================== #
        #  FETCH FROM STEAMSPY   #
        # ====================== #
        try:
            steamspy_data = fetch(steamspy_api)
        except Exception as e:
            error_name = type(e).__name__
            with Connection(APPS_DB_PATH) as db:
                # If Exception is not a type of FecthError
                # there might not be a response object
                # So record the unexpected exception without referring to the response obj.

                if issubclass(type(e), FetchError) and not isinstance(e, RequestTimeoutError):
                    print(f"\n{error_name}: {e.response.status_code} | URL: {steamspy_api}\nSkipping...")
                    insert_failed_request(app_id, "steamspy", error_name, e.response.status_code, db)
                else:
                    print(f"\nError : {error_name} | URL: {steam_api}\nSkipping...")
                    msg = {
                        "error": error_name,
                        "url": steamspy_api,
                        "traceback": traceback.format_exc()
                    }
                    insert_failed_request(app_id, "steamspy", error_name, None, db)
                    debug_log(msg)
            continue

        # Check minimum owner count to eliminate games over a million owners
        min_owner_count = get_min_owner_count(steamspy_data)

        if min_owner_count > MAX_OWNERS:
            with Connection(APPS_DB_PATH) as db:
                insert_app_over_million(app_id, db)
                update_log["apps_over_million"] += 1
            continue

        # Update app info
        app_details_from_steamspy = map_steamspy_data(steamspy_data)
        app_details.update(app_details_from_steamspy)
        app_details.update({"name": steamspy_data["name"]})

        # =================== #
        #  FETCH FROM STEAM   #
        # =================== #
        try:
            # Steam Response Format : {"000000": {"success": true, "data": {...}}}
            steam_response = fetch(steam_api)[str(app_id)]
        except Exception as e:
            error_name = type(e).__name__

            with Connection(APPS_DB_PATH) as db:
                if issubclass(type(e), FetchError) and not isinstance(e, RequestTimeoutError):
                    print(f"\n{error_name}: {e.response.status_code} | URL: {steam_api}\nSkipping...")
                    insert_failed_request(app_id, "steam", error_name, e.response.status_code, db)
                else:
                    print(f"\nError : {error_name} | URL: {steam_api}\nSkipping...")
                    msg = {
                        "error": error_name,
                        "url": steam_api,
                        "traceback": traceback.format_exc()
                    }
                    insert_failed_request(app_id, "steam", error_name, None, db)
                    debug_log(msg)

            update_log["last_request_to_steam"] = get_datetime_str()
            continue

        update_log["last_request_to_steam"] = get_datetime_str()

        if steam_response["success"]:
            steam_data = steam_response["data"]
            # Check if app is a game
            if steam_data["type"] != "game":
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
                    db.execute("DELETE FROM failed_requests WHERE app_id == ?", (app_id, ))

                output["fixed"] += 1
        else:
            with Connection(APPS_DB_PATH) as db:
                insert_failed_request(app_id, "steam", "failed", None, db)
            continue

    print("\nFinished...")
    print(f"Fixed Apps : {fixed_apps}")
    update_logger.save()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
