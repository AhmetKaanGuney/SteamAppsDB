"""Initialize sqlite database"""
import sqlite3
import os

from database import Connection, DATABASE_PATH

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)

# Initialize databa with init.sql file
init_script = os.path.join(current_dir, "init.sql")

def main():
    print(f"Initializing database at '{init_script}'...")

    # Get file content
    with open(init_script) as f:
        script_as_str = f.read()

    # Execute
    with Connection(DATABASE_PATH) as db:
        db.executescript(script_as_str)

    print("Initialisation successful!")


if __name__ == "__main__":
    main()