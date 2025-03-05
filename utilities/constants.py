# File: utilities/constants.py
# Purpose: Centralized path management and validation for the Owl Monitoring System
# 
# March 4, 2025 Update - Version 1.1.0
# - Updated version number
# - Added alert priority constants for single/multiple owls
# - Updated Supabase bucket configuration to use separate buckets for detections and base images
# - Added detection folder structure for owl_detections bucket

import os
import json
import pandas as pd
import logging
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Version information
VERSION = "1.1.0"

# Base directory path from environment variables with fallback
BASE_DIR = os.getenv("BASE_DIR", "/Users/maxferrigni/Insync/maxferrigni@gmail.com/Google Drive/01 - Owl Box/60_IT/20_Motion_Detection")

# Directory structure
LOCAL_FILES_DIR = os.path.join(BASE_DIR, "20_Local_Files")
GIT_DIR = os.path.join(BASE_DIR, "10_GIT", "Owly-Fans-Motion-Detection")

# Git repository paths
SCRIPTS_DIR = os.path.join(GIT_DIR, "scripts")
CONFIGS_DIR = os.path.join(GIT_DIR, "configs")
UTILITIES_DIR = os.path.join(GIT_DIR, "utilities")

# Local storage paths
BASE_IMAGES_DIR = os.path.join(LOCAL_FILES_DIR, "base_images")
IMAGE_COMPARISONS_DIR = os.path.join(LOCAL_FILES_DIR, "image_comparisons")
LOGS_DIR = os.path.join(LOCAL_FILES_DIR, "logs")
SAVED_IMAGES_DIR = os.path.join(LOGS_DIR, "saved_images")  # New folder for saved images when local saving is enabled

# Input config files
INPUT_CONFIG_FILES = {
    "config": os.path.join(CONFIGS_DIR, "config.json"),
    "sunrise_sunset": os.path.join(CONFIGS_DIR, "LA_Sunrise_Sunset.txt")
}

# Camera name to type mapping
CAMERA_MAPPINGS = {
    "Bindy Patio Camera": "Owl On Box",
    "Upper Patio Camera": "Owl In Area",
    "Wyze Internal Camera": "Owl In Box"
}

# Alert priority hierarchy (higher number = higher priority)
# Added in v1.1.0 - Enhanced alert priorities
ALERT_PRIORITIES = {
    "Owl In Area": 1,          # Lowest priority
    "Owl On Box": 2,
    "Owl In Box": 3,
    "Two Owls": 4,             # Multiple owls (except in box)
    "Two Owls In Box": 5,      # Multiple owls in box
    "Eggs Or Babies": 6        # Highest priority (not fully implemented)
}

# Fixed filenames for the limited number of images we keep
BASE_IMAGE_FILENAMES = {
    "day": {
        "Bindy Patio Camera": "bindy_patio_camera_day_base.jpg",
        "Upper Patio Camera": "upper_patio_camera_day_base.jpg",
        "Wyze Internal Camera": "wyze_internal_camera_day_base.jpg"
    },
    "night": {  # Reduced in v1.1.0 - Only day/night instead of 4 conditions
        "Bindy Patio Camera": "bindy_patio_camera_night_base.jpg",
        "Upper Patio Camera": "upper_patio_camera_night_base.jpg",
        "Wyze Internal Camera": "wyze_internal_camera_night_base.jpg"
    }
}

# Fixed filenames for comparison images
COMPARISON_IMAGE_FILENAMES = {
    "Owl In Box": "owl_in_box_comparison.jpg",
    "Owl On Box": "owl_on_box_comparison.jpg",
    "Owl In Area": "owl_in_area_comparison.jpg",
    "Two Owls": "two_owls_comparison.jpg",          # Added in v1.1.0
    "Two Owls In Box": "two_owls_in_box_comparison.jpg",  # Added in v1.1.0
    "Eggs Or Babies": "eggs_or_babies_comparison.jpg"     # Added in v1.1.0
}

# Supabase storage buckets - Updated in v1.1.0 to use separate buckets
SUPABASE_STORAGE = {
    "owl_detections": os.getenv("SUPABASE_BUCKET_DETECTIONS", "owl_detections"),
    "base_images": os.getenv("SUPABASE_BUCKET_IMAGES", "base_images")
}

# Detection folders within the owl_detections bucket - Added in v1.1.0
DETECTION_FOLDERS = {
    "Owl In Area": "owl_in_area",
    "Owl On Box": "owl_on_box", 
    "Owl In Box": "owl_in_box",
    "Two Owls": "two_owls",
    "Two Owls In Box": "two_owls_in_box",
    "Eggs Or Babies": "eggs_or_babies"
}

def get_comparison_image_path(camera_name, alert_type=None, temp=False, timestamp=None):
    """
    Get the comparison image path for a given camera.
    
    Args:
        camera_name (str): Name of the camera
        alert_type (str, optional): Specific alert type, otherwise derived from camera
        temp (bool): Deprecated, kept for backwards compatibility
        timestamp (datetime, optional): Timestamp for unique filenames in saved_images
        
    Returns:
        str: Path to the comparison image
    """
    # If alert_type not provided, derive from camera mapping
    if not alert_type:
        alert_type = CAMERA_MAPPINGS.get(camera_name)
        if not alert_type:
            raise ValueError(f"No camera mapping found for: {camera_name}")
    
    # Use the fixed filename for the main comparison image
    if alert_type in COMPARISON_IMAGE_FILENAMES:
        filename = COMPARISON_IMAGE_FILENAMES[alert_type]
    else:
        # Fallback for unknown alert types
        alert_type_clean = alert_type.lower().replace(' ', '_')
        filename = f"{alert_type_clean}_comparison.jpg"
    
    # Return standard path
    return os.path.join(IMAGE_COMPARISONS_DIR, filename)

def get_saved_image_path(camera_name, image_type, timestamp=None, alert_type=None):
    """
    Get path for saving a copy of an image to the logs folder when local saving is enabled.
    
    Args:
        camera_name (str): Name of the camera
        image_type (str): Type of image ("base" or "comparison")
        timestamp (datetime, optional): Timestamp for unique filename
        alert_type (str, optional): Type of alert for comparison images
        
    Returns:
        str: Path for saved image
    """
    # Make sure we have a timestamp
    if not timestamp:
        timestamp = datetime.now(pytz.timezone('America/Los_Angeles'))
    
    # Format camera name and create a timestamp
    camera_name_clean = camera_name.lower().replace(' ', '_')
    ts_str = timestamp.strftime('%Y%m%d_%H%M%S')
    
    # Create a more descriptive filename
    if image_type == "base":
        filename = f"{camera_name_clean}_base_{ts_str}.jpg"
    else:
        # If alert type provided, use it; otherwise get from camera mapping
        if not alert_type:
            alert_type = CAMERA_MAPPINGS.get(camera_name, "unknown")
        
        alert_type_clean = alert_type.lower().replace(' ', '_')
        filename = f"{camera_name_clean}_{alert_type_clean}_{ts_str}.jpg"
    
    # Ensure directory exists
    os.makedirs(SAVED_IMAGES_DIR, exist_ok=True)
    
    # Return the full path
    return os.path.join(SAVED_IMAGES_DIR, filename)

def get_detection_folder(alert_type):
    """
    Get the folder name for a detection type within the owl_detections bucket.
    Added in v1.1.0
    
    Args:
        alert_type (str): The type of alert/detection
        
    Returns:
        str: Folder name for this detection type
    """
    return DETECTION_FOLDERS.get(alert_type, "other")

def get_base_image_path(camera_name, lighting_condition):
    """
    Get the path for a base image based on camera and lighting condition.
    Uses fixed filenames to limit the number of base images.
    
    Args:
        camera_name (str): Name of the camera
        lighting_condition (str): Lighting condition (day or night in v1.1.0)
        
    Returns:
        str: Path for the base image
    """
    # Simplify lighting conditions to just day/night
    if lighting_condition in ['civil_twilight', 'astronomical_twilight']:
        # In v1.1.0, we don't take base images during transition periods
        return None
        
    # Map lighting condition to day/night only
    if lighting_condition not in ['day', 'night']:
        lighting_condition = 'night' if lighting_condition == 'unknown' else 'day'
    
    # Get the fixed filename for this camera and lighting condition
    if lighting_condition in BASE_IMAGE_FILENAMES and camera_name in BASE_IMAGE_FILENAMES[lighting_condition]:
        filename = BASE_IMAGE_FILENAMES[lighting_condition][camera_name]
    else:
        # Fallback to a default pattern if not found
        camera_name_clean = camera_name.lower().replace(' ', '_')
        filename = f"{camera_name_clean}_{lighting_condition}_base.jpg"
    
    return os.path.join(BASE_IMAGES_DIR, filename)

def ensure_directories_exist():
    """Create all necessary directories if they don't exist"""
    directories = [
        LOCAL_FILES_DIR,
        BASE_IMAGES_DIR,
        IMAGE_COMPARISONS_DIR,
        LOGS_DIR,
        SAVED_IMAGES_DIR
    ]

    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logging.info(f"Created/verified directory: {directory}")
        except Exception as e:
            logging.error(f"Failed to create directory {directory}: {e}")
            raise

def validate_config_files():
    """
    Validate all configuration files exist and are properly formatted.
    
    Returns:
        bool: True if all validations pass
    """
    try:
        # Check config.json
        config_path = INPUT_CONFIG_FILES["config"]
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
            
        with open(config_path, "r") as file:
            config = json.load(file)
            
        # Validate required fields in camera config
        required_fields = ["roi", "threshold_percentage", "luminance_threshold", "alert_type"]
        for camera, settings in config.items():
            missing_fields = [field for field in required_fields if field not in settings]
            if missing_fields:
                raise ValueError(f"Missing required fields {missing_fields} for camera {camera}")
                
        # Check sunrise/sunset data
        sunrise_sunset_path = INPUT_CONFIG_FILES["sunrise_sunset"]
        if not os.path.exists(sunrise_sunset_path):
            raise FileNotFoundError(f"Sunrise/Sunset data file not found: {sunrise_sunset_path}")
            
        # Validate sunrise/sunset data format
        df = pd.read_csv(sunrise_sunset_path, delimiter="\t")
        required_columns = ['Date', 'Sunrise', 'Sunset']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns in sunrise/sunset data: {missing_columns}")
            
        logging.info("All configuration files validated successfully")
        return True
        
    except Exception as e:
        logging.error(f"Configuration validation failed: {e}")
        return False

def validate_system():
    """
    Comprehensive system validation including paths and configs.
    
    Returns:
        bool: True if all validations pass
    """
    try:
        # Ensure all directories exist
        ensure_directories_exist()
        
        # Validate configuration files
        if not validate_config_files():
            return False
            
        logging.info("System validation completed successfully")
        return True
        
    except Exception as e:
        logging.error(f"System validation failed: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    validate_system()
