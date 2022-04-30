import os
import sys
import json
import subprocess

from db.update_logger import DEFAULT_LOG
from db.database import APPS_DB_PATH

current_dir = os.path.dirname(__file__)
update_log_path = os.path.join(current_dir, "db/update_log.json")
venv_path = os.path.join(current_dir, "venv")

def init_update_log():
    with open(update_log_path, "w") as log_file:
        print("Initialising update_log file...")
        json.dump(DEFAULT_LOG, log_file, indent=2)


if __name__ == "__main__":
    reset = False
    args = sys.argv
    if len(args) == 2:
        if args[1] == "-r":
            reset = True

    print("---")

    if reset:
        print(f"Deleting {APPS_DB_PATH} ...")
        os.remove(APPS_DB_PATH)
        print(f"Deleting {update_log_path} ...")
        os.remove(update_log_path)

    # Execute db/__init__.py script
    init_file = os.path.join(current_dir, "db/__init__.py")
    print(f"Executing {init_file}")

    os.system("python " + init_file)

    print("---")

    # Create update_log
    print("Checking if update_log exists...")
    if os.path.exists(update_log_path):
        print("update_log found!")

        with open(update_log_path) as f:
            ulog = json.load(f)

        default_keys = DEFAULT_LOG.keys()
        ulog_keys = ulog.keys()

        for i in default_keys:
            if i not in ulog_keys:
                print("update_log is not up to date.")
                init_update_log()
                break
    else:
        init_update_log()
    print("---")

    print("Setup succesfull!")

