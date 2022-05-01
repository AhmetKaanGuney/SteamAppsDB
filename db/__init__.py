"""Initialize sqlite database"""
import sqlite3
import os
import sys


def main():
    current_dir = os.path.dirname(__file__)

    # Initialize database with init.sql file
    init_apps_script = os.path.join(current_dir, "init_apps.sql")

    print(f"Initializing database at '{current_dir}'")

    reset_db = False
    # If script is called with '-r' delete db and recreate it
    if len(sys.argv) == 2:
        if sys.argv[1] == "-r":
            reset_db = True
        else:
            print(f"'{sys.argv[1]}' is not a valid argument. Use '-r' to reset the database.")
            exit(0)

    if reset_db:
        try:
            print("Deleting 'apps.db' ...")
            os.remove(os.path.join(current_dir, "apps.db"))
        except FileNotFoundError:
            print("Cannot delete 'apps.db', because file doesn't exists.")
            print("Resuming initialisation...")

    # Get file content
    with open(init_apps_script) as apps_f:
        init_apps_script_as_str = apps_f.read()

    # Execute
    with Connection(APPS_DB_PATH) as db:
        print("Executing 'init_apps.sql' script...")
        db.executescript(init_apps_script_as_str)


if __name__ == "__main__":
    from database import Connection, APPS_DB_PATH
    main()
