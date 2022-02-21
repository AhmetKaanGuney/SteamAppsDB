import os
from dotenv import dotenv_values

current_dir = os.path.dirname(__file__)
# Config
env = dotenv_values(os.path.join(current_dir, ".env"))

SECRET_KEY = env["SECRET_KEY"]
