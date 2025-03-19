# File: scripts/motion_workflow.py
# Purpose: Handle motion detection with adaptive lighting conditions and confidence-based detection
#
# March 19, 2025 Update - Version 1.4.4
# - Added running state check to prevent background image saving
# - Added version tagging to image filenames
# - Improved image management and cleanup
# - Fixed issues with text overlays on images

import os
import time
from datetime import datetime
from PIL import Image
import pyautogui
import pytz
import numpy as np
import json

# Import utilities
from utilities.constants import (
    BASE_IMAGES_DIR,
    get_comparison_image_path,
    CAMERA_MAPPINGS,
    get_base_image_path,
    VERSION
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

# Import global running flag if available, otherwise default to True for backward compatibility
try:
    from scripts.front_end_app import IS_RUNNING
except ImportError:
    IS_RUNNING = True

# Initialize logger and alert manager
logger = get_logger()
alert_manager = AlertManager()

# Set timezone
PACIFIC_TIME = pytz.timezone("America/Los_Angeles")

def get_version_tag():
    """
    Get version tag for image filenames.
    First checks environment variable, then falls back to constants.
    
    Returns:
        str: Version tag for image filenames
    """
    # Try to get from environment variable (set by front_end_app.py)
    env_version = os.environ.get('OWL_APP_VERSION')
    if env_version:
        return env_version
    
    # Fall back to VERSION constant
    return VERSION

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
            
            # Ensure default confidence threshold is set
            if "owl_confidence_threshold" not in config:
                # Set default threshold based on camera type
                if CAMERA_MAPPINGS.get(camera_name) == "Owl In Box":
                    config["owl_confidence_threshold"] = 75.0
                elif CAMERA_MAPPINGS.get(camera_name) == "Owl On Box":
                    config["owl_confidence_threshold"] = 65.0
                else:  # Owl In Area
                    config["owl_confidence_threshold"] = 55.0
                logger.info(f"Set default confidence threshold for {camera_name}: {config['owl_confidence_threshold']}%")
                
            # Ensure consecutive frames threshold is set
            if "consecutive_frames_threshold" not in config:
                config["consecutive_frames_threshold"] = 2
                
        # Verify base images directory based on local saving setting
        if not os.path.exists(BASE_IMAGES_DIR):
            os.makedirs(BASE_IMAGES_DIR, exist_ok=True)
            logger.info(f"Created base images directory: {BASE_IMAGES_DIR}")
            
        # Log confidence thresholds
        threshold_info = {camera: config.get("owl_confidence_threshold", 60.0) 
                          for camera, config in camera_configs.items()}
        logger.info(f"Confidence thresholds: {json.dumps(threshold_info)}")
            
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
        # Check if app is running
        global IS_RUNNING
        if not IS_RUNNING and not test_images:
            logger.info(f"Skipping camera processing for {camera_name}: Application not running")
            return {
                "camera": camera_name,
                "status": "Skipped",
                "is_owl_present": False,
                "owl_confidence": 0.0,
                "consecutive_owl_frames": 0,
                "timestamp": datetime.now(PACIFIC_TIME).isoformat()
            }
            
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
                "is_owl_present": False,
                "pixel_change": 0.0,
                "luminance_change": 0.0,
                "timestamp": timestamp.isoformat(),
                "owl_confidence": 0.0,
                "consecutive_owl_frames": 0,
                "threshold_used": config.get("owl_confidence_threshold", 60.0),
                "version": get_version_tag()  # Add version tag to results
            }
            
            logger.debug(f"Processing as {alert_type} type camera")
            
            # Pass camera name to detect_owl_in_box for temporal confidence
            is_owl_present, detection_info = detect_owl_in_box(
                new_image, 
                base_image,
                config,
                is_test=is_test,
                camera_name=camera_name
            )
            
            # Only create comparison image if either test mode or app is running
            comparison_path = None
            if is_test or IS_RUNNING:
                # Create comparison image with confidence data but NO TEXT OVERLAYS
                comparison_result = create_comparison_image(
                    base_image, 
                    new_image,
                    camera_name,
                    threshold=config["luminance_threshold"] * threshold_multiplier,
                    config=config,
                    detection_info=detection_info,
                    is_test=is_test,
                    timestamp=timestamp
                )
                
                comparison_path = comparison_result.get("composite_path")
            
            # Update detection results with detection info
            detection_results.update({
                "status": alert_type,
                "is_owl_present": is_owl_present,
                "owl_confidence": detection_info.get("owl_confidence", 0.0),
                "consecutive_owl_frames": detection_info.get("consecutive_owl_frames", 0),
                "confidence_factors": detection_info.get("confidence_factors", {}),
                "comparison_path": comparison_path,
                "pixel_change": detection_info.get("pixel_change", 0.0),
                "luminance_change": detection_info.get("luminance_change", 0.0),
                "threshold_used": config.get("owl_confidence_threshold", 60.0)
            })
            
            logger.info(
                f"Detection results for {camera_name}: Owl Present: {is_owl_present}, "
                f"Confidence: {detection_results['owl_confidence']:.1f}%, "
                f"Consecutive Frames: {detection_results['consecutive_owl_frames']}, "
                f"Threshold: {detection_results['threshold_used']}%"
            )

            # Format the results for database
            formatted_results = format_detection_results(detection_results)
            
            # Only push to Supabase if motion was detected or in test mode, and app is running or test mode
            if (is_owl_present or is_test) and (IS_RUNNING or is_test):
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
            "is_owl_present": False,
            "owl_confidence": 0.0,
            "consecutive_owl_frames": 0,
            "confidence_factors": {},
            "pixel_change": 0.0,
            "luminance_change": 0.0,
            "timestamp": datetime.now(PACIFIC_TIME).isoformat(),
            "version": get_version_tag()
        }

def process_cameras(camera_configs, test_images=None):
    """Process all cameras in batch for efficient motion detection"""
    try:
        # Check if app is running
        global IS_RUNNING
        if not IS_RUNNING and not test_images:
            logger.info("Skipping camera processing: Application not running")
            return []
            
        # Get lighting information once for all cameras
        lighting_condition = get_current_lighting_condition()
        threshold_multiplier = get_luminance_threshold_multiplier()
        
        lighting_info = {
            'condition': lighting_condition,
            'threshold_multiplier': threshold_multiplier
        }
        
        logger.info(f"Processing cameras under {lighting_condition} condition")
        
        # Only verify base images in real-time mode and if app is running
        if not test_images and IS_RUNNING:
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
                    "is_owl_present": False,
                    "owl_confidence": 0.0,
                    "consecutive_owl_frames": 0,
                    "confidence_factors": {},
                    "timestamp": datetime.now(PACIFIC_TIME).isoformat(),
                    "version": get_version_tag()
                })
        
        return results

    except Exception as e:
        logger.error(f"Error in camera processing cycle: {e}")
        raise

def update_thresholds(camera_configs, new_thresholds):
    """
    Update confidence thresholds in camera configurations.
    
    Args:
        camera_configs (dict): Camera configuration dictionary
        new_thresholds (dict): Dictionary of camera names to new threshold values
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        for camera_name, threshold in new_thresholds.items():
            if camera_name in camera_configs:
                threshold_value = float(threshold)
                if 0 <= threshold_value <= 100:
                    camera_configs[camera_name]["owl_confidence_threshold"] = threshold_value
                    logger.info(f"Updated confidence threshold for {camera_name} to {threshold_value}%")
                else:
                    logger.warning(f"Invalid threshold value for {camera_name}: {threshold_value}. Must be 0-100")
            else:
                logger.warning(f"Unknown camera: {camera_name}")
        
        # Update alert manager thresholds
        for camera_name, config in camera_configs.items():
            threshold = config.get("owl_confidence_threshold")
            if threshold is not None:
                alert_manager.set_confidence_threshold(camera_name, threshold)
                
        return True
        
    except Exception as e:
        logger.error(f"Error updating thresholds: {e}")
        return False

if __name__ == "__main__":
    # Set IS_RUNNING to True when running this file directly
    IS_RUNNING = True
    
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