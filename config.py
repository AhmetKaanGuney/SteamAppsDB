import json

with open("../env.json") as f:
    ENV = json.load(f)

SECRET_KEY = ENV["SECRET_KEY"]