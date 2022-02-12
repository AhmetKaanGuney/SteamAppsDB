import os

current_dir = os.path.dirname(__file__)

env_content = """\
SECRET_KEY =
SENDER_EMAIL =
PASSWORD =
RECEIVER_EMAIL =
SMTP_SERVER = "smtp.gmail.com"
PORT = 465"""

if __name__ == "__main__":
    # Create .env file
    with open("./.env2", "w") as env_file:
        print("Creating .env file...")
        env_file.write(env_content)

    # Execute db/__init__.py script
    init_file = os.path.join(current_dir, "db/__init__.py")
    os.system("python " + init_file)

print("Setup succesfull!\n")