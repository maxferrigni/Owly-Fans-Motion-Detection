# File: motion_workflow.py
# Purpose: Handle motion detection with adaptive lighting conditions

import os
from datetime import datetime
from PIL import Image
import pyautogui
import pytz

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
from utilities.image_comparison_utils import create_comparison_image
from capture_base_images import capture_base_images

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
        PIL.Image: Base image for comparison
    """
    try:
        # Generate the pattern for base images
        base_pattern = f"{camera_name.lower().replace(' ', '_')}_{lighting_condition}_base"
        
        # Find matching base image
        matching_files = [f for f in os.listdir(BASE_IMAGES_DIR) 
                         if f.startswith(base_pattern)]
        
        if not matching_files:
            # If no base image exists, capture new ones
            logger.info(f"No base image found for {camera_name}. Capturing new base images...")
            capture_base_images(lighting_condition, force_capture=True)
            
            # Try to find the base image again
            matching_files = [f for f in os.listdir(BASE_IMAGES_DIR) 
                            if f.startswith(base_pattern)]
            
            if not matching_files:
                raise FileNotFoundError(f"No base image found for {camera_name}")
        
        # Get most recent file
        latest_file = max(matching_files, key=lambda f: os.path.getctime(
            os.path.join(BASE_IMAGES_DIR, f)
        ))
        
        base_image_path = os.path.join(BASE_IMAGES_DIR, latest_file)
        logger.info(f"Using base image: {base_image_path}")
        
        return Image.open(base_image_path).convert("RGB")
        
    except Exception as e:
        logger.error(f"Error finding base image: {e}")
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
        threshold_pixels = base_image.size[0] * base_image.size[1] * config["threshold_percentage"]
        
        # Create comparison image and get metrics
        comparison_path = create_comparison_image(
            base_image, 
            new_image, 
            camera_name=config["alert_type"],
            threshold=adjusted_luminance_threshold
        )
        
        # Get metrics from comparison image
        diff_image = Image.open(comparison_path)
        width = diff_image.size[0] // 3  # Get the size of one panel
        diff_panel = diff_image.crop((width * 2, 0, width * 3, diff_image.height))
        
        # Count red pixels in difference panel
        red_pixels = sum(1 for pixel in diff_panel.getdata() 
                        if isinstance(pixel, tuple) and pixel[0] > 200 and pixel[1] < 100 and pixel[2] < 100)
        
        total_pixels = diff_panel.size[0] * diff_panel.size[1]
        motion_detected = red_pixels > threshold_pixels
        
        # Calculate average luminance
        luminance_values = [sum(pixel[:3])/3 for pixel in diff_panel.getdata()]
        avg_luminance_change = sum(luminance_values) / len(luminance_values)
        
        # Log detection details
        lighting_condition = get_current_lighting_condition()
        logger.debug(
            f"Motion detection - Condition: {lighting_condition}, "
            f"Threshold Multiplier: {threshold_multiplier}, "
            f"Adjusted Threshold: {adjusted_luminance_threshold}, "
            f"Changed Pixels: {red_pixels}, "
            f"Threshold Pixels: {threshold_pixels}, "
            f"Average Luminance Change: {avg_luminance_change}"
        )
        
        return motion_detected, red_pixels/total_pixels, avg_luminance_change
        
    except Exception as e:
        logger.error(f"Error in motion detection: {e}")
        raise

def process_camera(camera_name, config):
    """Process motion detection for a specific camera"""
    try:
        logger.info(f"Processing camera: {camera_name}")
        
        # Get current lighting condition
        lighting_condition = get_current_lighting_condition()
        logger.info(f"Current lighting condition: {lighting_condition}")
        
        # Check if we need to capture new base images
        if should_capture_base_image():
            logger.info("Time to capture new base images")
            capture_base_images(lighting_condition)
        
        # Load appropriate base image
        base_image = get_latest_base_image(camera_name, lighting_condition)
        new_image = capture_real_image(config["roi"])
        
        # Detect motion and get metrics
        motion_detected, pixel_change, avg_luminance_change = detect_motion(
            base_image,
            new_image,
            config
        )
        
        if motion_detected:
            logger.info(
                f"Motion detected for {camera_name} "
                f"during {lighting_condition} condition"
            )
        else:
            logger.debug(f"No motion detected for {camera_name}")
        
        # Get the comparison image path
        comparison_path = get_comparison_image_path(camera_name)
        
        return {
            "status": config["alert_type"] if motion_detected else "No Motion",
            "pixel_change": pixel_change * 100,  # Convert to percentage
            "luminance_change": avg_luminance_change,
            "snapshot_path": comparison_path if motion_detected else "",
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