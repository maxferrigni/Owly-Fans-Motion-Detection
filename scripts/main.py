# File: main.py
# Purpose: Main controller for the motion detection system

import time
import sys
import os

# Import utilities
from utilities.constants import (
    ensure_directories_exist,
    LOCAL_FILES_DIR,
    BASE_IMAGES_DIR,
    IMAGE_COMPARISONS_DIR,
    LOGS_DIR
)
from utilities.configs_loader import load_camera_config
from utilities.logging_utils import get_logger
from utilities.time_utils import get_current_lighting_condition

# Local imports
from motion_workflow import process_cameras, initialize_system
from push_to_supabase import push_log_to_supabase, format_log_entry
from capture_base_images import capture_base_images

# Set up logging
logger = get_logger()

def setup_system():
    """Initialize the system by ensuring directories exist and loading configs"""
    try:
        logger.info("Initializing system...")
        
        # Create base directory structure
        for directory in [LOCAL_FILES_DIR, BASE_IMAGES_DIR, IMAGE_COMPARISONS_DIR, LOGS_DIR]:
            if not os.path.exists(directory):
                logger.info(f"Creating directory: {directory}")
                os.makedirs(directory, exist_ok=True)
        
        # Create remaining directory structure
        ensure_directories_exist()
        
        # Load camera configurations
        CAMERA_CONFIGS = load_camera_config()
        logger.info("Camera configuration loaded successfully")
        
        return CAMERA_CONFIGS
        
    except Exception as e:
        logger.error(f"Error during system setup: {e}")
        return None

def format_detection_results(camera_results):
    """Format camera detection results for Supabase logging."""
    return format_log_entry(
        owl_in_box=(camera_results.get("status") == "Owl In Box"),
        pixel_change_owl_in_box=(camera_results.get("pixel_change", 0.0) 
                                if camera_results.get("status") == "Owl In Box" else 0.0),
        luminance_change_owl_in_box=(camera_results.get("luminance_change", 0.0) 
                                    if camera_results.get("status") == "Owl In Box" else 0.0),
        owl_in_box_url=(camera_results.get("snapshot_path", "") 
                       if camera_results.get("status") == "Owl In Box" else ""),
        owl_in_box_image_comparison_url="",
        
        owl_on_box=(camera_results.get("status") == "Owl On Box"),
        pixel_change_owl_on_box=(camera_results.get("pixel_change", 0.0) 
                                if camera_results.get("status") == "Owl On Box" else 0.0),
        luminance_change_owl_on_box=(camera_results.get("luminance_change", 0.0) 
                                    if camera_results.get("status") == "Owl On Box" else 0.0),
        owl_on_box_image_url=(camera_results.get("snapshot_path", "") 
                             if camera_results.get("status") == "Owl On Box" else ""),
        owl_on_box_image_comparison_url="",
        
        owl_in_area=(camera_results.get("status") == "Owl In Area"),
        pixel_change_owl_in_area=(camera_results.get("pixel_change", 0.0) 
                                 if camera_results.get("status") == "Owl In Area" else 0.0),
        luminance_change_owl_in_area=(camera_results.get("luminance_change", 0.0) 
                                     if camera_results.get("status") == "Owl In Area" else 0.0),
        owl_in_area_image_url=(camera_results.get("snapshot_path", "") 
                              if camera_results.get("status") == "Owl In Area" else ""),
        owl_in_area_image_comparison_url=""
    )

def motion_detection():
    """Perform motion detection for all configured cameras and push logs to Supabase."""
    try:
        # Initial system setup
        CAMERA_CONFIGS = setup_system()
        if not CAMERA_CONFIGS:
            logger.error("Failed to set up system")
            sys.exit(1)
            
        logger.info("System setup complete")
        
        # Initial delay for system stabilization
        logger.info("Waiting for system stabilization...")
        time.sleep(5)
        
        # Initialize motion detection system
        if not initialize_system(CAMERA_CONFIGS):
            logger.error("System initialization failed")
            sys.exit(1)
            
        logger.info("System initialization complete")
        
        # Get current lighting condition and force new base images
        lighting_condition = get_current_lighting_condition()
        logger.info(f"Current lighting condition: {lighting_condition}")
        
        logger.info("Capturing initial base images...")
        results = capture_base_images(lighting_condition, force_capture=True)
        
        # Verify base image capture
        if not all(result.get('status') == 'success' for result in results if 'status' in result):
            logger.error("Failed to capture initial base images")
            sys.exit(1)
            
        # Additional delay after base image capture
        logger.info("Waiting for base image stabilization...")
        time.sleep(3)
        
        logger.info("Starting motion detection...")

        # Main detection loop
        while True:
            try:
                # Process all cameras in one batch
                camera_results = process_cameras(CAMERA_CONFIGS)
                
                # Format and upload results for each camera
                for result in camera_results:
                    try:
                        # Format detection log for Supabase
                        log_entry = format_detection_results(result)
                        
                        # Push log entry to Supabase
                        push_log_to_supabase(log_entry)
                        
                    except Exception as e:
                        logger.error(f"Error processing results for camera {result.get('camera', 'unknown')}: {e}")

                # Wait before next iteration
                time.sleep(60)  # Capture images every minute

            except Exception as e:
                logger.error(f"Error in detection cycle: {e}")
                time.sleep(60)  # Still wait before retry

    except Exception as e:
        logger.error(f"Fatal error in motion detection: {e}")
        sys.exit(1)

if __name__ == "__main__":
    motion_detection()