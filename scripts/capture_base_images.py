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
    get_base_image_filename
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

def clear_old_base_images(camera_name, lighting_condition):
    """
    Clear existing base images for a specific camera and lighting condition.
    
    Args:
        camera_name (str): Name of the camera
        lighting_condition (str): Lighting condition to clear
    """
    try:
        if not os.path.exists(BASE_IMAGES_DIR):
            return

        base_pattern = f"{camera_name.lower().replace(' ', '_')}_{lighting_condition}_base"
        
        for filename in os.listdir(BASE_IMAGES_DIR):
            if filename.startswith(base_pattern):
                file_path = os.path.join(BASE_IMAGES_DIR, filename)
                os.remove(file_path)
                logger.info(f"Removed base image: {filename}")
    except Exception as e:
        logger.error(f"Error clearing old base images: {e}")

def get_latest_base_image(camera_name, lighting_condition):
    """
    Get the most recent base image path for a camera and lighting condition.
    
    Args:
        camera_name (str): Name of the camera
        lighting_condition (str): Current lighting condition
        
    Returns:
        str: Path to the most recent base image
        
    Raises:
        FileNotFoundError: If no matching base image is found
    """
    try:
        # Format camera name for filename matching
        base_pattern = f"{camera_name.lower().replace(' ', '_')}_{lighting_condition}_base"
        
        if not os.path.exists(BASE_IMAGES_DIR):
            os.makedirs(BASE_IMAGES_DIR, exist_ok=True)
            
        matching_files = [
            f for f in os.listdir(BASE_IMAGES_DIR) 
            if f.startswith(base_pattern)
        ]
        
        if matching_files:
            # Get most recent file
            latest_file = max(
                matching_files,
                key=lambda f: os.path.getctime(os.path.join(BASE_IMAGES_DIR, f))
            )
            
            image_path = os.path.join(BASE_IMAGES_DIR, latest_file)
            logger.info(f"Using base image: {image_path}")
            
            return image_path
        
        raise FileNotFoundError(
            f"No base image found for {camera_name} under {lighting_condition} condition"
        )
        
    except Exception as e:
        logger.error(f"Error getting latest base image: {e}")
        raise

def save_base_image(image, camera_name, lighting_condition):
    """
    Save base image locally (if enabled) and upload to Supabase.
    
    Args:
        image (PIL.Image): The base image to save
        camera_name (str): Name of the camera
        lighting_condition (str): Current lighting condition
        
    Returns:
        tuple: (local_path, supabase_url)
    """
    try:
        # Check if local saving is enabled
        local_saving = os.getenv('OWL_LOCAL_SAVING', 'False').lower() == 'true'
        local_path = None
        
        # Generate timestamp in consistent format
        timestamp = datetime.now(pytz.timezone('America/Los_Angeles'))
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
        
        # Generate standardized filename
        camera_name_clean = camera_name.lower().replace(' ', '_')
        filename = f"{camera_name_clean}_{lighting_condition}_base_{timestamp_str}.jpg"
        
        # Save locally if enabled
        if local_saving:
            # Ensure base images directory exists
            os.makedirs(BASE_IMAGES_DIR, exist_ok=True)
            
            # Save locally
            local_path = os.path.join(BASE_IMAGES_DIR, filename)
            if image.mode == "RGBA":
                image = image.convert("RGB")
            image.save(local_path)
            logger.info(f"Saved base image locally: {local_path}")
        else:
            # Create temporary file just for Supabase upload
            os.makedirs(BASE_IMAGES_DIR, exist_ok=True)
            temp_path = os.path.join(BASE_IMAGES_DIR, "temp_" + filename)
            if image.mode == "RGBA":
                image = image.convert("RGB")
            image.save(temp_path)
            local_path = temp_path
        
        # Upload to Supabase with consistent timestamp format
        supabase_filename = f"{camera_name_clean}_{lighting_condition}_base_{timestamp.strftime('%Y%m%d%H%M%S')}.jpg"
        supabase_url = upload_base_image(local_path, supabase_filename, camera_name, lighting_condition)
        
        # Record that we captured a base image
        record_base_image_capture(lighting_condition)
        
        # Clean up temporary file if local saving is disabled
        if not local_saving and os.path.exists(local_path):
            os.remove(local_path)
        
        return local_path if local_saving else None, supabase_url
        
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
                # Clear old base images for this camera and lighting condition
                if os.getenv('OWL_LOCAL_SAVING', 'False').lower() == 'true':
                    clear_old_base_images(camera_name, lighting_condition)
                
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