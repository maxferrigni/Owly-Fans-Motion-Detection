# File: capture_base_images.py
# Purpose: Capture and manage base images for motion detection system

import os
import pyautogui
from PIL import Image
import json
from datetime import datetime
import pytz
import shutil
import time

# Import utilities
from utilities.constants import (
    BASE_IMAGES_DIR,
    CONFIGS_DIR,
    get_base_image_path,
    get_saved_image_path,
)
from utilities.logging_utils import get_logger
from utilities.time_utils import (
    get_current_lighting_condition,
    is_lighting_condition_stable,
    record_base_image_capture
)
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

def get_latest_base_image(camera_name, lighting_condition):
    """
    Get the base image path for a camera and lighting condition.
    Always returns the fixed path for consistency.
    
    Args:
        camera_name (str): Name of the camera
        lighting_condition (str): Current lighting condition
        
    Returns:
        str: Path to the base image
        
    Raises:
        FileNotFoundError: If the base image doesn't exist
    """
    try:
        # Get the fixed path for this camera and lighting condition
        image_path = get_base_image_path(camera_name, lighting_condition)
        
        # Check if the file exists
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"No base image found for {camera_name} under {lighting_condition} condition")
            
        logger.info(f"Using base image: {image_path}")
        return image_path
        
    except Exception as e:
        logger.error(f"Error getting base image: {e}")
        raise

def save_base_image(image, camera_name, lighting_condition):
    """
    Save base image to fixed location and upload to Supabase.
    If local saving is enabled, also save a copy to the saved_images directory.
    
    Args:
        image (PIL.Image): The base image to save
        camera_name (str): Name of the camera
        lighting_condition (str): Current lighting condition
        
    Returns:
        tuple: (local_path, supabase_url)
    """
    try:
        # Generate timestamp in consistent format
        timestamp = datetime.now(pytz.timezone('America/Los_Angeles'))
        
        # Get the fixed path for this base image
        base_path = get_base_image_path(camera_name, lighting_condition)
        
        # Ensure base images directory exists
        os.makedirs(BASE_IMAGES_DIR, exist_ok=True)
        
        # Save to the fixed location
        if image.mode == "RGBA":
            image = image.convert("RGB")
            
        image.save(base_path)
        logger.info(f"Saved base image: {base_path}")
        
        # Check if local saving is enabled to save a copy to logs
        local_saving = os.getenv('OWL_LOCAL_SAVING', 'False').lower() == 'true'
        if local_saving:
            # Save a copy with timestamp to the saved_images folder
            saved_path = get_saved_image_path(camera_name, "base", timestamp)
            image.save(saved_path)
            logger.info(f"Saved copy to logs: {saved_path}")
        
        # Upload to Supabase with consistent timestamp format
        supabase_filename = f"{camera_name.lower().replace(' ', '_')}_{lighting_condition}_base_{timestamp.strftime('%Y%m%d%H%M%S')}.jpg"
        supabase_url = upload_base_image(base_path, supabase_filename, camera_name, lighting_condition)
        
        # Record that we captured a base image
        record_base_image_capture(lighting_condition)
        
        return base_path, supabase_url
        
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
        
        # Check if lighting condition is stable and it's a good time to capture
        if not force_capture and not is_lighting_condition_stable():
            logger.info(f"Lighting condition {lighting_condition} is not stable yet, skipping base image capture")
            return []
        
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
                    'lighting_condition': lighting_condition,
                    'timestamp': datetime.now(pytz.timezone('America/Los_Angeles')).isoformat(),
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
        
        # Wait for the new lighting condition to stabilize before capturing
        wait_time = 300  # 5 minutes
        logger.info(f"Waiting {wait_time} seconds for lighting to stabilize...")
        time.sleep(wait_time)
        
        # Only capture if the lighting condition is still the same after waiting
        current_condition = get_current_lighting_condition()
        if current_condition == new_condition:
            # Capture new base images for the new lighting condition
            capture_base_images(lighting_condition=new_condition, force_capture=True)
        else:
            logger.info(f"Lighting condition changed again to {current_condition}, skipping capture")
        
    except Exception as e:
        logger.error(f"Error handling lighting transition: {e}")
        raise

if __name__ == "__main__":
    try:
        # When run directly, capture fresh base images
        current_condition = get_current_lighting_condition()
        
        # Only proceed if lighting condition is stable
        if is_lighting_condition_stable():
            capture_base_images(current_condition, force_capture=True)
        else:
            logger.info(f"Lighting condition {current_condition} is not stable, waiting...")
    except Exception as e:
        logger.error(f"Base image capture failed: {e}")
        raise