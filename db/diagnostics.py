"""
Diagnostics tool for apps database
Usage: diagnostics.py [action]
Actions:
freeze      : Writes non_game_apps and failed_requests to files
merge       : saves diagnosis files to database
pull        : fetches diagnosis data from remote server and stores into apps.db
pull-old    : fetches diagnosis to db in old way
fix         : tries to refetch apps that failed
"""
import os
import sys
import json

from update import fetch
from database import (
    APPS_DB_PATH, Connection,
    get_failed_requests, get_non_game_apps,
    insert_failed_request, insert_non_game_app
)

ARGS = sys.argv

current_dir = os.path.dirname(__file__)
write_to_json = False

SERVER_IP = "192.168.1.119"
PORT = "5000"
NON_GAME_APPS_API = f"http://{SERVER_IP}:{PORT}/GetNonGameApps"
FAILED_REQUESTS_API = f"http://{SERVER_IP}:{PORT}/GetFailedRequests"

FAILED_REQUESTS_PATH = os.path.join(current_dir, "diagnosis/failed_request.json")
NON_GAME_APPS_PATH = os.path.join(current_dir, "diagnosis/non_game_apps.json")

STEAM_APP_DETAILS_API_BASE = "https://store.steampowered.com/api/appdetails/?appids="
STEAMSPY_APP_DETAILS_API_BASE = "https://steamspy.com/api.php?request=appdetails&appid="


def main():
    if len(ARGS) == 2:
        if ARGS[1] == "-h":
            print(__doc__)
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
        elif ARGS[1] == "pull-old":
            pull_old()
            exit(0)
        elif ARGS[1] == "status":
            where = "WHERE error != 'failed'"
            with Connection(APPS_DB_PATH) as db:
                failed_requests = get_failed_requests(where, db)

            print(f"Failed Requests ({len(failed_requests)}) - without 'failed': ")
            for i in failed_requests:
                print(f"Error: {i[0]} | Status Code: {i[1]} | URL: {i[2]}")

            print()

            with Connection(APPS_DB_PATH) as db:
                non_game_apps = get_non_game_apps(db)

            print(f"Non-Game Apps: {len(non_game_apps):,}")
            print()
    else:
        print(__doc__)
        exit(0)


def freeze():
    # Create dir if it doesnt exists
    diagnostic_folder_path = os.path.join(current_dir, diagnostic_folder)
    if not os.path.exists(diagnostic_folder_path):
        os.mkdir(diagnostic_folder_path)

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
    failed_size = os.path.getsize(FAILED_REQUESTS_PATH)
    if failed_size == 0:
        print(f"{FAILED_REQUESTS_PATH} is empty!\nSkipping...")
    else:
        with open(FAILED_REQUESTS_PATH, "r") as failed_file:
            failed_requests = json.load(failed_file)

        print("Saving failed requests:")
        with Connection(APPS_DB_PATH) as db:
            for i, r in enumerate(failed_requests):
                print(f"Progress: {i:,}", end="\r")
                insert_failed_request(r["error"], r["status_code"], r["url"], db)
        print("\nCompleted!")


    print("Reading non-game apps...")
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
                i["error"], i["status_code"], i["url"], db
            )


def pull_old():
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
            error = i["cause"]
            status_code = i["status_code"]
            url = ""
            if i["api_provider"] == "steam":
                url = STEAM_APP_DETAILS_API_BASE + str(i["app_id"])
            elif i["api_provider"] == "steamspy":
                url = STEAMSPY_APP_DETAILS_API_BASE + str(i["app_id"])
            insert_failed_request(
                error, status_code, url,  db
            )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
