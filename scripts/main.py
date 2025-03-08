# File: main.py
# Purpose: Main controller for the motion detection system
#
# March 7, 2025 Update - Version 1.4.1
# - Added tracking for initial base image capture to prevent redundant captures
# - Improved error handling and logging
# - Optimized startup sequence

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
from utilities.database_utils import ensure_required_tables_exist

# Local imports
from motion_workflow import process_cameras, initialize_system
from push_to_supabase import push_log_to_supabase
from capture_base_images import capture_base_images

# Import from push_to_supabase
from push_to_supabase import format_detection_results  # Changed to push_to_supabase

# Set up logging
logger = get_logger()

# Flag to track initial base image capture
initial_capture_completed = False

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
        
        # Ensure database tables exist with proper columns
        try:
            ensure_required_tables_exist()
        except Exception as db_error:
            logger.warning(f"Database initialization error (continuing anyway): {db_error}")
        
        # Load camera configurations
        CAMERA_CONFIGS = load_camera_config()
        logger.info("Camera configuration loaded successfully")
        
        return CAMERA_CONFIGS
        
    except Exception as e:
        logger.error(f"Error during system setup: {e}")
        sys.exit(1)

def motion_detection():
    """Main motion detection function"""
    global initial_capture_completed
    
    try:
        # Initialize system and load camera configurations
        CAMERA_CONFIGS = setup_system()
        
        # Initialize motion detection system
        if not initialize_system(CAMERA_CONFIGS):
            logger.error("Failed to initialize motion detection system")
            sys.exit(1)
            
        # Capture initial base images (only once)
        logger.info("Capturing initial base images...")
        initial_condition = get_current_lighting_condition()
        if not capture_base_images(initial_condition, force_capture=True):
            logger.error("Failed to capture initial base images")
            sys.exit(1)
            
        # Mark initial capture as completed to prevent redundant captures
        initial_capture_completed = True
            
        # Additional delay after base image capture
        logger.info("Waiting for base image stabilization...")
        time.sleep(3)
        
        # Get the capture interval from environment variable (default to 60 if not set)
        try:
            capture_interval = int(os.getenv('OWL_CAPTURE_INTERVAL', '60'))
            logger.info(f"Using capture interval of {capture_interval} seconds")
        except ValueError:
            logger.warning("Invalid capture interval value, defaulting to 60 seconds")
            capture_interval = 60
        
        logger.info("Starting motion detection...")

        # Main detection loop
        while True:
            try:
                # Process all cameras in one batch, passing the initial capture flag
                camera_results = process_cameras(CAMERA_CONFIGS, initial_capture=initial_capture_completed)
                
                # Format and upload results for each camera
                for result in camera_results:
                    try:
                        # Format detection log for Supabase
                        log_entry = format_detection_results(result)
                        
                        # Push log entry to Supabase
                        push_log_to_supabase(log_entry)
                        
                    except Exception as e:
                        logger.error(f"Error processing results for camera {result.get('camera', 'unknown')}: {e}")

                # Wait before next iteration using the configured interval
                logger.debug(f"Waiting {capture_interval} seconds for next detection cycle")
                time.sleep(capture_interval)

            except Exception as e:
                logger.error(f"Error in detection cycle: {e}")
                time.sleep(capture_interval)  # Still wait before retry

    except Exception as e:
        logger.error(f"Fatal error in motion detection: {e}")
        sys.exit(1)

if __name__ == "__main__":
    motion_detection()