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
from errors import FetchError, RequestTimeoutError
from appdata import AppDetails
from update import (
    fetch, fetchProxy, RATE_LIMIT, UPDATE_LOG_PATH,
    STEAM_APP_DETAILS_API_BASE, STEAMSPY_APP_DETAILS_API_BASE,
    map_steam_data, map_steamspy_response, get_min_owner_count,
    OWNER_LIMIT, get_datetime_str, debug_log

)
from database import (
    APPS_DB_PATH, Connection,
    get_failed_requests, get_non_game_apps,
    insert_failed_request, insert_non_game_app,
    insert_app_over_million, insert_app,
    get_applist, handle_steam_response
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
DUPLICATION_PATH = os.path.join(DIAGNOSIS_DIR + "/apps_with_duplication.json")

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
            try:
                fix()
            except KeyboardInterrupt:
                print("\n")

        elif ARGS[1] == "fix-duplicate":
            # Create log file if it doesnt exists
            if not os.path.exists(DUPLICATION_PATH):
                default_log = {"index": 0, "applist": []}
                save_json(default_log, DUPLICATION_PATH)

            duplication_log = load_json(DUPLICATION_PATH)
            duplication_log["applist"] = set(duplication_log["applist"])
            try:
                with Connection(APPS_DB_PATH) as db:
                    fix_duplicate(duplication_log, db)
            except KeyboardInterrupt:
                pass
            except Exception as e:
                print("\n\n", traceback.format_exc())

            print(f"Saving apps with duplication at: '{DUPLICATION_PATH}'")
            duplication_log["applist"] = list(duplication_log["applist"])
            save_json(duplication_log, DUPLICATION_PATH)
            print("Total Apps with Duplication: ", len(duplication_log["applist"]))
            print("Finished!\n")

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

    print("Saving failed requests...")
    save_json(failed_requests, FAILED_REQUESTS_PATH)

    print("Saving non-game apps...")
    save_json(non_game_apps, NON_GAME_APPS_API)


def merge():
    print("Reading failed requests...")

    if not os.path.exists(FAILED_REQUESTS_PATH):
        print("File not found! Skipping failed requests...")
        return

    failed_size = os.path.getsize(FAILED_REQUESTS_PATH)
    if failed_size == 0:
        print(f"{FAILED_REQUESTS_PATH} is empty!\nSkipping...")
    else:
        failed_requests = load_json(FAILED_REQUESTS_PATH)

        print("Saving failed requests:")
        with Connection(APPS_DB_PATH) as db:
            for i, request in enumerate(failed_requests):
                print(f"Progress: {i:,}", end="\r")
                try:
                    insert_failed_request(request["app_id"], request["api_provider"], request["error"], request["status_code"], db)
                except KeyError:
                    insert_failed_request(request["app_id"], request["api_provider"], request["cause"], request["status_code"], db)

        print("\nCompleted!")

    print("Reading non-game apps...")
    if os.path.exists(NON_GAME_APPS_PATH):
        non_game_size = os.path.getsize(NON_GAME_APPS_PATH)
        if non_game_size == 0:
            print(f"{NON_GAME_APPS_PATH} is empty!\nSkipping...")
        else:
            non_game_apps = load_json(NON_GAME_APPS_PATH)

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


def fix_duplicate(duplication_log, db):
    # duplication["applist"] is a set
    applist_query = db.execute("SELECT app_id FROM apps").fetchall()
    applist = [i[0] for i in applist_query]
    applist = applist[duplication_log["index"]:]
    total_iteration = len(applist) - 1
    duplication = 0

    print("Starting from index: ", duplication_log["index"])

    for iteration, appid in enumerate(applist):
        print(f"Progress: {iteration:,} / {total_iteration:,} | Apps With Duplication: {duplication:,}", end="\r")
        duplication_log["index"] += 1

        tag_query = db.execute("""
            SELECT tag_id
            FROM apps_tags
            WHERE app_id = ?
            GROUP BY tag_id
            HAVING COUNT(*) > 1
            """, (appid, )).fetchall()

        tags = [i[0] for i in tag_query]

        if not tags:
            continue

        duplication += 1
        duplication_log["applist"].add(appid)

        # Delete duplicates
        for tag_id in tags:
            db.execute("""
                DELETE FROM apps_tags
                WHERE app_id = ? AND tag_id = ?
                """, (appid, tag_id))

    print(f"\nDeleted {duplication:,} tag sections.")


def save_json(data, path):
    with open(path, "w") as f:
        json.dump(data, f)


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def fix():
    with Connection(APPS_DB_PATH) as db:
        failed_requests = get_failed_requests("WHERE error != 'failed'", db)

    failed_length = len(failed_requests)
    fixed_apps = 0

    print("Refetching Failed Requests...")
    for i, row in enumerate(failed_requests):
        print(f"Progress: {i + 1:,} / {failed_length} | Fixed: {fixed_apps}", end="\r")

        app_id = row["app_id"]

        time.sleep(RATE_LIMIT)

        # Create Appdetails
        app_details = AppDetails({"app_id": app_id})

        # FETCH FROM STEAMSPY
        steamspy_data = fetchProxy("steamspy", app_id)
        if steamspy_data is None:
            continue

        # Check minimum owner count to eliminate games over a million owners
        min_owner_count = get_min_owner_count(steamspy_data)

        if min_owner_count > OWNER_LIMIT:
            with Connection(APPS_DB_PATH) as db:
                insert_app_over_million(app_id, db)
                update_log["apps_over_million"] += 1
            continue

        # Update app info
        app_details_from_steamspy = map_steamspy_response(steamspy_data)
        app_details.update(app_details_from_steamspy)
        app_details.update({"name": steamspy_data["name"]})

        # FETCH FROM STEAM
        steam_response = fetchProxy("steam", app_id)
        update_log["last_request_to_steam"] = get_datetime_str()
        if steam_response is None:
            continue

        result = handle_steam_response(app_id, steam_response, app_details)
        if result == "updated":
            fixed_apps += 1

    print("\nFinished...")
    print(f"Fixed Apps : {fixed_apps}\n")
    update_logger.save()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
