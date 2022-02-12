"""Manages update_log"""
import json

class UpdateLogger:
    """On init loads file.
    On update: updates dictionary key with new value
    then writes log to file"""

    def __init__(self, file: str):
        self.file = file
        self.log = self._load_file()
        if self.log["reset_log"]:
            print("Resetting log!")
            self._reset_log()

    def _load_file(self) -> dict:
        with open(self.file, "r") as f:
            try:
                log = json.load(f)
            except json.JSONDecodeError:
                print("Cannot decode json file:\n", f.readlines())
                log = {}
        return log

    def save(self):
        with open(self.file, "w") as f:
            json.dump(self.log, f, indent=2)


    def _reset_log(self):
        self.log = {
            "reset_log": False,
            "last_request_to_steam": "",
            "steam_request_count": 0,
            "steam_request_limit_reached": False,
            "applist_length": 0,
            "applist_fetched": False,
            "updated_apps": 0,
            "non_game_apps": 0,
            "applist_index": 0,
            "rejected_apps": []
        }
        self.save()
