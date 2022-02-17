"""Diagnostics for apps.db"""


if __name__ == "__main__":
    import os
    import sys
    import json

    from database import (
        APPS_DB_PATH, Connection,
        get_failed_requests, get_non_game_apps
    )

    current_dir = os.path.dirname(__file__)
    diagnostic_folder = "diagnostics"
    FAILED_REQUESTS_PATH = os.path.join(current_dir, diagnostic_folder, "failed_request.json")
    NON_GAME_APPS_PATH = os.path.join(current_dir, diagnostic_folder, "non_game_apps.json")

    args = sys.argv
    write_to_json = False

    if len(args) == 2:
        if args[1] == "freeze":
            write_to_json = True

    if write_to_json is True:
        os.mkdir(os.path.join(current_dir, diagnostic_folder))
        with Connection(APPS_DB_PATH) as db:
            print("Loading failed requests...")
            failed_requests: list[dict] = get_failed_requests("", db)
            print("Loading non-game apps...")
            non_game_apps: list[int] = get_non_game_apps(db)

        print("Writing failed reqeusts...")
        with open(FAILED_REQUESTS_PATH, "w") as failed_file:
            json.dump(failed_requests, failed_file)

        print("Writing non=game apps...")
        with open(NON_GAME_APPS_PATH, "w") as non_game_file:
            json.dump(NON_GAME_APPS_PATH, non_game_file)

        exit(0)


    filter_failed = ""
    filter_failed = "WHERE cause == 'failed'"
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
        for i in non_game_apps:
            print(type(i))
            exit(0)

    print(f"Non-Game Apps: {len(non_game_apps)}")

    print()
