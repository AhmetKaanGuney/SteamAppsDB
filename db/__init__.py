"""Initialize sqlite database"""
import sqlite3
import os
import sys

from database import Connection, DATABASE_PATH

current_dir = os.path.dirname(__file__)

# Initialize databa with init.sql file
init_script = os.path.join(current_dir, "init.sql")

def main():
    print(f"Initializing database at '{init_script}'...")

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
            os.remove(os.path.join(current_dir, "apps.db"))
        except FileNotFoundError:
            print("Cannot delete 'apps.db', because file doesn't exists.")
            print("Resuming initialisation...")

    # Get file content
    with open(init_script) as f:
        script_as_str = f.read()

    # Execute
    with Connection(DATABASE_PATH) as db:
        print("Executing 'init.sql' script...")
        db.executescript(script_as_str)

    print("Initialisation successful!")


if __name__ == "__main__":
    main()