# File: scripts/motion_workflow.py
# Purpose: Handle motion detection with adaptive lighting conditions and confidence-based detection

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
    get_comparison_image_path,
    CAMERA_MAPPINGS,
    get_base_image_path  # Updated from get_base_image_filename
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
from utilities.confidence_utils import reset_frame_history
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
        
        # Reset frame history at startup
        reset_frame_history()
        
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
        if not os.path.exists(BASE_IMAGES_DIR):
            os.makedirs(BASE_IMAGES_DIR, exist_ok=True)
            logger.info(f"Created base images directory: {BASE_IMAGES_DIR}")
            
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
    """Process motion detection for a specific camera with confidence-based detection"""
    try:
        logger.info(f"Processing camera: {camera_name} {'(Test Mode)' if test_images else ''}")
        base_image = None
        new_image = None
        timestamp = datetime.now(PACIFIC_TIME)
        
        try:
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
                base_image_age = int(time.time() - os.path.getctime(base_image_path))
                logger.debug(f"Base image age: {base_image_age} seconds")
                
                # Load the images
                base_image = Image.open(base_image_path).convert("RGB")
                new_image = capture_real_image(config["roi"])
                is_test = False

            # Get camera type and initialize detection results
            alert_type = CAMERA_MAPPINGS[camera_name]
            detection_results = {
                "camera": camera_name,
                "is_test": is_test,
                "status": alert_type,  # Set default status to camera type
                "motion_detected": False,
                "pixel_change": 0.0,
                "luminance_change": 0.0,
                "timestamp": timestamp.isoformat(),
                "owl_confidence": 0.0,
                "consecutive_owl_frames": 0
            }
            
            logger.debug(f"Processing as {alert_type} type camera")
            
            # Run owl detection with confidence calculation
            is_owl_present, detection_info = detect_owl_in_box(
                new_image, 
                base_image,
                config,
                is_test=is_test,
                camera_name=camera_name  # Pass camera name for temporal confidence
            )
            
            # Always create comparison image with confidence data
            comparison_path = create_comparison_image(
                base_image, 
                new_image,
                camera_name,
                threshold=config["luminance_threshold"] * threshold_multiplier,
                config=config,
                detection_info=detection_info,  # Pass detection info with confidence
                is_test=is_test,
                timestamp=timestamp
            )
            
            # Update detection results with detection info
            detection_results.update({
                "status": alert_type,
                "motion_detected": is_owl_present,
                "is_owl_present": is_owl_present,
                "owl_confidence": detection_info.get("owl_confidence", 0.0),
                "consecutive_owl_frames": detection_info.get("consecutive_owl_frames", 0),
                "confidence_factors": detection_info.get("confidence_factors", {}),
                "comparison_path": comparison_path,
                "pixel_change": detection_info.get("pixel_change", 0.0),
                "luminance_change": detection_info.get("luminance_change", 0.0)
            })
            
            logger.info(
                f"Detection results for {camera_name}: Owl Present: {is_owl_present}, "
                f"Confidence: {detection_results['owl_confidence']:.1f}%, "
                f"Consecutive Frames: {detection_results['consecutive_owl_frames']}"
            )

            # Format the results for database
            formatted_results = format_detection_results(detection_results)
            
            # Only push to Supabase if motion was detected or in test mode
            if is_owl_present or is_test:
                log_entry = push_log_to_supabase(formatted_results, lighting_condition, base_image_age)
                
                # Process alert only if we have a successful log entry and owl was detected
                if log_entry and is_owl_present and not is_test:
                    alert_manager.process_detection(
                        camera_name,
                        detection_results,
                        log_entry.get("id")
                    )
            else:
                logger.debug(f"No owl detected for {camera_name}, skipping database push")

            return detection_results

        finally:
            # Clean up image objects
            if base_image and hasattr(base_image, 'close'):
                base_image.close()
            if new_image and hasattr(new_image, 'close'):
                new_image.close()

    except Exception as e:
        logger.error(f"Error processing {camera_name}: {e}")
        return {
            "camera": camera_name,
            "status": "Error",
            "error_message": str(e),
            "is_test": is_test if 'is_test' in locals() else False,
            "motion_detected": False,
            "is_owl_present": False,
            "owl_confidence": 0.0,
            "consecutive_owl_frames": 0,
            "confidence_factors": {},
            "pixel_change": 0.0,
            "luminance_change": 0.0,
            "timestamp": datetime.now(PACIFIC_TIME).isoformat()
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
                    "error_message": str(e),
                    "motion_detected": False,
                    "is_owl_present": False,
                    "owl_confidence": 0.0,
                    "consecutive_owl_frames": 0,
                    "confidence_factors": {},
                    "timestamp": datetime.now(PACIFIC_TIME).isoformat()
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
            logger.info(f"Test Results: {results}")
    except Exception as e:
        logger.error(f"Motion detection test failed: {e}")
        raise