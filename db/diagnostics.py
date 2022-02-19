"""Diagnostics for apps.db"""
import os
import sys
import json

from database import (
    APPS_DB_PATH, Connection,
    get_failed_requests, get_non_game_apps,
    insert_failed_request, insert_non_game_app
)
current_dir = os.path.dirname(__file__)
diagnostic_folder = "diagnostics"
FAILED_REQUESTS_PATH = os.path.join(current_dir, diagnostic_folder, "failed_request.json")
NON_GAME_APPS_PATH = os.path.join(current_dir, diagnostic_folder, "non_game_apps.json")

args = sys.argv
write_to_json = False

def main():
    if len(args) == 2:
        if args[1] == "-h":
            print(f"Usage: {__name__} [action]")
            print("Actions: ")
            print("freeze : Writes non_game_apps and failed_requests to files")
            print("load-to-db : loads written files to database")
            print("")
            exit(0)
        if args[1] == "freeze":
            freeze()
            exit(0)
        if args[1] == "load-to-db":
            load_to_db()
            exit(0)

    if len(args) == 1:
        filter_failed = ""
        filter_failed = "WHERE cause != 'failed'"
        with Connection(APPS_DB_PATH) as db:
            failed_requests = db.execute(f"""
                SELECT app_id, api_provider, cause, status_code
                FROM failed_requests
                {filter_failed}
                """).fetchall()

        print(f"Failed Requests ({len(failed_requests)}): ")
        for i in failed_requests:
            print(f"AppID: {i[0]} | Provider: {i[1]} | Cause: {i[2]} | Status Code: {i[3]}")

        print()

        with Connection(APPS_DB_PATH) as db:
            non_game_apps = get_non_game_apps(db)

        print(f"Non-Game Apps: {len(non_game_apps):,}")
        print()


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


def load_to_db():
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
                insert_failed_request(r["app_id"], r["api_provider"], r["cause"], r["status_code"], db)
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


if __name__ == "__main__":
    main()



