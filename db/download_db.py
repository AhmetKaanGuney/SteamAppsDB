"""Download and save non_game_apps and failed_requests"""
import os
try:
    from update import fetch
    from database import (
        insert_failed_request, insert_non_game_app,
        APPS_DB_PATH, Connection
        )
except ImportError:
    from .update import fetch
    from database import (
        insert_failed_request, insert_non_game_app,
        APPS_DB_PATH, Connection
        )

# Dirs
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)

SERVER_IP = "192.168.1.232"
PORT = "500"
NON_GAME_APPS_API = f"http://{SERVER_IP}:{PORT}/GetNonGameApps"
FAILED_REQUESTS_API = f"htttp://{SERVER_IP}:{PORT}/GetFailedRequests"

def main():
    print("===           Download to DB          ===")
    print("Fetching non_game_apps...")
    non_game_apps = fetch(NON_GAME_APPS_API)
    print(non_game_apps)
    print("Fetching failed_requests...")
    failed_requests = fetch(FAILED_REQUESTS_API)
    print(failed_requests)

    with Connection(APPS_DB_PATH) as db:
        print("Inserting non_game_apps...")
        for app_id in non_game_apps:
            insert_non_game_app(app_id, db)

        print("Inserting failed_requests...")
        for i in failed_requests:
            insert_failed_request(
                i["app_id"], i["api_provider"],
                i["cause"], i["status_code"], db
            )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
