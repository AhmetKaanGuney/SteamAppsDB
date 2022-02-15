"""Initialize sqlite database"""
import sqlite3
import os
import sys

def main():
    current_dir = os.path.dirname(__file__)

    # Initialize databa with init.sql file
    init_apps_script = os.path.join(current_dir, "init_apps.sql")
    init_update_script = os.path.join(current_dir, "init_update.sql")

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
            print("Deleting 'update.db' ...")
            os.remove(os.path.join(current_dir, "update.db"))
        except FileNotFoundError:
            print("Cannot delete 'apps.db', because file doesn't exists.")
            print("Resuming initialisation...")

    # Get file content
    with open(init_apps_script) as apps_f:
        init_apps_script_as_str = apps_f.read()

    with open(init_update_script) as update_f:
        init_update_script_as_str = update_f.read()

    # Execute
    with Connection(APPS_DB_PATH) as db:
        print("Executing 'init_apps.sql' script...")
        db.executescript(init_apps_script_as_str)

    with Connection(UPDATE_DB_PATH) as db:
        print("Executing 'update.sql' script...")
        db.executescript(init_update_script_as_str)


if __name__ == "__main__":
    from database import Connection, APPS_DB_PATH, UPDATE_DB_PATH
    main()