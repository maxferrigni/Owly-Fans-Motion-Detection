# File: utilities/constants.py
# Purpose: Centralized path management and validation for the Owl Monitoring System

import os
import json
import pandas as pd
import logging

# Base directory path definition
BASE_DIR = "/Users/maxferrigni/Insync/maxferrigni@gmail.com/Google Drive/01 - Owl Box/60_IT/20_Motion_Detection"

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

# Camera-specific comparison image paths
COMPARISON_IMAGE_PATHS = {
    "Owl In Box": os.path.join(IMAGE_COMPARISONS_DIR, "owl_in_box_comparison.jpg"),
    "Owl On Box": os.path.join(IMAGE_COMPARISONS_DIR, "owl_on_box_comparison.jpg"),
    "Owl In Area": os.path.join(IMAGE_COMPARISONS_DIR, "owl_in_area_comparison.jpg")
}

# Supabase storage buckets
SUPABASE_STORAGE = {
    "owl_detections": "owl_detections",
    "base_images": "base_images"
}

def get_comparison_image_path(camera_name):
    """Get the comparison image path for a given camera"""
    alert_type = CAMERA_MAPPINGS.get(camera_name)
    if not alert_type:
        raise ValueError(f"No camera mapping found for: {camera_name}")
    
    path = COMPARISON_IMAGE_PATHS.get(alert_type)
    if not path:
        raise ValueError(f"No comparison image path found for alert type: {alert_type}")
    
    return path

def ensure_directories_exist():
    """Create all necessary directories if they don't exist"""
    directories = [
        LOCAL_FILES_DIR,
        BASE_IMAGES_DIR,
        IMAGE_COMPARISONS_DIR,
        LOGS_DIR
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
            
        # Validate comparison image paths
        for alert_type, path in COMPARISON_IMAGE_PATHS.items():
            parent_dir = os.path.dirname(path)
            if not os.path.exists(parent_dir):
                logging.error(f"Comparison image directory missing: {parent_dir}")
                return False
                
        logging.info("System validation completed successfully")
        return True
        
    except Exception as e:
        logging.error(f"System validation failed: {e}")
        return False

def get_base_image_filename(camera_name, lighting_condition, timestamp):
    """Generate filename for base images"""
    return f"{camera_name.lower().replace(' ', '_')}_{lighting_condition}_base_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    validate_system()