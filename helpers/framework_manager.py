import os
import json


def convert_date_to_readable_format():
    pass


def get_payload(file) -> json:
    path = os.path.join(os.path.dirname(__file__), "..", "data", f"{file}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
