# File: motion_workflow.py
# Purpose: Handle motion detection by comparing base images with new snapshots

import os
from datetime import datetime
from PIL import Image, ImageChops
import pyautogui
import pytz

# Import utilities
from utilities.constants import BASE_IMAGES_DIR, CAMERA_SNAPSHOT_DIRS
from utilities.logging_utils import get_logger

# Initialize logger
logger = get_logger()

# Set timezone
PACIFIC_TIME = pytz.timezone("America/Los_Angeles")

def load_base_image(camera_name):
    """
    Load the base image for a specific camera.
    
    Args:
        camera_name (str): Name of the camera
        
    Returns:
        PIL.Image: Base image for comparison
    """
    base_image_path = os.path.join(BASE_IMAGES_DIR, f"{camera_name.replace(' ', '_')}_base.jpg")
    if not os.path.exists(base_image_path):
        error_msg = f"Base image not found for {camera_name}: {base_image_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    logger.info(f"Loading base image for {camera_name}")
    return Image.open(base_image_path).convert("RGB")

def capture_real_image(roi):
    """
    Capture a screenshot of the region specified by the camera's ROI.
    
    Args:
        roi (tuple): Region of interest (x, y, width, height)
        
    Returns:
        PIL.Image: Captured screenshot
    """
    try:
        x, y, width, height = roi
        region = (x, y, width - x, height - y)
        logger.debug(f"Capturing screenshot with ROI: {region}")
        screenshot = pyautogui.screenshot(region=region)
        return screenshot.convert("RGB")
    except Exception as e:
        logger.error(f"Error capturing screenshot: {e}")
        raise

def detect_motion(base_image, new_image, threshold_percentage, luminance_threshold):
    """
    Compare the base image and the new image to detect motion.
    
    Args:
        base_image (PIL.Image): Reference image
        new_image (PIL.Image): Current captured image
        threshold_percentage (float): Motion detection threshold
        luminance_threshold (int): Minimum luminance change to consider
        
    Returns:
        tuple: (motion_detected, significant_pixels, avg_luminance_change, total_pixels)
    """
    try:
        diff = ImageChops.difference(base_image, new_image).convert("L")
        total_pixels = diff.size[0] * diff.size[1]
        significant_pixels = sum(1 for pixel in diff.getdata() if pixel > luminance_threshold)
        avg_luminance_change = sum(diff.getdata()) / total_pixels
        threshold_pixels = total_pixels * threshold_percentage
        motion_detected = significant_pixels > threshold_pixels
        
        logger.debug(f"Motion detection - Significant pixels: {significant_pixels}, "
                    f"Threshold: {threshold_pixels}, "
                    f"Average luminance change: {avg_luminance_change}")
        
        return motion_detected, significant_pixels, avg_luminance_change, total_pixels
    except Exception as e:
        logger.error(f"Error in motion detection: {e}")
        raise

def save_snapshot(image, camera_name):
    """
    Save the captured image as a snapshot.
    
    Args:
        image (PIL.Image): Image to save
        camera_name (str): Name of the camera
        
    Returns:
        str: Path to saved snapshot
    """
    try:
        snapshot_folder = CAMERA_SNAPSHOT_DIRS[camera_name]
        os.makedirs(snapshot_folder, exist_ok=True)
        
        timestamp = datetime.now(PACIFIC_TIME).strftime('%Y%m%d%H%M%S')
        snapshot_name = f"{camera_name.replace(' ', '_')}_{timestamp}.jpg"
        snapshot_path = os.path.join(snapshot_folder, snapshot_name)
        
        image.save(snapshot_path)
        logger.info(f"Saved snapshot: {snapshot_path}")
        return snapshot_path
    except Exception as e:
        logger.error(f"Error saving snapshot: {e}")
        raise

def process_camera(camera_name, config):
    """
    Process motion detection for a specific camera.
    
    Args:
        camera_name (str): Name of the camera
        config (dict): Camera configuration
        
    Returns:
        dict: Detection results for Supabase logging
    """
    try:
        logger.info(f"Processing camera: {camera_name}")
        
        base_image = load_base_image(camera_name)
        new_image = capture_real_image(config["roi"])
        
        motion_detected, significant_pixels, avg_luminance_change, total_pixels = detect_motion(
            base_image,
            new_image,
            config["threshold_percentage"],
            config["luminance_threshold"],
        )
        
        if motion_detected:
            snapshot_path = save_snapshot(new_image, camera_name)
            logger.info(f"Motion detected for {camera_name}")
        else:
            snapshot_path = ""
            logger.debug(f"No motion detected for {camera_name}")
        
        pixel_change = significant_pixels / total_pixels
        status = config["alert_type"] if motion_detected else "No Motion"

        return {
            "status": status,
            "pixel_change": pixel_change,
            "luminance_change": avg_luminance_change,
            "snapshot_path": snapshot_path
        }

    except Exception as e:
        logger.error(f"Error processing {camera_name}: {e}")
        return {
            "status": "Error",
            "error_message": str(e),
            "pixel_change": 0.0,
            "luminance_change": 0.0,
            "snapshot_path": ""
        }