# File: capture_base_images.py
# Purpose: Capture and manage base images for motion detection system

import os
import pyautogui
from PIL import Image
import json
from datetime import datetime
import pytz
import shutil

# Import utilities
from utilities.constants import (
    BASE_IMAGES_DIR,
    CONFIGS_DIR,
    get_base_image_filename
)
from utilities.logging_utils import get_logger
from utilities.time_utils import get_current_lighting_condition
from upload_images_to_supabase import upload_base_image

# Initialize logger
logger = get_logger()

def load_config():
    """Load camera configurations from the JSON file"""
    config_path = os.path.join(CONFIGS_DIR, "config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, 'r') as f:
        return json.load(f)

def capture_real_image(roi):
    """
    Capture a screenshot of the specified region.
    
    Args:
        roi (tuple): Region of interest (x, y, width, height)
    
    Returns:
        PIL.Image: Captured screenshot
    """
    x, y, width, height = roi
    width = abs(width - x)
    height = abs(height - y)
    logger.info(f"Capturing screenshot: x={x}, y={y}, width={width}, height={height}")
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid ROI dimensions: {roi}")
    return pyautogui.screenshot(region=(x, y, width, height))

def clear_base_images(lighting_condition=None):
    """
    Clear existing base images.
    
    Args:
        lighting_condition (str, optional): If provided, only clear images for this condition
    """
    try:
        if not os.path.exists(BASE_IMAGES_DIR):
            return

        for filename in os.listdir(BASE_IMAGES_DIR):
            if lighting_condition:
                if lighting_condition in filename:
                    os.remove(os.path.join(BASE_IMAGES_DIR, filename))
                    logger.info(f"Removed base image: {filename}")
            else:
                os.remove(os.path.join(BASE_IMAGES_DIR, filename))
                logger.info(f"Removed base image: {filename}")
    except Exception as e:
        logger.error(f"Error clearing base images: {e}")

def save_base_image(image, camera_name, lighting_condition):
    """
    Save base image locally and upload to Supabase.
    
    Args:
        image (PIL.Image): The base image to save
        camera_name (str): Name of the camera
        lighting_condition (str): Current lighting condition
        
    Returns:
        tuple: (local_path, supabase_url)
    """
    try:
        # Ensure base images directory exists
        os.makedirs(BASE_IMAGES_DIR, exist_ok=True)
        
        # Generate timestamp
        timestamp = datetime.now(pytz.timezone('America/Los_Angeles'))
        
        # Generate filename
        filename = get_base_image_filename(camera_name, lighting_condition, timestamp)
        
        # Save locally
        local_path = os.path.join(BASE_IMAGES_DIR, filename)
        if image.mode == "RGBA":
            image = image.convert("RGB")
        image.save(local_path)
        logger.info(f"Saved base image locally: {local_path}")
        
        # Upload to Supabase
        supabase_url = upload_base_image(local_path, camera_name, lighting_condition)
        
        return local_path, supabase_url
        
    except Exception as e:
        logger.error(f"Error saving base image: {e}")
        raise

def capture_base_images(lighting_condition=None, force_capture=False):
    """
    Capture new base images for all cameras.
    
    Args:
        lighting_condition (str, optional): Override current lighting condition
        force_capture (bool): Force capture regardless of timing conditions
        
    Returns:
        list: List of dictionaries containing capture results
    """
    logger.info("Starting base image capture process...")

    try:
        # Get current lighting condition if not provided
        if not lighting_condition:
            lighting_condition = get_current_lighting_condition()
        
        logger.info(f"Using lighting condition: {lighting_condition}")
        
        # Clear existing base images for this lighting condition
        clear_base_images(lighting_condition)
        
        configs = load_config()
        results = []
        
        for camera_name, config in configs.items():
            if config["roi"] is None:
                logger.warning(f"Skipping {camera_name}: No ROI defined.")
                continue
            
            logger.info(f"Capturing base image for {camera_name}...")
            
            try:
                # Capture new image
                new_image = capture_real_image(config["roi"])
                
                # Save and upload
                local_path, supabase_url = save_base_image(
                    new_image,
                    camera_name,
                    lighting_condition
                )
                
                results.append({
                    'camera': camera_name,
                    'local_path': local_path,
                    'supabase_url': supabase_url,
                    'status': 'success'
                })
                
            except Exception as e:
                logger.error(f"Error capturing base image for {camera_name}: {e}")
                results.append({
                    'camera': camera_name,
                    'status': 'error',
                    'error': str(e)
                })
        
        logger.info("Base image capture process completed")
        return results
        
    except Exception as e:
        logger.error(f"Error during base image capture process: {e}")
        raise

def handle_lighting_transition(old_condition, new_condition):
    """
    Handle transition between lighting conditions.
    
    Args:
        old_condition (str): Previous lighting condition
        new_condition (str): New lighting condition
    """
    try:
        logger.info(f"Handling lighting transition: {old_condition} -> {new_condition}")
        
        # Capture new base images for the new lighting condition
        capture_base_images(lighting_condition=new_condition, force_capture=True)
        
        # Archive old base images if needed
        # (implemented if you want to keep historical base images)
        
    except Exception as e:
        logger.error(f"Error handling lighting transition: {e}")
        raise

if __name__ == "__main__":
    try:
        # When run directly, capture fresh base images
        current_condition = get_current_lighting_condition()
        capture_base_images(current_condition, force_capture=True)
    except Exception as e:
        logger.error(f"Base image capture failed: {e}")
        raise