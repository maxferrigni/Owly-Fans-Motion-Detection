# File: scripts/motion_workflow.py
# Purpose: Handle motion detection with adaptive lighting conditions

import os
import time
from datetime import datetime
from PIL import Image
import pyautogui
import pytz
import numpy as np

# Import utilities
from utilities.constants import (
    BASE_IMAGES_DIR,
    TEMP_BASE_IMAGES_DIR,
    get_comparison_image_path,
    CAMERA_MAPPINGS,
    get_archive_comparison_path
)
from utilities.logging_utils import get_logger
from utilities.time_utils import (
    get_current_lighting_condition,
    should_capture_base_image,
    get_luminance_threshold_multiplier
)
from utilities.owl_detection_utils import detect_owl_in_box
from utilities.image_comparison_utils import create_comparison_image
from utilities.alert_manager import AlertManager
from capture_base_images import capture_base_images, get_latest_base_image

# Import from push_to_supabase
from push_to_supabase import push_log_to_supabase, format_detection_results

# Initialize logger and alert manager
logger = get_logger()
alert_manager = AlertManager()

# Set timezone
PACIFIC_TIME = pytz.timezone("America/Los_Angeles")

def initialize_system(camera_configs, is_test=False):
    """Initialize the motion detection system."""
    try:
        logger.info(f"Initializing motion detection system (Test Mode: {is_test})")
        
        # Verify camera configurations
        if not camera_configs:
            logger.error("No camera configurations provided")
            return False
            
        # Check for required ROIs
        for camera_name, config in camera_configs.items():
            if "roi" not in config or not config["roi"]:
                logger.error(f"Missing ROI configuration for {camera_name}")
                return False
                
        # Verify base images directory based on local saving setting
        local_saving = os.getenv('OWL_LOCAL_SAVING', 'True').lower() == 'true'
        logger.info(f"Local image saving is {'enabled' if local_saving else 'disabled'}")
        
        if not is_test:
            check_dir = BASE_IMAGES_DIR if local_saving else TEMP_BASE_IMAGES_DIR
            if not os.path.exists(check_dir):
                os.makedirs(check_dir, exist_ok=True)
                logger.info(f"Created base images directory: {check_dir}")
            
        logger.info("Motion detection system initialization complete")
        return True
        
    except Exception as e:
        logger.error(f"Error during motion detection system initialization: {e}")
        return False

def capture_real_image(roi):
    """Capture a screenshot of the specified region"""
    try:
        x, y, width, height = roi
        region = (x, y, width - x, height - y)
        logger.debug(f"Capturing screenshot with ROI: {region}")
        screenshot = pyautogui.screenshot(region=region)
        return screenshot.convert("RGB")
    except Exception as e:
        logger.error(f"Error capturing screenshot: {e}")
        raise

def process_camera(camera_name, config, lighting_info=None, test_images=None):
    """Process motion detection for a specific camera"""
    try:
        logger.info(f"Processing camera: {camera_name} {'(Test Mode)' if test_images else ''}")
        
        # Get or use provided lighting condition
        if lighting_info is None:
            lighting_condition = get_current_lighting_condition()
            threshold_multiplier = get_luminance_threshold_multiplier()
        else:
            lighting_condition = lighting_info['condition']
            threshold_multiplier = lighting_info['threshold_multiplier']
            
        logger.info(f"Current lighting condition: {lighting_condition}")
        
        # Get base image path and age
        base_image_age = 0
        if test_images:
            base_image = test_images['base']
            new_image = test_images['test']
            is_test = True
        else:
            # Get base image path first
            base_image_path = get_latest_base_image(camera_name, lighting_condition)
            logger.info(f"Using base image: {base_image_path}")
            
            # Calculate base image age from the file
            try:
                base_image_age = int(time.time() - os.path.getctime(base_image_path))
            except Exception as e:
                logger.warning(f"Could not determine base image age: {e}")
            
            # Load the base image
            base_image = Image.open(base_image_path).convert("RGB")
            new_image = capture_real_image(config["roi"])
            is_test = False

        # Initialize detection results
        detection_results = {
            "camera": camera_name,
            "is_test": is_test
        }
        
        # Get camera type
        alert_type = CAMERA_MAPPINGS[camera_name]
        
        # Process based on camera type
        detection_info = None
        if alert_type == "Owl In Box":
            is_owl_present, detection_info = detect_owl_in_box(
                new_image, 
                base_image,
                config,
                is_test=is_test
            )
            if is_owl_present:
                comparison_path = create_comparison_image(
                    base_image, 
                    new_image,
                    camera_name=alert_type,
                    threshold=config["luminance_threshold"] * threshold_multiplier,
                    config=config,
                    is_test=is_test
                )
                if detection_info:
                    detection_info["comparison_path"] = comparison_path
                detection_results["status"] = "Owl In Box"
        else:
            comparison_path = create_comparison_image(
                base_image, 
                new_image,
                camera_name=alert_type,
                threshold=config["luminance_threshold"] * threshold_multiplier,
                config=config,
                is_test=is_test
            )
            
            if comparison_path:
                detection_info = {
                    "motion_detected": True,
                    "comparison_path": comparison_path
                }
                detection_results["status"] = alert_type

        # Format metrics for database
        if detection_info:
            detection_results.update({
                "pixel_change": detection_info.get("pixel_change", 0.0),
                "luminance_change": detection_info.get("luminance_change", 0.0),
                "comparison_path": detection_info.get("comparison_path", ""),
                "motion_detected": detection_info.get("motion_detected", False)
            })

        # Push to activity log
        formatted_results = format_detection_results(detection_results)
        log_entry = push_log_to_supabase(formatted_results, lighting_condition, base_image_age)

        if log_entry and detection_info and detection_info.get("motion_detected", False) and not is_test:
            # Process alert if motion was detected
            alert_manager.process_detection(
                camera_name,
                detection_results,
                log_entry.get("id")
            )

        return detection_results

    except Exception as e:
        logger.error(f"Error processing {camera_name}: {e}")
        return {
            "camera": camera_name,
            "status": "Error",
            "error_message": str(e),
            "is_test": is_test if 'is_test' in locals() else False
        }

def process_cameras(camera_configs, test_images=None):
    """Process all cameras in batch for efficient motion detection"""
    try:
        # Get lighting information once for all cameras
        lighting_condition = get_current_lighting_condition()
        threshold_multiplier = get_luminance_threshold_multiplier()
        
        lighting_info = {
            'condition': lighting_condition,
            'threshold_multiplier': threshold_multiplier
        }
        
        logger.info(f"Processing cameras under {lighting_condition} condition")
        
        # Only verify base images in real-time mode
        if not test_images:
            if should_capture_base_image():
                logger.info("Time to capture new base images")
                capture_base_images(lighting_condition, force_capture=True)
                time.sleep(3)  # Allow system to stabilize after capture
        
        # Process each camera with shared lighting info
        results = []
        for camera_name, config in camera_configs.items():
            try:
                camera_test_images = test_images.get(camera_name) if test_images else None
                result = process_camera(
                    camera_name, 
                    config, 
                    lighting_info,
                    test_images=camera_test_images
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing camera {camera_name}: {e}")
                results.append({
                    "camera": camera_name,
                    "status": "Error",
                    "error_message": str(e)
                })
        
        return results

    except Exception as e:
        logger.error(f"Error in camera processing cycle: {e}")
        raise

if __name__ == "__main__":
    # Test the motion detection
    try:
        from utilities.configs_loader import load_camera_config
        
        # Load test configuration
        test_configs = load_camera_config()
        
        # Initialize system
        if initialize_system(test_configs, is_test=True):
            # Run test detection cycle
            results = process_cameras(test_configs)
            logger.info("Test Results:", results)
    except Exception as e:
        logger.error(f"Motion detection test failed: {e}")
        raise