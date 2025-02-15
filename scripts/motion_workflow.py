# File: motion_workflow.py
# Purpose: Handle motion detection with adaptive lighting conditions

import os
from datetime import datetime
from PIL import Image, ImageChops
import pyautogui
import pytz
import glob

# Import utilities
from utilities.constants import (
    BASE_IMAGES_DIR,
    CAMERA_SNAPSHOT_DIRS,
    IMAGE_COMPARISONS_DIR,
    get_base_image_filename
)
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

def get_latest_base_image(camera_name, lighting_condition):
    """
    Get the most recent base image for the given camera and lighting condition.
    
    Args:
        camera_name (str): Name of the camera
        lighting_condition (str): Current lighting condition
        
    Returns:
        str: Path to the most recent base image
    """
    try:
        # Generate the pattern for base images
        pattern = os.path.join(
            BASE_IMAGES_DIR,
            f"{camera_name.lower().replace(' ', '_')}_{lighting_condition}_base_*.jpg"
        )
        
        # Get list of matching files
        matching_files = glob.glob(pattern)
        
        if not matching_files:
            # Fall back to basic base image if no lighting-specific one exists
            basic_pattern = os.path.join(
                BASE_IMAGES_DIR,
                f"{camera_name.lower().replace(' ', '_')}_base.jpg"
            )
            matching_files = glob.glob(basic_pattern)
            
            if not matching_files:
                error_msg = f"No base image found for {camera_name} in {lighting_condition} condition"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
        
        # Get most recent file
        latest_file = max(matching_files, key=os.path.getctime)
        logger.info(f"Using base image: {latest_file}")
        return latest_file
        
    except Exception as e:
        logger.error(f"Error finding base image: {e}")
        raise

def load_base_image(camera_name, lighting_condition):
    """
    Load the appropriate base image for the current lighting condition.
    
    Args:
        camera_name (str): Name of the camera
        lighting_condition (str): Current lighting condition
        
    Returns:
        PIL.Image: Base image for comparison
    """
    try:
        base_image_path = get_latest_base_image(camera_name, lighting_condition)
        logger.info(f"Loading base image for {camera_name} ({lighting_condition})")
        return Image.open(base_image_path).convert("RGB")
    except Exception as e:
        logger.error(f"Error loading base image: {e}")
        raise

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

def detect_motion(base_image, new_image, config):
    """
    Compare images with lighting-adjusted thresholds.
    
    Args:
        base_image (PIL.Image): Reference image
        new_image (PIL.Image): Current captured image
        config (dict): Camera configuration with thresholds
    """
    try:
        # Get lighting-adjusted threshold
        threshold_multiplier = get_luminance_threshold_multiplier()
        adjusted_luminance_threshold = config["luminance_threshold"] * threshold_multiplier
        
        diff = ImageChops.difference(base_image, new_image).convert("L")
        total_pixels = diff.size[0] * diff.size[1]
        significant_pixels = sum(1 for pixel in diff.getdata() 
                               if pixel > adjusted_luminance_threshold)
        avg_luminance_change = sum(diff.getdata()) / total_pixels
        threshold_pixels = total_pixels * config["threshold_percentage"]
        motion_detected = significant_pixels > threshold_pixels
        
        # Log detection details
        lighting_condition = get_current_lighting_condition()
        logger.debug(
            f"Motion detection - Condition: {lighting_condition}, "
            f"Threshold Multiplier: {threshold_multiplier}, "
            f"Adjusted Threshold: {adjusted_luminance_threshold}, "
            f"Significant Pixels: {significant_pixels}, "
            f"Threshold Pixels: {threshold_pixels}, "
            f"Average Luminance Change: {avg_luminance_change}"
        )
        
        return motion_detected, significant_pixels, avg_luminance_change, total_pixels
        
    except Exception as e:
        logger.error(f"Error in motion detection: {e}")
        raise

def save_snapshot(image, camera_name):
    """Save the captured image as a snapshot"""
    try:
        # Get the snapshot directory for this camera
        snapshot_dir = CAMERA_SNAPSHOT_DIRS.get(camera_name)
        if not snapshot_dir:
            error_msg = f"No snapshot directory configured for camera: {camera_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Create dated subfolder
        date_folder = datetime.now(PACIFIC_TIME).strftime('%Y%m%d')
        dated_snapshot_dir = os.path.join(snapshot_dir, date_folder)
        os.makedirs(dated_snapshot_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now(PACIFIC_TIME).strftime('%H%M%S')
        lighting_condition = get_current_lighting_condition()
        snapshot_name = f"{timestamp}_{lighting_condition}.jpg"
        
        # Full path for snapshot
        snapshot_path = os.path.join(dated_snapshot_dir, snapshot_name)
        
        # Save the image
        image.save(snapshot_path)
        logger.info(f"Saved snapshot: {snapshot_path}")
        
        # Check if we should capture a new base image
        if should_capture_base_image():
            from capture_base_images import capture_base_images
            capture_base_images(lighting_condition)
        
        return snapshot_path
        
    except Exception as e:
        logger.error(f"Error saving snapshot: {e}")
        raise

def process_camera(camera_name, config):
    """Process motion detection for a specific camera"""
    try:
        logger.info(f"Processing camera: {camera_name}")
        
        # Get current lighting condition
        lighting_condition = get_current_lighting_condition()
        logger.info(f"Current lighting condition: {lighting_condition}")
        
        # Load appropriate base image
        base_image = load_base_image(camera_name, lighting_condition)
        new_image = capture_real_image(config["roi"])
        
        motion_detected, significant_pixels, avg_luminance_change, total_pixels = detect_motion(
            base_image,
            new_image,
            config
        )
        
        if motion_detected:
            snapshot_path = save_snapshot(new_image, camera_name)
            logger.info(
                f"Motion detected for {camera_name} "
                f"during {lighting_condition} condition"
            )
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
            "lighting_condition": lighting_condition
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