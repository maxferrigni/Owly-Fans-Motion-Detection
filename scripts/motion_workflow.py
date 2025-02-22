# File: motion_workflow.py
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
    get_comparison_image_path,
    CAMERA_MAPPINGS
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

def initialize_system(camera_configs):
    """
    Initialize the motion detection system.
    
    Args:
        camera_configs (dict): Dictionary of camera configurations
        
    Returns:
        bool: True if initialization successful
    """
    try:
        logger.info("Initializing motion detection system...")
        
        # Verify camera configurations
        if not camera_configs:
            logger.error("No camera configurations provided")
            return False
            
        # Check for required ROIs
        for camera_name, config in camera_configs.items():
            if "roi" not in config or not config["roi"]:
                logger.error(f"Missing ROI configuration for {camera_name}")
                return False
                
        # Verify base images directory exists
        if not os.path.exists(BASE_IMAGES_DIR):
            logger.error("Base images directory not found")
            return False
            
        # Log local saving status
        local_saving = os.getenv('OWL_LOCAL_SAVING', 'False').lower() == 'true'
        logger.info(f"Local image saving is {'enabled' if local_saving else 'disabled'}")
            
        # Motion detection system initialized successfully
        logger.info("Motion detection system initialization complete")
        return True
        
    except Exception as e:
        logger.error(f"Error during motion detection system initialization: {e}")
        return False

def verify_base_images(lighting_condition):
    """
    Verify that all necessary base images exist and are recent.
    
    Args:
        lighting_condition (str): Current lighting condition
        
    Returns:
        bool: True if all base images are valid
    """
    try:
        logger.info("Verifying base images...")
        
        # Check for base images
        base_images = os.listdir(BASE_IMAGES_DIR)
        if not base_images:
            logger.info("No base images found")
            return False
            
        # Check for each camera
        for camera_name in CAMERA_MAPPINGS.keys():
            base_pattern = f"{camera_name.lower().replace(' ', '_')}_{lighting_condition}_base"
            matching_files = [f for f in base_images if f.startswith(base_pattern)]
            
            if not matching_files:
                logger.info(f"No base image found for {camera_name}")
                return False
                
            # Check age of most recent base image
            latest_file = max(matching_files, key=lambda f: os.path.getctime(
                os.path.join(BASE_IMAGES_DIR, f)
            ))
            file_age = time.time() - os.path.getctime(os.path.join(BASE_IMAGES_DIR, latest_file))
            
            # If base image is more than 24 hours old, consider it invalid
            if file_age > 86400:  # 24 hours in seconds
                logger.info(f"Base image for {camera_name} is too old")
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

def process_camera(camera_name, config, lighting_info=None):
    """
    Process motion detection for a specific camera.
    
    Args:
        camera_name (str): Name of the camera
        config (dict): Camera configuration
        lighting_info (dict, optional): Current lighting information
        
    Returns:
        dict: Detection results
    """
    try:
        logger.info(f"Processing camera: {camera_name}")
        
        # Get or use provided lighting condition
        if lighting_info is None:
            lighting_condition = get_current_lighting_condition()
            threshold_multiplier = get_luminance_threshold_multiplier()
        else:
            lighting_condition = lighting_info['condition']
            threshold_multiplier = lighting_info['threshold_multiplier']
            
        logger.info(f"Current lighting condition: {lighting_condition}")
        
        # Load base image and capture new image
        base_image = get_latest_base_image(camera_name, lighting_condition)
        new_image = capture_real_image(config["roi"])
        
        # Handle different camera types
        motion_detected = False
        owl_info = None
        
        if config["alert_type"] == "Owl In Box":
            # Use specialized owl detection for box camera
            is_owl_present, detection_info = detect_owl_in_box(new_image, base_image, config)
            motion_detected = is_owl_present
            owl_info = detection_info
            
            # Generate comparison image
            comparison_path = None
            if motion_detected:
                comparison_path = create_comparison_image(
                    base_image, 
                    new_image, 
                    config["alert_type"],
                    config["motion_detection"]["brightness_threshold"],
                    config
                )
        else:
            # Create comparison image and get metrics
            comparison_path = create_comparison_image(
                base_image, 
                new_image, 
                camera_name=config["alert_type"],
                threshold=config["luminance_threshold"] * threshold_multiplier,
                config=config
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
                "threshold_used": config["luminance_threshold"]
            }

            # Clean up temporary comparison image if local saving is disabled
            if (not os.getenv('OWL_LOCAL_SAVING', 'False').lower() == 'true' and 
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
            "detection_info": owl_info
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
            "detection_info": None
        }

def process_cameras(camera_configs):
    """
    Process all cameras in batch for efficient motion detection.
    
    Args:
        camera_configs (dict): Dictionary of camera configurations
        
    Returns:
        list: List of detection results for each camera
    """
    try:
        # Get lighting information once for all cameras
        lighting_condition = get_current_lighting_condition()
        threshold_multiplier = get_luminance_threshold_multiplier()
        
        lighting_info = {
            'condition': lighting_condition,
            'threshold_multiplier': threshold_multiplier
        }
        
        logger.info(f"Processing cameras under {lighting_condition} condition")
        
        # Verify base images are valid
        if not verify_base_images(lighting_condition):
            logger.info("Base images need to be updated")
            capture_base_images(lighting_condition, force_capture=True)
            time.sleep(3)  # Allow system to stabilize after capture
        
        # Process each camera with shared lighting info
        results = []
        for camera_name, config in camera_configs.items():
            try:
                result = process_camera(camera_name, config, lighting_info)
                
                # Process detection for alerts
                alert_manager.process_detection(camera_name, result)
                
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