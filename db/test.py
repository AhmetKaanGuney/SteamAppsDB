import os
# a = {"key": "value"}
# refence_to_a = a
# b = refence_to_a

# refence_to_a["key"] = "different_value"
# b["key"] = "much_more_different_value"
# print("a: ", a)
# print("reference_to_a: ", refence_to_a)
# print("b: ", b)

# import datetime

# today = datetime.datetime.utcnow()
# tomorrow = today + datetime.timedelta(days=1)
# yesterday = today + datetime.timedelta(days=-1)
# print("today: ", today)
# print("tomorrow: ", tomorrow)
# print("yesterday: ", yesterday)
# print("today > tomorrow: ", today > tomorrow)
# print("yesterday > today: ", yesterday > today)

# Dirs
# current_dir = os.getcwd()
# parent_dir = os.path.dirname(current_dir)

# print("FILE : ", __file__)
# print("DIR NAME : ", os.path.dirname(__file__))

import json
import datetime

with open("./app_details.json") as f:
    apps = json.load(f)


apps_coming_soon = {}
apps_filtered = {}
for appid in apps:
    if not apps[appid]["release_date"]["coming_soon"]:
        apps_filtered[appid] = {
            "release_date": apps[appid]["release_date"]["date"]
        }

# apps_json = json.dumps(apps_coming_soon, indent=2)
# print(apps_json)

for app_id in apps_filtered:
    release_date = apps_filtered[app_id]["release_date"]
    release_date = release_date.replace(",", "")
    rd = release_date.split(" ")

    months = {
        "Jan": "01",
        "Feb": "02",
        "Mar": "03",
        "Apr": "04",
        "May": "05",
        "Jun": "06",
        "Jul": "07",
        "Aug": "08",
        "Sep": "09",
        "Oct": "10",
        "Nov": "11",
        "Dec": "12",
    }
    formatted_date = rd[2] + "-" + months[rd[1]] + "-" + rd[0]
    print(release_date)
    print(formatted_date)
    print("---")
