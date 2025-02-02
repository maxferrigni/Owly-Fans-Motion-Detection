# File: motion_workflow.py
# Purpose: Handle motion detection with adaptive lighting conditions

import os
from datetime import datetime
from PIL import Image, ImageChops
import pyautogui
import pytz

# Import utilities
from utilities.constants import BASE_IMAGES_DIR, CAMERA_SNAPSHOT_DIRS
from utilities.logging_utils import get_logger
from utilities.time_utils import (
    get_current_lighting_condition,
    should_capture_base_image,
    get_luminance_threshold_multiplier
)

# Initialize logger
logger = get_logger()

# Set timezone
PACIFIC_TIME = pytz.timezone("America/Los_Angeles")

def load_base_image(camera_name):
    """Load the base image for a specific camera."""
    lighting_condition = get_current_lighting_condition()
    base_image_name = f"{camera_name.replace(' ', '_')}_{lighting_condition}_base.jpg"
    base_image_path = os.path.join(BASE_IMAGES_DIR, base_image_name)
    
    # If specific lighting condition base image doesn't exist, fall back to default
    if not os.path.exists(base_image_path):
        base_image_path = os.path.join(BASE_IMAGES_DIR, f"{camera_name.replace(' ', '_')}_base.jpg")
        
    if not os.path.exists(base_image_path):
        error_msg = f"Base image not found for {camera_name}: {base_image_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    logger.info(f"Loading base image for {camera_name} ({lighting_condition})")
    return Image.open(base_image_path).convert("RGB")

def capture_real_image(roi):
    """Capture a screenshot of the specified region."""
    try:
        x, y, width, height = roi
        region = (x, y, width - x, height - y)
        logger.debug(f"Capturing screenshot with ROI: {region}")
        screenshot = pyautogui.screenshot(region=region)
        return screenshot.convert("RGB")
    except Exception as e:
        logger.error(f"Error capturing screenshot: {e}")
        raise

def save_base_image(image, camera_name):
    """Save a new base image if lighting conditions are optimal."""
    try:
        if should_capture_base_image():
            lighting_condition = get_current_lighting_condition()
            base_image_name = f"{camera_name.replace(' ', '_')}_{lighting_condition}_base.jpg"
            base_image_path = os.path.join(BASE_IMAGES_DIR, base_image_name)
            
            image.save(base_image_path)
            logger.info(f"Saved new base image for {camera_name} ({lighting_condition})")
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error saving base image: {e}")
        return False

def detect_motion(base_image, new_image, config):
    """
    Compare images to detect motion, adjusting for current lighting conditions.
    """
    try:
        diff = ImageChops.difference(base_image, new_image).convert("L")
        total_pixels = diff.size[0] * diff.size[1]
        
        # Adjust luminance threshold based on lighting conditions
        base_luminance = config["luminance_threshold"]
        multiplier = get_luminance_threshold_multiplier()
        adjusted_luminance = base_luminance * multiplier
        
        logger.debug(f"Adjusted luminance threshold: {adjusted_luminance} "
                    f"(base: {base_luminance}, multiplier: {multiplier})")
        
        significant_pixels = sum(1 for pixel in diff.getdata() 
                               if pixel > adjusted_luminance)
        avg_luminance_change = sum(diff.getdata()) / total_pixels
        threshold_pixels = total_pixels * config["threshold_percentage"]
        motion_detected = significant_pixels > threshold_pixels
        
        logger.debug(f"Motion detection - Significant pixels: {significant_pixels}, "
                    f"Threshold: {threshold_pixels}, "
                    f"Average luminance change: {avg_luminance_change}")
        
        return motion_detected, significant_pixels, avg_luminance_change, total_pixels
    except Exception as e:
        logger.error(f"Error in motion detection: {e}")
        raise

def save_snapshot(image, camera_name):
    """Save the captured image as a snapshot."""
    try:
        snapshot_folder = CAMERA_SNAPSHOT_DIRS[camera_name]
        os.makedirs(snapshot_folder, exist_ok=True)
        
        timestamp = datetime.now(PACIFIC_TIME).strftime('%Y%m%d%H%M%S')
        lighting_condition = get_current_lighting_condition()
        snapshot_name = f"{camera_name.replace(' ', '_')}_{lighting_condition}_{timestamp}.jpg"
        snapshot_path = os.path.join(snapshot_folder, snapshot_name)
        
        image.save(snapshot_path)
        logger.info(f"Saved snapshot: {snapshot_path}")
        return snapshot_path
    except Exception as e:
        logger.error(f"Error saving snapshot: {e}")
        raise

def process_camera(camera_name, config):
    """Process motion detection for a specific camera."""
    try:
        logger.info(f"Processing camera: {camera_name}")
        current_lighting = get_current_lighting_condition()
        logger.info(f"Current lighting condition: {current_lighting}")
        
        base_image = load_base_image(camera_name)
        new_image = capture_real_image(config["roi"])
        
        # Potentially update base image if conditions are optimal
        if should_capture_base_image():
            save_base_image(new_image, camera_name)
        
        motion_detected, significant_pixels, avg_luminance_change, total_pixels = detect_motion(
            base_image,
            new_image,
            config
        )
        
        if motion_detected:
            snapshot_path = save_snapshot(new_image, camera_name)
            logger.info(f"Motion detected for {camera_name} under {current_lighting} conditions")
        else:
            snapshot_path = ""
            logger.debug(f"No motion detected for {camera_name}")
        
        pixel_change = significant_pixels / total_pixels
        status = config["alert_type"] if motion_detected else "No Motion"

        return {
            "status": status,
            "pixel_change": pixel_change,
            "luminance_change": avg_luminance_change,
            "snapshot_path": snapshot_path,
            "lighting_condition": current_lighting
        }

    except Exception as e:
        logger.error(f"Error processing {camera_name}: {e}")
        return {
            "status": "Error",
            "error_message": str(e),
            "pixel_change": 0.0,
            "luminance_change": 0.0,
            "snapshot_path": "",
            "lighting_condition": "unknown"
        }