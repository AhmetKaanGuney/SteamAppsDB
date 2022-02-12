import os
import json

from db.update_logger import DEFAULT_LOG

current_dir = os.path.dirname(__file__)
env_path = os.path.join(current_dir, ".env")
update_log_path = os.path.join(current_dir, "db/update_log.json")

env_content = """\
SECRET_KEY =
SENDER_EMAIL =
PASSWORD =
RECEIVER_EMAIL =
SMTP_SERVER = "smtp.gmail.com"
PORT = 465"""

if __name__ == "__main__":
    # Create .env file
    print("Checking if env file exists...")
    if os.path.exists(env_path):
        print("env file found! Resuming...")
    else:
        with open(env_path, "w") as env_file:
            print("Creating env file...")
            env_file.write(env_content)

    print("---")

    # Execute db/__init__.py script
    init_file = os.path.join(current_dir, "db/__init__.py")
    os.system("python " + init_file)

    print("---")

    # Create update_log
    print("Checking if update_log exists...")
    if os.path.exists(update_log_path):
        print("update_log found! Resuming...")
    else:
        with open(update_log_path, "w") as log_file:
            print("Creating update_log file...")
            json.dump(DEFAULT_LOG, log_file, indent=2)
    print("---")

    print("Setup succesfull!\n")