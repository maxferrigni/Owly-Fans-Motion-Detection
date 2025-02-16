# File: capture_base_images.py
# Purpose: Capture and manage base images for motion detection system

import os
import pyautogui
from PIL import Image
import json
from datetime import datetime
import pytz

# Import utilities
from utilities.constants import (
    BASE_IMAGES_DIR,
    CONFIGS_DIR,
    get_base_image_filename
)
from utilities.logging_utils import get_logger
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
    """Capture a screenshot of the specified region"""
    x, y, width, height = roi
    width = abs(width - x)
    height = abs(height - y)
    logger.info(f"Capturing screenshot: x={x}, y={y}, width={width}, height={height}")
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid ROI dimensions: {roi}")
    return pyautogui.screenshot(region=(x, y, width, height))

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
        
        # Clean up old base images for this camera and lighting condition
        cleanup_old_base_images(camera_name, lighting_condition)
        
        return local_path, supabase_url
        
    except Exception as e:
        logger.error(f"Error saving base image: {e}")
        raise

def cleanup_old_base_images(camera_name, lighting_condition):
    """
    Remove old base images for a specific camera and lighting condition.
    Keep only the most recent one.
    
    Args:
        camera_name (str): Name of the camera
        lighting_condition (str): Lighting condition
    """
    try:
        pattern = f"{camera_name.lower().replace(' ', '_')}_{lighting_condition}_base_*.jpg"
        matching_files = [f for f in os.listdir(BASE_IMAGES_DIR) 
                         if f.startswith(camera_name.lower().replace(' ', '_')) and 
                         lighting_condition in f]
        
        # Sort by creation time
        matching_files.sort(key=lambda x: os.path.getctime(
            os.path.join(BASE_IMAGES_DIR, x)
        ))
        
        # Keep only the most recent file
        for old_file in matching_files[:-1]:
            try:
                os.remove(os.path.join(BASE_IMAGES_DIR, old_file))
                logger.info(f"Removed old base image: {old_file}")
            except Exception as e:
                logger.error(f"Error removing old base image {old_file}: {e}")
                
    except Exception as e:
        logger.error(f"Error cleaning up old base images: {e}")

def capture_base_images(lighting_condition):
    """
    Capture new base images for all cameras.
    
    Args:
        lighting_condition (str): Current lighting condition
    """
    logger.info(f"Starting base image capture for {lighting_condition} condition...")

    try:
        configs = load_config()
        results = []
        
        for camera_name, config in configs.items():
            if config["roi"] is None:
                logger.warning(f"Skipping {camera_name}: No ROI defined.")
                continue
            
            logger.info(f"Capturing base image for {camera_name}...")
            
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
                'supabase_url': supabase_url
            })
        
        logger.info("Base image capture completed successfully.")
        return results
        
    except Exception as e:
        logger.error(f"Error during base image capture: {e}")
        raise

if __name__ == "__main__":
    try:
        from utilities.time_utils import get_current_lighting_condition
        current_condition = get_current_lighting_condition()
        capture_base_images(current_condition)
    except Exception as e:
        logger.error(f"Base image capture failed: {e}")
        raise