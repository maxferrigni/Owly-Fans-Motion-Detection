# File: logging_utils.py

import os
import csv
from datetime import datetime
import pytz

# Set timezone for logs
PACIFIC_TIME = pytz.timezone("America/Los_Angeles")

def append_to_local_log(log_file, camera_name, status, pixel_change=None, luminance_change=None):
    """
    Append a log entry to the local log file.
    Args:
        log_file (str): Path to the log file.
        camera_name (str): Name of the camera.
        status (str): Status message.
        pixel_change (str, optional): Percentage of pixel change.
        luminance_change (str, optional): Average luminance change.
    """
    now = datetime.now(PACIFIC_TIME)
    row = [
        now.strftime("%Y-%m-%d %H:%M:%S"),
        camera_name,
        status,
        pixel_change or "",
        luminance_change or "",
    ]

    # Create the log file with headers if it doesn't exist
    if not os.path.exists(log_file):
        with open(log_file, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "CameraName", "Status", "PixelChange", "LuminanceChange"])

    # Append the new row
    with open(log_file, "a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(row)

def log_event(log_folder, camera_name, status, pixel_change=None, luminance_change=None):
    """
    Log an event to a daily log file.
    Args:
        log_folder (str): Path to the folder where daily logs are stored.
        camera_name (str): Name of the camera.
        status (str): Status message.
        pixel_change (str, optional): Percentage of pixel change.
        luminance_change (str, optional): Average luminance change.
    """
    os.makedirs(log_folder, exist_ok=True)
    date_str = datetime.now(PACIFIC_TIME).strftime("%Y-%m-%d")
    log_file = os.path.join(log_folder, f"motion_log_{date_str}.txt")

    timestamp = datetime.now(PACIFIC_TIME).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp}|{camera_name}|{status}|{pixel_change or ''}|{luminance_change or ''}\n"

    with open(log_file, "a") as log:
        log.write(entry)

def merge_logs(local_log, repo_log):
    """
    Merge the local log into the repository log file.
    Args:
        local_log (str): Path to the local log file.
        repo_log (str): Path to the repository log file.
    """
    if not os.path.exists(local_log):
        print(f"Local log file not found: {local_log}")
        return

    # Create repo log if it doesn't exist
    if not os.path.exists(repo_log):
        with open(repo_log, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "CameraName", "Status", "PixelChange", "LuminanceChange"])

    # Append local log entries to the repo log
    with open(repo_log, "a", newline="") as repo_file, open(local_log, "r") as local_file:
        repo_writer = csv.writer(repo_file)
        local_reader = csv.reader(local_file)
        next(local_reader, None)  # Skip header in local log
        for row in local_reader:
            repo_writer.writerow(row)
