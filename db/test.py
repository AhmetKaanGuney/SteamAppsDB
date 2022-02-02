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
current_dir = os.getcwd()
parent_dir = os.path.dirname(current_dir)

print("FILE : ", __file__)
print("DIR NAME : ", os.path.dirname(__file__))