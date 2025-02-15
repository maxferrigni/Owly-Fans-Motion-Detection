# File: capture_base_images.py
# Purpose: Capture and manage base images for motion detection system

import os
import pyautogui
from PIL import Image
import json
from datetime import datetime
import numpy as np
import pytz

# Import utilities
from utilities.constants import (
    BASE_IMAGES_DIR,
    CONFIGS_DIR,
    get_base_image_filename,
    SUPABASE_STORAGE
)
from utilities.logging_utils import get_logger
from push_to_supabase import supabase_client

# Initialize logger
logger = get_logger()

def calculate_average_luminance(image):
    """Calculate the average luminance of an image"""
    try:
        # Convert image to numpy array
        img_array = np.array(image)
        # Convert to grayscale using standard luminance formula
        luminance = 0.299 * img_array[:,:,0] + 0.587 * img_array[:,:,1] + 0.114 * img_array[:,:,2]
        return float(np.mean(luminance))
    except Exception as e:
        logger.error(f"Error calculating luminance: {e}")
        return 0.0

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
    Save base image locally and to Supabase.
    
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
        with open(local_path, 'rb') as f:
            supabase_response = supabase_client.storage \
                .from_(SUPABASE_STORAGE['base_images']) \
                .upload(filename, f)
        
        # Generate public URL
        supabase_url = f"{supabase_client.storage.get_public_url(SUPABASE_STORAGE['base_images'], filename)}"
        
        # Log to base_images_log table
        light_level = calculate_average_luminance(image)
        log_entry = {
            'camera_name': camera_name,
            'lighting_condition': lighting_condition,
            'base_image_url': supabase_url,
            'light_level': light_level,
            'capture_time': timestamp.strftime('%H:%M:%S'),
            'capture_date': timestamp.strftime('%Y-%m-%d'),
            'notes': f'Auto-captured during {lighting_condition} condition'
        }
        
        supabase_client.table('base_images_log').insert(log_entry).execute()
        logger.info(f"Base image logged to Supabase: {filename}")
        
        return local_path, supabase_url
        
    except Exception as e:
        logger.error(f"Error saving base image: {e}")
        raise

def clear_local_base_images():
    """Clear old base images from local storage"""
    if os.path.exists(BASE_IMAGES_DIR):
        for file_name in os.listdir(BASE_IMAGES_DIR):
            file_path = os.path.join(BASE_IMAGES_DIR, file_name)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    logger.info(f"Deleted local base image: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {e}")

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