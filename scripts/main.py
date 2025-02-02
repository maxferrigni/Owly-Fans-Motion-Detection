# File: main.py
# Purpose:
# This script serves as the main controller for the motion detection system.
# It coordinates motion detection across configured cameras and ensures all detection logs are sent to Supabase.

import argparse
import time as sleep_time
import sys
import os

# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Local imports
from utilities.configs_loader import load_camera_config
from utilities.time_utils import is_within_allowed_hours
from motion_workflow import process_camera
from push_to_supabase import push_log_to_supabase, format_log_entry

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Motion Detection Script")
parser.add_argument("--darkness", action="store_true", help="Run the script during darkness only")
args = parser.parse_args()

def motion_detection():
    """
    Perform motion detection for all configured cameras and push logs to Supabase.
    """
    try:
        # Load configurations
        CAMERA_CONFIGS = load_camera_config()
        print("Starting motion detection...")

        while True:
            if args.darkness:
                is_dark = is_within_allowed_hours()
                if not is_dark:
                    print("Outside of allowed hours. Waiting...")
                    sleep_time.sleep(60)
                    continue

            for camera_name, config in CAMERA_CONFIGS.items():
                try:
                    # Process camera detection
                    detection_result = process_camera(camera_name, config)

                    # Format detection log for Supabase
                    log_entry = format_log_entry(
                        owl_in_box=detection_result.get("status") == "Owl In Box",
                        pixel_change_owl_in_box=detection_result.get("pixel_change", 0.0),
                        luminance_change_owl_in_box=detection_result.get("luminance_change", 0.0),
                        owl_in_box_url=detection_result.get("snapshot_path", ""),
                        owl_in_box_image_comparison_url="",
                        
                        owl_on_box=detection_result.get("status") == "Owl On Box",
                        pixel_change_owl_on_box=detection_result.get("pixel_change", 0.0),
                        luminance_change_owl_on_box=detection_result.get("luminance_change", 0.0),
                        owl_on_box_image_url=detection_result.get("snapshot_path", ""),
                        owl_on_box_image_comparison_url="",
                        
                        owl_in_area=detection_result.get("status") == "Owl In Area",
                        pixel_change_owl_in_area=detection_result.get("pixel_change", 0.0),
                        luminance_change_owl_in_area=detection_result.get("luminance_change", 0.0),
                        owl_in_area_image_url=detection_result.get("snapshot_path", ""),
                        owl_in_area_image_comparison_url=""
                    )

                    # Push log entry to Supabase
                    push_log_to_supabase(log_entry)

                except Exception as e:
                    print(f"Error processing {camera_name}: {e}")

            sleep_time.sleep(60)  # Capture images every minute

    except Exception as e:
        print(f"Fatal error in motion detection: {e}")
        sys.exit(1)

if __name__ == "__main__":
    motion_detection()