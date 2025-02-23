# File: motion_workflow.py
# Purpose: Handle motion detection with adaptive lighting conditions

import os
import time
from datetime import datetime
from PIL import Image
import pyautogui
import pytz
import numpy as np
import shutil

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

# Initialize logger and alert manager
logger = get_logger()
alert_manager = AlertManager()

# Set timezone
PACIFIC_TIME = pytz.timezone("America/Los_Angeles")

def initialize_system(camera_configs, is_test=False):
    """
    Initialize the motion detection system.
    
    Args:
        camera_configs (dict): Dictionary of camera configurations
        is_test (bool): Whether this is a test initialization
        
    Returns:
        bool: True if initialization successful
    """
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
        local_saving = os.getenv('OWL_LOCAL_SAVING', 'True').lower() == 'true'  # Changed default to True
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

def verify_base_images(lighting_condition):
    """Verify that all necessary base images exist and are recent"""
    try:
        logger.info("Verifying base images...")
        
        # Determine which directories to check based on local saving setting
        local_saving = os.getenv('OWL_LOCAL_SAVING', 'True').lower() == 'true'  # Changed default to True
        check_dirs = [TEMP_BASE_IMAGES_DIR]
        if local_saving:
            check_dirs.append(BASE_IMAGES_DIR)
        
        # Track found base images
        found_images = {camera: False for camera in CAMERA_MAPPINGS.keys()}
        
        # Check all relevant directories
        for directory in check_dirs:
            if not os.path.exists(directory):
                continue
                
            base_images = os.listdir(directory)
            
            # Check for each camera
            for camera_name in CAMERA_MAPPINGS.keys():
                if found_images[camera_name]:
                    continue
                    
                base_pattern = f"{camera_name.lower().replace(' ', '_')}_{lighting_condition}_base"
                matching_files = [f for f in base_images if f.startswith(base_pattern)]
                
                if matching_files:
                    # Get most recent file
                    latest_file = max(matching_files, key=lambda f: os.path.getctime(
                        os.path.join(directory, f)
                    ))
                    file_path = os.path.join(directory, latest_file)
                    
                    # Check age - using 2 minutes as threshold since these are temp files
                    file_age = time.time() - os.path.getctime(file_path)
                    if file_age > 120:  # 2 minutes in seconds
                        logger.info(f"Base image for {camera_name} is too old")
                        continue
                        
                    found_images[camera_name] = True
        
        # Check if all cameras have valid base images
        all_valid = all(found_images.values())
        if not all_valid:
            missing_cameras = [cam for cam, found in found_images.items() if not found]
            logger.info(f"Missing or outdated base images for: {', '.join(missing_cameras)}")
            return False
            
        logger.info("Base image verification complete")
        return True
        
    except Exception as e:
        logger.error(f"Error verifying base images: {e}")
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

def save_to_archive(comparison_path, camera_name):
    """
    Save a copy of the comparison image to the archive directory.
    
    Args:
        comparison_path (str): Path to the comparison image
        camera_name (str): Name of the camera
    """
    try:
        if os.getenv('OWL_LOCAL_SAVING', 'True').lower() == 'true':  # Changed default to True
            current_time = datetime.now(PACIFIC_TIME)
            archive_path = get_archive_comparison_path(camera_name, current_time)
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(archive_path), exist_ok=True)
            
            # Copy the comparison image to archive
            shutil.copy2(comparison_path, archive_path)
            logger.info(f"Archived comparison image to: {archive_path}")
    except Exception as e:
        logger.error(f"Error archiving comparison image: {e}")

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
        
        # Get images either from test or capture
        if test_images:
            base_image = test_images['base']
            new_image = test_images['test']
            is_test = True
        else:
            base_image = get_latest_base_image(camera_name, lighting_condition)
            new_image = capture_real_image(config["roi"])
            is_test = False
        
        # Handle different camera types
        motion_detected = False
        owl_info = None
        comparison_path = None

        if config["alert_type"] == "Owl In Box":
            # Use specialized owl detection for box camera
            is_owl_present, detection_info = detect_owl_in_box(
                new_image, 
                base_image, 
                config,
                is_test=is_test
            )
            motion_detected = is_owl_present
            owl_info = detection_info
            
            # Generate comparison image
            if motion_detected:
                comparison_path = create_comparison_image(
                    base_image, 
                    new_image, 
                    config["alert_type"],
                    config["motion_detection"]["brightness_threshold"],
                    config,
                    is_test=is_test
                )
        else:
            # Create comparison image and get metrics
            comparison_path = create_comparison_image(
                base_image, 
                new_image, 
                camera_name=config["alert_type"],
                threshold=config["luminance_threshold"] * threshold_multiplier,
                config=config,
                is_test=is_test
            )
            
            # Get metrics from comparison image
            diff_image = Image.open(comparison_path)
            width = diff_image.size[0] // 3  # Get the size of one panel
            diff_panel = diff_image.crop((width * 2, 0, width * 3, diff_image.height))
            
            # Process metrics
            pixels_array = np.array(diff_panel.convert('L'))
            changed_pixels = np.sum(pixels_array > config["luminance_threshold"])
            total_pixels = pixels_array.size
            
            motion_detected = (changed_pixels / total_pixels) > config["threshold_percentage"]
            owl_info = {
                "pixel_change": changed_pixels / total_pixels,
                "luminance_change": np.mean(pixels_array),
                "threshold_used": config["luminance_threshold"],
                "is_test": is_test
            }

        # If motion detected and we have a comparison image, save to archive
        if motion_detected and comparison_path:
            save_to_archive(comparison_path, camera_name)

        # Clean up temporary comparison image if local saving is disabled
        if (not os.getenv('OWL_LOCAL_SAVING', 'True').lower() == 'true' and  # Changed default to True
            comparison_path and 
            os.path.exists(comparison_path) and 
            'temp' in comparison_path):
            try:
                os.remove(comparison_path)
                logger.debug(f"Cleaned up temporary comparison image: {comparison_path}")
            except Exception as e:
                logger.error(f"Error cleaning up temporary file: {e}")
        
        if motion_detected:
            logger.info(
                f"Motion detected for {camera_name} "
                f"during {lighting_condition} condition"
            )
            
        return {
            "status": config["alert_type"] if motion_detected else "No Motion",
            "pixel_change": owl_info.get("pixel_change", 0.0) * 100 if owl_info else 0.0,
            "luminance_change": owl_info.get("luminance_change", 0.0) if owl_info else 0.0,
            "snapshot_path": comparison_path if motion_detected else "",
            "lighting_condition": lighting_condition,
            "detection_info": owl_info,
            "is_test": is_test
        }

    except Exception as e:
        logger.error(f"Error processing {camera_name}: {e}")
        return {
            "status": "Error",
            "error_message": str(e),
            "pixel_change": 0.0,
            "luminance_change": 0.0,
            "snapshot_path": "",
            "lighting_condition": "unknown",
            "detection_info": None,
            "is_test": test_images is not None
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
            if not verify_base_images(lighting_condition):
                logger.info("Base images need to be updated")
                capture_base_images(lighting_condition, force_capture=True)
                time.sleep(3)  # Allow system to stabilize after capture
        
        # Process each camera with shared lighting info
        results = []
        for camera_name, config in camera_configs.items():
            try:
                # Get test images for this camera if in test mode
                camera_test_images = test_images.get(camera_name) if test_images else None
                
                result = process_camera(
                    camera_name, 
                    config, 
                    lighting_info,
                    test_images=camera_test_images
                )
                
                # Only process alerts for non-test detections
                if not result.get("is_test", False):
                    alert_manager.process_detection(camera_name, result)
                
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing camera {camera_name}: {e}")
                results.append({
                    "camera": camera_name,
                    "status": "Error",
                    "error_message": str(e),
                    "is_test": test_images is not None
                })
        
        return results

    except Exception as e:
        logger.error(f"Error in camera processing cycle: {e}")
        raise