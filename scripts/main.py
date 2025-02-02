# File: main.py
# Purpose: Main controller for the motion detection system

import time as sleep_time
import sys

# Import utilities
from utilities.constants import ensure_directories_exist
from utilities.configs_loader import load_camera_config
from utilities.logging_utils import get_logger

# Local imports
from motion_workflow import process_camera
from push_to_supabase import push_log_to_supabase, format_log_entry

# Set up logging
logger = get_logger()

def initialize_system():
    """Initialize the system by ensuring directories exist and loading configs"""
    try:
        logger.info("Initializing system...")
        ensure_directories_exist()
        CAMERA_CONFIGS = load_camera_config()
        logger.info("System initialization complete")
        return CAMERA_CONFIGS
    except Exception as e:
        logger.error(f"Error during system initialization: {e}")
        sys.exit(1)

def motion_detection():
    """
    Perform motion detection for all configured cameras and push logs to Supabase.
    """
    try:
        # Load configurations
        CAMERA_CONFIGS = initialize_system()
        logger.info("Starting motion detection...")

        while True:
            for camera_name, config in CAMERA_CONFIGS.items():
                try:
                    # Process camera detection
                    logger.info(f"Processing camera: {camera_name}")
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
                    logger.error(f"Error processing {camera_name}: {e}")

            sleep_time.sleep(60)  # Capture images every minute

    except Exception as e:
        logger.error(f"Fatal error in motion detection: {e}")
        sys.exit(1)

if __name__ == "__main__":
    motion_detection()