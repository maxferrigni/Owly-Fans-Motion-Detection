#log_to_local.py

import csv
from datetime import datetime
import os

# Local log path
LOCAL_LOG_PATH = "/path/to/local_owl_log.csv"  # Replace with actual path

# Function to get simulated data (replace with actual detection logic)
def get_owl_status():
    # Replace with actual detection logic
    return {"OwlInBox": "Yes", "OwlOnBox": "No", "OwlInArea": "Yes"}

# Append data to the local log
def append_to_local_log():
    status = get_owl_status()
    total_owls = sum(1 for value in status.values() if value == "Yes")
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status["OwlInBox"],
        status["OwlOnBox"],
        status["OwlInArea"],
        total_owls
    ]
    
    # Ensure file exists
    if not os.path.exists(LOCAL_LOG_PATH):
        with open(LOCAL_LOG_PATH, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "OwlInBox", "OwlOnBox", "OwlInArea", "TotalOwls"])

    # Append row to the file
    with open(LOCAL_LOG_PATH, "a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(row)

if __name__ == "__main__":
    append_to_local_log()
