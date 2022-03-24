"""
Diagnostics tool for apps database
Usage: diagnostics.py [action]
Actions:
status  : Shows db status
freeze  : Writes non_game_apps and failed_requests to files
merge   : saves diagnosis files to database
pull    : fetches diagnosis data from remote server and stores into apps.db
get-app [<app_id: int>]  : returns data about app
update [failed-requests || duplication] : updates specified apps
delete-duplicates:  detects duplicate rows for tags, genres and categories
                    then deletes all duplicate rows in apps_tags, apps_genres,
                    apps_categories
"""
import os
import sys
import json
import time
import traceback

from update_logger import UpdateLogger
from errors import FetchError, RequestTimeoutError
from appdata import AppDetails, AppSnippet
from update import (
    fetch, fetchProxy, RATE_LIMIT, UPDATE_LOG_PATH,
    STEAM_APP_DETAILS_API_BASE, STEAMSPY_APP_DETAILS_API_BASE,
    map_steam_data, map_steamspy_response, get_min_owner_count,
    OWNER_LIMIT, get_datetime_str, debug_log, handle_steam_response

)
from database import (
    APPS_DB_PATH, Connection,
    get_failed_requests, get_non_game_apps,
    insert_failed_request, insert_non_game_app,
    insert_app_over_million, insert_app,
    get_applist, get_tags, get_genres, get_categories
)

args = sys.argv

current_dir = os.path.dirname(__file__)
write_to_json = False

SERVER_IP = "192.168.1.119"
PORT = "5000"
NON_GAME_APPS_API = f"http://{SERVER_IP}:{PORT}/GetNonGameApps"
FAILED_REQUESTS_API = f"http://{SERVER_IP}:{PORT}/GetFailedRequests"

DIAGNOSIS_DIR = os.path.join(current_dir, "diagnosis")
FAILED_REQUESTS_PATH = os.path.join(current_dir, "diagnosis/failed_requests.json")
NON_GAME_APPS_PATH = os.path.join(current_dir, "diagnosis/non_game_apps.json")
APPS_WITH_DUPLICATION_PATH = os.path.join(DIAGNOSIS_DIR + "/apps_with_duplication.json")

update_logger = UpdateLogger(UPDATE_LOG_PATH)
update_log = update_logger.log


def main():
    if len(args) == 2:
        if args[1] == "-h":
            print(__doc__)
            exit(0)
        elif args[1] == "status":
            status()
        elif args[1] == "freeze":
            freeze()
        elif args[1] == "merge":
            merge()
        elif args[1] == "pull":
            pull()
        elif args[1] == "delete-duplicates":
            # Create log file if it doesnt exists
            if not os.path.exists(APPS_WITH_DUPLICATION_PATH):
                default_log = {"index": 0, "applist": []}
                save_json(default_log, APPS_WITH_DUPLICATION_PATH)

            duplication_log = load_json(APPS_WITH_DUPLICATION_PATH)
            duplication_log["applist"] = set(duplication_log["applist"])
            try:
                with Connection(APPS_DB_PATH) as db:
                    delete_duplicates(duplication_log, db)
            except KeyboardInterrupt:
                print("\n")
            except Exception as e:
                print("\n\n", traceback.format_exc())

            print(f"Saving duplication_log...")
            duplication_log["applist"] = list(duplication_log["applist"])
            save_json(duplication_log, APPS_WITH_DUPLICATION_PATH)

            print("Total Apps with Duplication: ", len(duplication_log["applist"]))
            print("Finished!\n")
            exit(0)
        else:
            print(__doc__)
            exit(0)
    elif len(args) == 3:
        if args[1] == "get-app":
            app_id = args[2]
            get_app(app_id)

        elif args[1] == "update":
            updated_list = []
            if args[2] == "failed-requests":
                with Connection(APPS_DB_PATH) as db:
                    failed_requests = get_failed_requests("WHERE error != 'failed'", db)
                    applist = [i["app_id"] for i in failed_requests]

            elif args[2] == "duplication":
                duplication_log = load_json(APPS_WITH_DUPLICATION_PATH)

                if not duplication_log:
                    print("Error: ", APPS_WITH_DUPLICATION_PATH, " is empty!\n")
                    exit(0)

                applist = duplication_log["applist"]
            else:
                print("Try: [update failed-requests], [update duplication]")
                exit(0)
            try:
                update_apps(applist, updated_list)
            except KeyboardInterrupt:
                print("\n")
            finally:
                # Update logs and db
                if args[2] == "failed-requests":
                    print("Deleting updated apps from failed_requests...")
                    updated_length = len(updated_list)
                    for i, app_id in enumerate(updated_list):
                        print(f"Progress: {i:,} / {updated_length:,}", end="\r")
                        with Connection(APPS_DB_PATH) as db:
                            delete_row(app_id, "", "", "failed_requests", db)
                    print()

                elif args[2] == "duplication":
                    print("Deleting updated apps from duplication_log...")
                    duplication_log = load_json(APPS_WITH_DUPLICATION_PATH)
                    duplication_log["applist"] = list(
                        filter(lambda x: x not in updated_list, duplication_log["applist"])
                    )
                    save_json(duplication_log, APPS_WITH_DUPLICATION_PATH)

                print("Saving update_log...\n")
                update_logger.save()
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
    exit(0)


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
    exit(0)


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
    exit(0)


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
    exit(0)


def get_app(app_id):
    columns = ["name"]
    with Connection(APPS_DB_PATH) as db:
        app = db.execute(f"""
        SELECT {",".join(columns)}
        FROM apps WHERE app_id = ?""", (app_id, )).fetchall()[0]

        tags = get_tags(app_id, db)
        genres = get_genres(app_id, db)
        categories = get_categories(app_id, db)

    for i, value in enumerate(app):
        print(f"{columns[i]}: {value}")
        if not tags:
            tags = {}
        print(f"Tags        : ", [i["name"] for i in tags])
        print(f"Genres      : ", [i for i in genres])
        print(f"Categories  : ", [i for i in categories])
        print()
    exit(0)


def delete_duplicates(duplication_log, db):
    # duplication["applist"] is a set
    applist_query = db.execute("SELECT app_id FROM apps").fetchall()
    applist = [i[0] for i in applist_query]
    applist = applist[duplication_log["index"]:]
    total_iteration = len(applist)

    total_tags_deleted = 0
    total_genres_deleted = 0
    total_categories_deleted = 0

    print("Starting from index: ", duplication_log["index"])

    for iteration, app_id in enumerate(applist):
        print(f"Progress: {iteration + 1:,} / {total_iteration:,} | Apps With Duplication: {len(duplication_log['applist']):,}", end="\r")
        duplication_log["index"] += 1

        tags_deleted = delete_duplicate_rows(app_id, "tag_id", "apps_tags", db, duplication_log)
        total_tags_deleted += tags_deleted

        genres_deleted = delete_duplicate_rows(app_id, "genre_id", "apps_genres", db, duplication_log)
        total_genres_deleted += genres_deleted

        categories_deleted = delete_duplicate_rows(app_id, "category_id", "apps_categories", db, duplication_log)
        total_categories_deleted += categories_deleted


def delete_duplicate_rows(app_id, column, table, db, duplication_log):
    deleted_items = 0
    duplicates = get_duplicates(app_id, column, table, db)

    if not duplicates:
        return deleted_items

    for item_id in duplicates:
        delete_row(app_id, item_id, column, table, db)
        deleted_items += 1

    duplication_log["applist"].add(app_id)

    return deleted_items


def get_duplicates(app_id, column, table, db):
    query = db.execute(f"""
        SELECT {column}
        FROM {table}
        WHERE app_id = {app_id}
        GROUP BY {column}
        HAVING COUNT(*) > 1
        """).fetchall()
    return [i[0] for i in query]


def delete_row(app_id, item_id, column, table, db):
    condition = ""
    if column and item_id:
        condition = f"AND {column} = {item_id}"

    db.execute(f"""
        DELETE FROM {table}
        WHERE app_id = {app_id} {condition}
    """)


def save_json(data, path):
    with open(path, "w") as f:
        json.dump(data, f)


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def update_apps(applist, updated_list):
    applist_length = len(applist)
    updated_apps = 0

    print("Updating...")
    for i, app_id in enumerate(applist):
        print(f"Progress: {i:,} / {applist_length} | Updated: {updated_apps}", end="\r")

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
            # Remove app from failed requests
            updated_list.append(app_id)

            updated_apps += 1

    print("\nFinished...")
    print(f"Updated Apps : {updated_apps}\n")


if __name__ == "__main__":
    main()
