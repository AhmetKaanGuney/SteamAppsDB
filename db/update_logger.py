"""Manages db_log"""
import json

class UpdateLogger:
    """On init loads file.
    On update: updates dictionary key with new value
    then writes log to file"""

    def __init__(self, file: str):
        self.file = file
        self.log = self._load_file()
        self.log.update(
            {
            "updated_apps": 0,
            "rejected_apps": []
            }
        )

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
            "lastest_request_to_steam": "",
            "failed_apps": []
        }
        self.save()
