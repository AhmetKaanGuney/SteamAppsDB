"""
Diagnostics tool for apps database
Usage: diagnostics.py [action]
Actions:
freeze      : Writes non_game_apps and failed_requests to files
merge       : saves diagnosis files to database
pull        : fetches diagnosis data from remote server and stores into apps.db
split       : splits db in to small files and stores inside split_db
join        : joins files in the split_db into apps.db file
"""
import os
import sys
import json

from update import fetch
from errors import FetchError
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

DIAGNOSIS_DIR = os.path.join(current_dir, "diagnosis")
FAILED_REQUESTS_PATH = os.path.join(current_dir, "diagnosis/failed_request.json")
NON_GAME_APPS_PATH = os.path.join(current_dir, "diagnosis/non_game_apps.json")
SPLIT_DIR = os.path.join(current_dir, "db_split")


STEAM_APP_DETAILS_API_BASE = "https://store.steampowered.com/api/appdetails/?appids="
STEAMSPY_APP_DETAILS_API_BASE = "https://steamspy.com/api.php?request=appdetails&appid="


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
        elif ARGS[1] == "split":
            split_db()
            exit(0)
        elif ARGS[1] == "join":
            join_db()
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
                insert_failed_request(request["app_id"], request["api_provider"], request["error"], request["status_code"], db)
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
                i["app_id"], i["api_provider"], i["error"], i["status_code"], db
            )


def split_db():
    if os.path.exists(SPLIT_DIR):
        for i in os.listdir(SPLIT_DIR):
            fp = os.path.join(SPLIT_DIR, i)
            os.remove(fp)
    else:
        os.mkdir(SPLIT_DIR)

    MB = 1024 * 1024
    chunk_size = 90 * MB
    file_number = 0

    with open(APPS_DB_PATH, "rb") as db_file:
        chunk = db_file.read(chunk_size)

        i = 0
        while chunk:
            print(f"Iteration: {i}", end="\r")

            file_path = os.path.join(SPLIT_DIR, str(file_number))

            with open(file_path, "wb") as chunk_file:
                chunk_file.write(chunk)

            file_number += 1
            chunk = db_file.read(chunk_size)
            i += 1

        print("\nCompleted!")


def join_db():
    # reset file
    open(APPS_DB_PATH, "wb").close()

    for i in os.listdir(SPLIT_DIR):
        print(f"Progress: {i}", end="\r")
        fp = os.path.join(SPLIT_DIR, i)

        with open(fp, "rb") as chunk_file:
            batch = chunk_file.read()
        with open(APPS_DB_PATH, "ab") as join_file:
            join_file.write(batch)

        os.remove(fp)

    print("\nCompleted!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
