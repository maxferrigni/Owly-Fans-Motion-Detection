# File: scripts/motion_workflow.py
# Purpose: Handle motion detection with adaptive lighting conditions and confidence-based detection
#
# April 2025 Update - Version 2.1
# - Modified confidence calculation to be more additive rather than requiring high scores in all categories
# - Made shape detection more permissive, especially at night
# - Added special overrides for obvious owl detections, particularly for Wyze Internal Camera
# - Lowered thresholds across the board to improve detection rates
# - Added significant weight to pixel change and position data as primary detection factors
# - Fixed database schema alignment and image upload logic (v1.91)
# - V2.1 Updates: Fixed false positives, image URL problems, and upload function errors

import os
import time
from datetime import datetime
from PIL import Image
import pyautogui
import pytz
import numpy as np
import json
import cv2  # Required for motion pattern analysis

# Import utilities
from utilities.constants import (
    BASE_IMAGES_DIR,
    get_comparison_image_path,
    CAMERA_MAPPINGS,
    get_base_image_path,
    VERSION,
    SUPABASE_PUBLIC_URL,
    SUPABASE_STORAGE_URL
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

# Import function from Scripts
from scripts.upload_images_to_supabase import upload_comparison_image, upload_component_image, upload_detection_images
from scripts.push_to_supabase import generate_alert_id

# Import function to check running state, otherwise default to True for backward compatibility
try:
    from scripts.front_end_app import get_running_state
    def is_app_running():
        return True # always return true for testing
except ImportError:
    def is_app_running():
        return True

# Initialize logger and alert manager
logger = get_logger()
alert_manager = AlertManager()

# Set timezone
PACIFIC_TIME = pytz.timezone("America/Los_Angeles")

def analyze_motion_pattern(current_candidates, previous_candidates, current_frame, previous_frame):
    """Analyze motion patterns between frames to identify owl-like movement"""
    if not current_candidates or not previous_candidates:
        return 0.0  # No pattern to analyze
        
    # Create mask of current and previous candidates
    height, width = current_frame.shape[:2]
    current_mask = np.zeros((height, width), dtype=np.uint8)
    previous_mask = np.zeros((height, width), dtype=np.uint8)
    
    # Draw contours on masks
    for candidate in current_candidates:
        cv2.drawContours(current_mask, [candidate['contour']], -1, 255, -1)
    
    for candidate in previous_candidates:
        cv2.drawContours(previous_mask, [candidate['contour']], -1, 255, -1)
    
    # Calculate overlap
    overlap = cv2.bitwise_and(current_mask, previous_mask)
    overlap_pixels = np.sum(overlap > 0)
    
    # Calculate motion continuity score
    current_area = np.sum(current_mask > 0)
    previous_area = np.sum(previous_mask > 0)
    
    if current_area == 0 or previous_area == 0:
        return 0.0
        
    # Calculate weighted average of overlap ratio - MODIFIED: More lenient overlap requirement
    overlap_ratio = overlap_pixels / max(current_area, previous_area)
    
    # MODIFIED: Owl movement can have varying degrees of overlap - more lenient scoring
    # Previous ideal_overlap was 0.6, changed to accept wider range
    ideal_overlap = 0.4  # Lowered from 0.6 to be more permissive
    overlap_score = 10.0 * (1.0 - min(1.0, abs(overlap_ratio - ideal_overlap) / 0.6))
    
    return max(0, min(10, overlap_score))

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
            
            # Check for day or night settings
            if "day_settings" not in config or "night_settings" not in config:
                logger.warning(f"Camera {camera_name} missing day/night settings. Using legacy configuration.")
                # Create day/night settings from legacy configuration for backward compatibility
                migrate_legacy_config(config)
                
            # Ensure consecutive frames threshold is set
            if "consecutive_frames_threshold" not in config:
                config["consecutive_frames_threshold"] = 2  # Increased from 1
                
        # Verify base images directory based on local saving setting
        if not os.path.exists(BASE_IMAGES_DIR):
            os.makedirs(BASE_IMAGES_DIR, exist_ok=True)
            logger.info(f"Created base images directory: {BASE_IMAGES_DIR}")
            
        # Log confidence thresholds for day and night
        day_thresholds = {camera: config.get("day_settings", {}).get("owl_confidence_threshold", 55.0) 
                          for camera, config in camera_configs.items()}
        night_thresholds = {camera: config.get("night_settings", {}).get("owl_confidence_threshold", 50.0) 
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
        
        # MODIFIED: Adjust night settings for better detection
        if "threshold_percentage" in night_settings:
            # MODIFIED: Lower threshold percentage for night for better motion sensitivity
            night_settings["threshold_percentage"] = min(max(night_settings["threshold_percentage"] * 0.8, 0.05), 0.5)
            
        if "luminance_threshold" in night_settings:
            # MODIFIED: Lower luminance threshold at night to be more sensitive
            night_settings["luminance_threshold"] = max(night_settings["luminance_threshold"] * 0.6, 5)
            
        if "owl_confidence_threshold" in night_settings:
            # MODIFIED: Lower confidence threshold for night to be more permissive
            night_settings["owl_confidence_threshold"] = max(min(night_settings["owl_confidence_threshold"] * 0.8, 95.0), 45.0)
            
        if "motion_detection" in night_settings:
            # MODIFIED: Adjust motion detection parameters for night with more permissive settings
            if "min_circularity" in night_settings["motion_detection"]:
                night_settings["motion_detection"]["min_circularity"] = max(
                    night_settings["motion_detection"]["min_circularity"] * 0.7, 
                    0.3  # Lower minimum to 0.3
                )
                
            if "min_aspect_ratio" in night_settings["motion_detection"]:
                night_settings["motion_detection"]["min_aspect_ratio"] = max(
                    night_settings["motion_detection"]["min_aspect_ratio"] * 0.7, 
                    0.3  # Lower minimum to 0.3
                )
                
            if "max_aspect_ratio" in night_settings["motion_detection"]:
                night_settings["motion_detection"]["max_aspect_ratio"] = min(
                    night_settings["motion_detection"]["max_aspect_ratio"] * 1.3, 
                    2.5  # Increased max to 2.5
                )
                
            if "min_area_ratio" in night_settings["motion_detection"]:
                night_settings["motion_detection"]["min_area_ratio"] = max(
                    night_settings["motion_detection"]["min_area_ratio"] * 0.5, 
                    0.05  # Lowered to 0.05
                )
                
            if "brightness_threshold" in night_settings["motion_detection"]:
                night_settings["motion_detection"]["brightness_threshold"] = max(
                    night_settings["motion_detection"]["brightness_threshold"] * 0.6, 
                    10  # Lowered to be more sensitive
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
        # MODIFIED: During transition periods, use the more permissive of day/night settings
        # instead of returning None to skip detection
        if "day_settings" in config and "night_settings" in config:
            # For confidence threshold, use the lower of the two
            day_confidence = config["day_settings"].get("owl_confidence_threshold", 60.0)
            night_confidence = config["night_settings"].get("owl_confidence_threshold", 55.0)
            
            # Choose the settings with the lower confidence threshold
            if night_confidence <= day_confidence:
                transition_settings = dict(config["night_settings"])
            else:
                transition_settings = dict(config["day_settings"])
                
            # Lower the confidence threshold further for transition periods
            if "owl_confidence_threshold" in transition_settings:
                # MODIFIED: Reduce further for transition periods
                transition_settings["owl_confidence_threshold"] = max(transition_settings["owl_confidence_threshold"] * 0.9, 45.0)
                
            logger.info(f"Using transition settings with confidence threshold: {transition_settings.get('owl_confidence_threshold', 60.0)}")
            return transition_settings
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

def generate_image_url(image_path, alert_type, camera_name):
    """
    Generate a URL for an uploaded image.
    This function constructs a URL based on the storage path.
    
    Args:
        image_path (str): The local path to the image
        alert_type (str): The type of alert (e.g., "Owl In Box")
        camera_name (str): The name of the camera
        
    Returns:
        str: URL to the uploaded image
    """
    try:
        if not image_path:
            return None
            
        # Check if it's already a URL
        if image_path.startswith('http://') or image_path.startswith('https://'):
            return image_path
            
        # Convert local path to storage URL
        # Extract file name from path
        file_name = os.path.basename(image_path)
        
        # Format alert type for URL path (lowercase, underscores)
        alert_type_path = alert_type.lower().replace(' ', '_')
        
        # Use the standardized Supabase URL from constants
        url = f"{SUPABASE_STORAGE_URL}/owl_detections/{alert_type_path}/{file_name}"
        
        logger.debug(f"Generated URL for {image_path}: {url}")
        return url
    except Exception as e:
        logger.error(f"Error generating image URL: {e}")
        return None

def validate_image_url(url):
    """
    Validate an image URL to ensure it uses the correct Supabase domain.
    
    Args:
        url (str): Image URL to validate
        
    Returns:
        str: Corrected URL or None if invalid
    """
    if not url:
        return None
    
    try:
        # Check if using wrong domain and fix it
        wrong_domain = "project-dev-123.supabase.co"
        if wrong_domain in url:
            url = url.replace(wrong_domain, SUPABASE_PUBLIC_URL.replace("https://", ""))
            logger.info(f"Fixed incorrect domain in URL: {url}")
            
        # Make sure URL starts with proper protocol
        if not url.startswith("http"):
            url = f"https://{url}"
            
        # Simple check if URL seems valid
        if "supabase" not in url or ".co" not in url:
            logger.warning(f"URL doesn't look like a valid Supabase URL: {url}")
            return None
            
        return url
        
    except Exception as e:
        logger.error(f"Error validating URL: {e}")
        return None

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
        is_test = False
        
        try:
            # Get or use provided lighting condition
            if lighting_info is None:
                lighting_condition = get_current_lighting_condition()
                threshold_multiplier = get_luminance_threshold_multiplier()
            else:
                lighting_condition = lighting_info['condition']
                threshold_multiplier = lighting_info['threshold_multiplier']
                
            logger.info(f"Current lighting condition: {lighting_condition}")
            
            # MODIFIED: Don't skip detection during transition periods
            # Instead, use the more permissive settings
            
            # Get appropriate settings for current lighting
            settings = get_settings_for_lighting(config, lighting_condition)
            if settings is None and not test_images:
                # This should rarely happen now with the modified get_settings_for_lighting
                logger.warning(f"No settings available for {lighting_condition} condition. Using fallback settings.")
                # Create fallback settings with very permissive thresholds
                settings = {
                    "threshold_percentage": 0.05,
                    "luminance_threshold": 10,
                    "owl_confidence_threshold": 45.0,  # Very permissive
                    "motion_detection": {
                        "min_circularity": 0.3,
                        "min_aspect_ratio": 0.3,
                        "max_aspect_ratio": 2.5,
                        "min_area_ratio": 0.05,
                        "brightness_threshold": 15
                    }
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
                
            # MODIFIED: Adjust the threshold multiplier to be more sensitive
            # This effectively lowers all thresholds
            threshold_multiplier = threshold_multiplier * 0.8  # 20% reduction
            
            # Increase thresholds, especially for day conditions
            if lighting_condition == 'day' and 'day_settings' in config:
                # Get base threshold
                threshold = detection_config.get("owl_confidence_threshold", 55.0)
                # Increase for daytime (when false positives are more common)
                threshold = threshold * 1.25  # 25% increase for daytime
                detection_config["owl_confidence_threshold"] = threshold
                logger.debug(f"Increased day threshold to {threshold:.1f}%")
            elif lighting_condition == 'night' and 'night_settings' in config:
                # Get base threshold
                threshold = detection_config.get("owl_confidence_threshold", 50.0)
                # Slight increase for night
                threshold = threshold * 1.1  # 10% increase for night
                detection_config["owl_confidence_threshold"] = threshold
                logger.debug(f"Increased night threshold to {threshold:.1f}%")
                
            # Require more consecutive frames for all cameras
            if "consecutive_frames_threshold" not in detection_config:
                detection_config["consecutive_frames_threshold"] = 2  # Increased from 1
                
            # Apply higher threshold for day conditions
            if lighting_condition == 'day':
                detection_config["consecutive_frames_threshold"] = 3  # Even more consecutive frames required for day
            
            # Pass camera name to detect_owl_in_box for temporal confidence
            is_owl_present, detection_info = detect_owl_in_box(
                new_image, 
                base_image,
                detection_config,
                is_test=is_test,
                camera_name=camera_name
            )
            
            # Create comparison image for UI display regardless of detection
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
            component_paths = comparison_result.get('component_paths', {})

            # Store paths in detection_results for local usage
            detection_results['comparison_path'] = comparison_path
            if 'component_paths' in comparison_result:
                detection_results['component_paths'] = component_paths

            # IMPORTANT: Don't upload images yet - just keep the paths for now
            # We'll only upload images if an alert is actually triggered
            
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
                "threshold_used": detection_config.get("owl_confidence_threshold", 60.0),
                # Add detailed detection criteria for display in emails
                "detection_criteria": {
                    "shape_score": detection_info.get("confidence_factors", {}).get("shape_confidence", 0.0),
                    "motion_score": detection_info.get("confidence_factors", {}).get("motion_confidence", 0.0),
                    "temporal_score": detection_info.get("confidence_factors", {}).get("temporal_confidence", 0.0),
                    "camera_score": detection_info.get("confidence_factors", {}).get("camera_confidence", 0.0),
                    "pattern_score": detection_info.get("confidence_factors", {}).get("motion_pattern_bonus", 0.0)
                }
            })

            # ONLY upload images when an alert is actually triggered and active (not in cooldown)
            if is_owl_present and (is_app_running() or is_test):
                # Generate alert ID first for tracking
                alert_id = generate_alert_id()  # Import this from push_to_supabase
                detection_results['alert_id'] = alert_id
                
                # Now decide whether to send an alert
                alert_triggered = False
                if not is_test:
                    alert_triggered = alert_manager.process_detection(
                        camera_name,
                        detection_results,
                        None
                    )
                    
                # Only upload images if an alert was actually triggered or this is a test
                if alert_triggered or is_test:
                    logger.info(f"Alert was triggered - uploading images with alert ID: {alert_id}")
                    
                    # Upload only two essential images: comparison and current
                    if comparison_path:
                        comparison_image_url = upload_comparison_image(
                            comparison_path,
                            camera_name,
                            alert_type,
                            alert_id  # Include alert ID in filename
                        )
                        detection_results['comparison_image_url'] = comparison_image_url
                        
                    # Upload current image for context
                    if 'component_paths' in comparison_result and 'current' in comparison_result['component_paths']:
                        current_path = comparison_result['component_paths']['current']
                        current_image_url = upload_component_image(
                            current_path,
                            camera_name,
                            alert_type,
                            "current",
                            alert_id  # Include alert ID in filename
                        )
                        detection_results['current_image_url'] = current_image_url
                        
                    # No need to upload base image every time as it rarely changes
                    # Skip uploading analysis image - it's not needed in emails or database
                else:
                    logger.info(f"No alert triggered for {camera_name} - skipping image uploads")

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
            "status": "ProcessingError",  # Changed from "Error" to avoid upload attempts
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
            "lighting_condition": lighting_condition if 'lighting_condition' in locals() else "unknown",
            "_skip_upload": True  # Flag to indicate this shouldn't be uploaded
        }

def process_cameras(camera_configs, test_images=None):
    """
    Process all cameras in batch for efficient motion detection.
    Updated in v1.9.0 to properly handle error states and prevent error uploads to Supabase.
    
    Args:
        camera_configs (dict): Dictionary of camera configurations
        test_images (dict, optional): Test images for each camera
        
    Returns:
        list: List of detection results for each camera
    """
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
        
        # MODIFIED: Don't skip processing during transition periods
        # Instead use more permissive settings
        
        # Check if we should capture base images (only in real-time mode and if app is running)
        if not test_images and is_app_running():
            should_capture, condition = should_capture_base_image()
            if should_capture:
                logger.info(f"Time to capture new base images: {condition}")
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
                # Add result with skip_upload flag
                results.append({
                    "camera": camera_name,
                    "status": "ProcessingError",
                    "error_message": str(e),
                    "is_owl_present": False,
                    "owl_confidence": 0.0,
                    "consecutive_owl_frames": 0,
                    "confidence_factors": {},
                    "timestamp": datetime.now(PACIFIC_TIME).isoformat(),
                    "version": get_version_tag(),
                    "lighting_condition": lighting_condition,
                    "_skip_upload": True  # Flag to indicate this shouldn't be uploaded
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