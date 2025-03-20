# File: scripts/motion_workflow.py
# Purpose: Handle motion detection with adaptive lighting conditions and confidence-based detection
#
# March 28, 2025 Update - Version 1.4.6
# - Added support for separate day and night detection settings
# - Skip detection during transition periods
# - Improved lighting condition handling
# - Enhanced logging for parameter selection

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
    get_luminance_threshold_multiplier,
    is_transition_period,
    is_pure_lighting_condition
)
from utilities.owl_detection_utils import detect_owl_in_box
from utilities.image_comparison_utils import create_comparison_image
from utilities.alert_manager import AlertManager
from utilities.confidence_utils import reset_frame_history
from capture_base_images import capture_base_images, get_latest_base_image

# Import function to check running state, otherwise default to True for backward compatibility
try:
    from scripts.front_end_app import get_running_state
    def is_app_running():
        return True  # Always return True for motion detection
except ImportError:
    def is_app_running():
        return True

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
            
            # Check for day and night settings
            if "day_settings" not in config or "night_settings" not in config:
                logger.warning(f"Camera {camera_name} missing day/night settings. Using legacy configuration.")
                # Create day/night settings from legacy configuration for backward compatibility
                migrate_legacy_config(config)
                
            # Ensure consecutive frames threshold is set
            if "consecutive_frames_threshold" not in config:
                config["consecutive_frames_threshold"] = 2
                
        # Verify base images directory based on local saving setting
        if not os.path.exists(BASE_IMAGES_DIR):
            os.makedirs(BASE_IMAGES_DIR, exist_ok=True)
            logger.info(f"Created base images directory: {BASE_IMAGES_DIR}")
            
        # Log confidence thresholds for day and night
        day_thresholds = {camera: config.get("day_settings", {}).get("owl_confidence_threshold", 60.0) 
                          for camera, config in camera_configs.items()}
        night_thresholds = {camera: config.get("night_settings", {}).get("owl_confidence_threshold", 60.0) 
                           for camera, config in camera_configs.items()}
                           
        logger.info(f"Day confidence thresholds: {json.dumps(day_thresholds)}")
        logger.info(f"Night confidence thresholds: {json.dumps(night_thresholds)}")
            
        logger.info("Motion detection system initialization complete")
        return True
        
    except Exception as e:
        logger.error(f"Error during motion detection system initialization: {e}")
        return False

def migrate_legacy_config(config):
    """
    Migrate legacy configuration to day/night settings format.
    
    Args:
        config (dict): Camera configuration to migrate
    """
    try:
        # Create day settings from existing config
        day_settings = {}
        night_settings = {}
        
        # List of parameters to migrate
        params_to_migrate = [
            "threshold_percentage",
            "luminance_threshold", 
            "owl_confidence_threshold",
            "lighting_thresholds",
            "motion_detection"
        ]
        
        # Copy existing parameters to day settings
        for param in params_to_migrate:
            if param in config:
                day_settings[param] = config[param]
                
        # Create night settings with slightly adjusted values
        night_settings = json.loads(json.dumps(day_settings))  # Deep copy
        
        # Adjust night settings for better infrared detection
        if "threshold_percentage" in night_settings:
            night_settings["threshold_percentage"] = min(night_settings["threshold_percentage"] * 1.5, 1.0)
            
        if "luminance_threshold" in night_settings:
            night_settings["luminance_threshold"] = max(night_settings["luminance_threshold"] * 0.8, 5)
            
        if "owl_confidence_threshold" in night_settings:
            night_settings["owl_confidence_threshold"] = min(night_settings["owl_confidence_threshold"] * 1.1, 95.0)
            
        if "motion_detection" in night_settings:
            # Adjust motion detection parameters for night
            if "min_circularity" in night_settings["motion_detection"]:
                night_settings["motion_detection"]["min_circularity"] = min(
                    night_settings["motion_detection"]["min_circularity"] + 0.1, 
                    0.9
                )
                
            if "min_area_ratio" in night_settings["motion_detection"]:
                night_settings["motion_detection"]["min_area_ratio"] = min(
                    night_settings["motion_detection"]["min_area_ratio"] * 1.2, 
                    0.5
                )
                
            if "brightness_threshold" in night_settings["motion_detection"]:
                night_settings["motion_detection"]["brightness_threshold"] = max(
                    night_settings["motion_detection"]["brightness_threshold"] * 0.7, 
                    10
                )
        
        # Set the day and night settings in the config
        config["day_settings"] = day_settings
        config["night_settings"] = night_settings
        
        logger.info("Successfully migrated legacy configuration to day/night settings format")
        
    except Exception as e:
        logger.error(f"Error migrating legacy config: {e}")
        # Ensure at least empty settings are created
        if "day_settings" not in config:
            config["day_settings"] = {}
        if "night_settings" not in config:
            config["night_settings"] = {}

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

def get_settings_for_lighting(config, lighting_condition):
    """
    Get the appropriate settings for the current lighting condition.
    
    Args:
        config (dict): Camera configuration
        lighting_condition (str): Current lighting condition ('day', 'night', or 'transition')
        
    Returns:
        dict: Settings to use for detection
    """
    if lighting_condition == 'day' and "day_settings" in config:
        return config["day_settings"]
    elif lighting_condition == 'night' and "night_settings" in config:
        return config["night_settings"]
    elif lighting_condition == 'transition':
        # During transition periods, we'll return None to skip detection
        return None
    else:
        # Fallback to legacy settings
        logger.warning(f"Using legacy settings for {lighting_condition} condition")
        settings = {}
        # List of parameters to include
        params = [
            "threshold_percentage",
            "luminance_threshold", 
            "owl_confidence_threshold",
            "lighting_thresholds",
            "motion_detection"
        ]
        
        # Copy parameters from config to settings
        for param in params:
            if param in config:
                settings[param] = config[param]
                
        return settings

def process_camera(camera_name, config, lighting_info=None, test_images=None):
    """Process motion detection for a specific camera with confidence-based detection"""
    try:
        # Check if app is running
        if not is_app_running() and not test_images:
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
            
            # Skip detection during transition periods
            if lighting_condition == 'transition' and not test_images:
                logger.info(f"Skipping detection for {camera_name} during transition period")
                return {
                    "camera": camera_name,
                    "status": "Skipped - Transition Period",
                    "is_owl_present": False,
                    "owl_confidence": 0.0,
                    "consecutive_owl_frames": 0,
                    "timestamp": timestamp.isoformat(),
                    "lighting_condition": lighting_condition
                }
            
            # Get appropriate settings for current lighting
            settings = get_settings_for_lighting(config, lighting_condition)
            if settings is None and not test_images:
                logger.warning(f"No settings available for {lighting_condition} condition. Skipping detection.")
                return {
                    "camera": camera_name,
                    "status": "Skipped - No Settings",
                    "is_owl_present": False,
                    "owl_confidence": 0.0,
                    "consecutive_owl_frames": 0,
                    "timestamp": timestamp.isoformat(),
                    "lighting_condition": lighting_condition
                }
                
            # Log which settings we're using
            if settings:
                logger.info(f"Using {lighting_condition} settings for {camera_name} with confidence threshold: {settings.get('owl_confidence_threshold', 60.0)}")
            
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
                "threshold_used": settings.get("owl_confidence_threshold", 60.0) if settings else 60.0,
                "version": get_version_tag(),  # Add version tag to results
                "lighting_condition": lighting_condition
            }
            
            logger.debug(f"Processing as {alert_type} type camera")
            
            # Create detection config by combining camera config with lighting settings
            detection_config = {**config}
            if settings:
                # Add lighting-specific settings to detection config
                for key, value in settings.items():
                    detection_config[key] = value
                
            # Pass camera name to detect_owl_in_box for temporal confidence
            is_owl_present, detection_info = detect_owl_in_box(
                new_image, 
                base_image,
                detection_config,
                is_test=is_test,
                camera_name=camera_name
            )
            
            # Only create comparison image if either test mode or app is running
            comparison_path = None
            if is_test or is_app_running():
                # Create comparison image with confidence data but NO TEXT OVERLAYS
                comparison_result = create_comparison_image(
                    base_image, 
                    new_image,
                    camera_name,
                    threshold=detection_config["luminance_threshold"] * threshold_multiplier,
                    config=detection_config,
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
                "threshold_used": detection_config.get("owl_confidence_threshold", 60.0)
            })
            
            logger.info(
                f"Detection results for {camera_name} ({lighting_condition}): Owl Present: {is_owl_present}, "
                f"Confidence: {detection_results['owl_confidence']:.1f}%, "
                f"Consecutive Frames: {detection_results['consecutive_owl_frames']}, "
                f"Threshold: {detection_results['threshold_used']}%"
            )

            # Format the results for database
            formatted_results = format_detection_results(detection_results)
            
            # Only push to Supabase if motion was detected or in test mode, and app is running or test mode
            if (is_owl_present or is_test) and (is_app_running() or is_test):
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
            "version": get_version_tag(),
            "lighting_condition": lighting_condition if 'lighting_condition' in locals() else "unknown"
        }

def process_cameras(camera_configs, test_images=None):
    """Process all cameras in batch for efficient motion detection"""
    try:
        # Check if app is running
        if not is_app_running() and not test_images:
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
        
        # Skip processing during transition periods
        if lighting_condition == 'transition' and not test_images:
            logger.info("Transition period detected - skipping detection for all cameras")
            results = []
            for camera_name in camera_configs.keys():
                results.append({
                    "camera": camera_name,
                    "status": "Skipped - Transition Period",
                    "is_owl_present": False,
                    "owl_confidence": 0.0,
                    "consecutive_owl_frames": 0,
                    "timestamp": datetime.now(PACIFIC_TIME).isoformat(),
                    "lighting_condition": lighting_condition
                })
            return results
        
        # Only verify base images in real-time mode and if app is running
        if not test_images and is_app_running():
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
                    "version": get_version_tag(),
                    "lighting_condition": lighting_condition
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
        # Update thresholds for day and night settings
        for camera_name, threshold in new_thresholds.items():
            if camera_name in camera_configs:
                threshold_value = float(threshold)
                if 0 <= threshold_value <= 100:
                    # Get current lighting condition to determine which settings to update
                    lighting_condition = get_current_lighting_condition()
                    
                    if lighting_condition == 'day' and 'day_settings' in camera_configs[camera_name]:
                        camera_configs[camera_name]['day_settings']["owl_confidence_threshold"] = threshold_value
                        logger.info(f"Updated day confidence threshold for {camera_name} to {threshold_value}%")
                    elif lighting_condition == 'night' and 'night_settings' in camera_configs[camera_name]:
                        camera_configs[camera_name]['night_settings']["owl_confidence_threshold"] = threshold_value
                        logger.info(f"Updated night confidence threshold for {camera_name} to {threshold_value}%")
                    else:
                        # Fallback to legacy setting
                        camera_configs[camera_name]["owl_confidence_threshold"] = threshold_value
                        logger.info(f"Updated legacy confidence threshold for {camera_name} to {threshold_value}%")
                else:
                    logger.warning(f"Invalid threshold value for {camera_name}: {threshold_value}. Must be 0-100")
            else:
                logger.warning(f"Unknown camera: {camera_name}")
        
        # Update alert manager thresholds
        for camera_name, config in camera_configs.items():
            # Get current lighting condition
            lighting_condition = get_current_lighting_condition()
            
            # Get appropriate threshold based on lighting
            if lighting_condition == 'day' and 'day_settings' in config:
                threshold = config['day_settings'].get("owl_confidence_threshold")
            elif lighting_condition == 'night' and 'night_settings' in config:
                threshold = config['night_settings'].get("owl_confidence_threshold")
            else:
                threshold = config.get("owl_confidence_threshold")
                
            if threshold is not None:
                alert_manager.set_confidence_threshold(camera_name, threshold)
                
        return True
        
    except Exception as e:
        logger.error(f"Error updating thresholds: {e}")
        return False

if __name__ == "__main__":
    # Set is_app_running() to return True when running this file directly
    def is_app_running():
        return True
    
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

# Import at the end to avoid circular import
from push_to_supabase import push_log_to_supabase, format_detection_results