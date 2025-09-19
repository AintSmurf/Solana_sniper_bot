import os
import json
from datetime import datetime




def convert_blocktime_to_readable_format(blocktime):
    readble_fomrat = datetime.fromtimestamp(blocktime).strftime('%H:%M:%S')
    return readble_fomrat

def get_the_dif_between_unix_timestamps(current_time, unix_timestamp):
    return current_time - unix_timestamp
    
def get_payload(file) -> json:
    path = os.path.join(os.path.dirname(__file__), "..", "data", f"{file}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
