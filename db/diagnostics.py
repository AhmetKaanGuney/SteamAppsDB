if __name__ == "__main__":
    from database import (
        APPS_DB_PATH, Connection,
        get_failed_requests, get_non_game_apps
    )

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

    print(f"Non-Game Apps: {len(non_game_apps)}")

    print()
