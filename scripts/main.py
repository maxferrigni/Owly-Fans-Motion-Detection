# File: main.py
# Purpose:
# This script serves as the main controller for the motion detection system.
# It coordinates motion detection across configured cameras and ensures all detection logs are sent to Supabase.
# Features:
# - Loads camera configurations.
# - Handles command-line arguments for operational modes (e.g., darkness only).
# - Runs the motion detection workflow and pushes logs to Supabase.
# - Ensures real-time logging without local storage.
# - Implements error handling to prevent system crashes.
# Typical Usage:
# Run this script to initiate motion detection:
# `python main.py --darkness` (to run during darkness only) or `python main.py` (to run always).

import argparse
import time as sleep_time

# Local imports
from utilities.logging_utils import append_to_local_log, log_event
from utilities.configs_loader import load_camera_config
from utilities.time_utils import is_within_allowed_hours
from scripts.motion_workflow import process_camera
from scripts.push_to_supabase import push_log_to_supabase, format_log_entry

# Load configurations
CAMERA_CONFIGS = load_camera_config()

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Motion Detection Script")
parser.add_argument("--darkness", action="store_true", help="Run the script during darkness only")
args = parser.parse_args()
RUN_IN_DARKNESS_ONLY = args.darkness

def motion_detection():
    """
    Perform motion detection for all configured cameras and push logs to Supabase.
    """
    print("Starting motion detection...")

    while True:
        if RUN_IN_DARKNESS_ONLY and not is_within_allowed_hours():
            print("Outside of allowed hours. Waiting...")
            sleep_time.sleep(60)
            continue

        for camera_name, config in CAMERA_CONFIGS.items():
            try:
                # Process camera detection
                detection_result = process_camera(camera_name, config)

                # Format detection log for Supabase
                log_entry = format_log_entry(
                    owl_in_box=detection_result.get("owl_in_box", False),
                    pixel_change_owl_in_box=detection_result.get("pixel_change_owl_in_box", 0.0),
                    luminance_change_owl_in_box=detection_result.get("luminance_change_owl_in_box", 0.0),
                    owl_in_box_url=detection_result.get("owl_in_box_url", ""),
                    owl_in_box_image_comparison_url=detection_result.get("owl_in_box_image_comparison_url", ""),
                    
                    owl_on_box=detection_result.get("owl_on_box", False),
                    pixel_change_owl_on_box=detection_result.get("pixel_change_owl_on_box", 0.0),
                    luminance_change_owl_on_box=detection_result.get("luminance_change_owl_on_box", 0.0),
                    owl_on_box_image_url=detection_result.get("owl_on_box_image_url", ""),
                    owl_on_box_image_comparison_url=detection_result.get("owl_on_box_image_comparison_url", ""),
                    
                    owl_in_area=detection_result.get("owl_in_area", False),
                    pixel_change_owl_in_area=detection_result.get("pixel_change_owl_in_area", 0.0),
                    luminance_change_owl_in_area=detection_result.get("luminance_change_owl_in_area", 0.0),
                    owl_in_area_image_url=detection_result.get("owl_in_area_image_url", ""),
                    owl_in_area_image_comparison_url=detection_result.get("owl_in_area_image_comparison_url", ""),
                )

                # Push log entry to Supabase
                push_log_to_supabase(log_entry)

            except Exception as e:
                print(f"Error processing {camera_name}: {e}")

        sleep_time.sleep(60)  # Capture images every minute

if __name__ == "__main__":
    motion_detection()