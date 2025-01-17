
# File: main.py
# Purpose:
# This is the main controller script for the motion detection system.
# It coordinates motion detection across configured cameras by:
# - Loading camera configurations.
# - Handling command-line arguments for operational modes (e.g., darkness only).
# - Running the motion detection workflow in a loop, checking each camera.
# Typical Usage:
# Run this script to initiate motion detection, optionally restricting it to "darkness only" mode:
# `python main.py --darkness` (to run during darkness only) or `python main.py` (to run always).

import argparse
import time as sleep_time
from scripts.motion_workflow import process_camera
from utilities.configs_loader import load_camera_config
from utilities.time_utils import is_within_allowed_hours

# Load configurations
CAMERA_CONFIGS = load_camera_config()

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Motion Detection Script")
parser.add_argument("--darkness", action="store_true", help="Run the script during darkness only")
args = parser.parse_args()
RUN_IN_DARKNESS_ONLY = args.darkness

def motion_detection():
    """
    Perform motion detection for all configured cameras.
    """
    print("Starting motion detection...")
    while True:
        if RUN_IN_DARKNESS_ONLY and not is_within_allowed_hours():
            print("Outside of allowed hours. Waiting...")
            sleep_time.sleep(60)
            continue

        for camera_name, config in CAMERA_CONFIGS.items():
            process_camera(camera_name, config)

        sleep_time.sleep(60)  # Capture images every minute

if __name__ == "__main__":
    motion_detection()
