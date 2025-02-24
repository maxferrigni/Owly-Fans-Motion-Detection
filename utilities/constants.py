# File: utilities/constants.py
# Purpose: Centralized path management and validation for the Owl Monitoring System

import os
import json
import pandas as pd
import logging
from datetime import datetime
import pytz

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

# Temporary storage paths for non-local saving mode
TEMP_DIR = os.path.join(LOCAL_FILES_DIR, "temp")
TEMP_BASE_IMAGES_DIR = os.path.join(TEMP_DIR, "base_images")
TEMP_COMPARISONS_DIR = os.path.join(TEMP_DIR, "comparisons")

# NEW: Archival storage path for saved comparisons
ARCHIVE_DIR = os.path.join(LOCAL_FILES_DIR, "archived_detections")

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

# Camera-specific comparison image paths (using standardized naming)
COMPARISON_IMAGE_PATHS = {
    "Owl In Box": os.path.join(IMAGE_COMPARISONS_DIR, "owl_in_box_comparison.jpg"),
    "Owl On Box": os.path.join(IMAGE_COMPARISONS_DIR, "owl_on_box_comparison.jpg"),
    "Owl In Area": os.path.join(IMAGE_COMPARISONS_DIR, "owl_in_area_comparison.jpg")
}

# Temporary comparison image paths
TEMP_COMPARISON_PATHS = {
    "Owl In Box": os.path.join(TEMP_COMPARISONS_DIR, "temp_owl_in_box_comparison.jpg"),
    "Owl On Box": os.path.join(TEMP_COMPARISONS_DIR, "temp_owl_on_box_comparison.jpg"),
    "Owl In Area": os.path.join(TEMP_COMPARISONS_DIR, "temp_owl_in_area_comparison.jpg")
}

# Supabase storage buckets
SUPABASE_STORAGE = {
    "owl_detections": "owl_detections",
    "base_images": "base_images"
}

def get_comparison_image_path(camera_name, temp=False, timestamp=None):
    """
    Get the comparison image path for a given camera.
    Uses temporary path if local saving is disabled or temp=True.
    If timestamp is provided, generates an archived path.
    
    Args:
        camera_name (str): Name of the camera
        temp (bool): Whether to use temporary directory
        timestamp (datetime, optional): Timestamp for archived images
        
    Returns:
        str: Path to the comparison image
    """
    alert_type = CAMERA_MAPPINGS.get(camera_name)
    if not alert_type:
        raise ValueError(f"No camera mapping found for: {camera_name}")
    
    # If timestamp provided, generate archived path with timestamp
    if timestamp:
        return get_archive_comparison_path(camera_name, timestamp)
    
    # Determine if using temporary path
    if temp or not os.getenv('OWL_LOCAL_SAVING', 'False').lower() == 'true':
        path = TEMP_COMPARISON_PATHS.get(alert_type)
    else:
        # Generate standardized path in the comparisons directory
        alert_type_clean = alert_type.lower().replace(" ", "_")
        camera_name_clean = camera_name.lower().replace(" ", "_")
        timestamp_str = datetime.now(pytz.timezone('America/Los_Angeles')).strftime("%Y%m%d_%H%M%S")
        filename = f"{camera_name_clean}_{alert_type_clean}_{timestamp_str}_comparison.jpg"
        path = os.path.join(IMAGE_COMPARISONS_DIR, filename)
    
    if not path:
        raise ValueError(f"No comparison image path found for alert type: {alert_type}")
    
    return path

# Function to generate archival path for comparison images
def get_archive_comparison_path(camera_name, timestamp):
    """
    Generate path for archived comparison image with timestamp-based organization.
    
    Args:
        camera_name (str): Name of the camera
        timestamp (datetime): Timestamp of the detection
        
    Returns:
        str: Full path for archived comparison image
    """
    # Format camera name
    camera_name_clean = camera_name.lower().replace(" ", "_")
    
    # Use simple flat organization
    # Format: archived_detections/camera_name_alerttype_YYYYMMDD_HHMMSS_comparison.jpg
    alert_type = CAMERA_MAPPINGS.get(camera_name, "unknown")
    alert_type_clean = alert_type.lower().replace(" ", "_")
    
    filename = f"{camera_name_clean}_{alert_type_clean}_{timestamp.strftime('%Y%m%d_%H%M%S')}_comparison.jpg"
    
    return os.path.join(ARCHIVE_DIR, filename)

def get_base_image_path(camera_name, lighting_condition, temp=False):
    """
    Get the base image directory path based on camera and lighting condition.
    Uses temporary path if local saving is disabled or temp=True.
    
    Args:
        camera_name (str): Name of the camera
        lighting_condition (str): Lighting condition (day, civil_twilight, etc.)
        temp (bool): Whether to use temporary directory
        
    Returns:
        str: Directory path for storing base images
    """
    if temp or not os.getenv('OWL_LOCAL_SAVING', 'False').lower() == 'true':
        return TEMP_BASE_IMAGES_DIR
    return BASE_IMAGES_DIR

def get_base_image_filename(camera_name, lighting_condition, timestamp=None):
    """
    Generate standardized filename for base images.
    
    Args:
        camera_name (str): Name of the camera
        lighting_condition (str): Current lighting condition
        timestamp (datetime, optional): Timestamp to use, defaults to current time
        
    Returns:
        str: Standardized filename for base image
    """
    if not timestamp:
        timestamp = datetime.now(pytz.timezone('America/Los_Angeles'))
        
    camera_name_clean = camera_name.lower().replace(" ", "_")
    return f"{camera_name_clean}_{lighting_condition}_base_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"

def ensure_directories_exist():
    """Create all necessary directories if they don't exist"""
    directories = [
        LOCAL_FILES_DIR,
        BASE_IMAGES_DIR,
        IMAGE_COMPARISONS_DIR,
        LOGS_DIR,
        TEMP_DIR,
        TEMP_BASE_IMAGES_DIR,
        TEMP_COMPARISONS_DIR,
        ARCHIVE_DIR
    ]

    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logging.info(f"Created/verified directory: {directory}")
        except Exception as e:
            logging.error(f"Failed to create directory {directory}: {e}")
            raise

def cleanup_temp_files(older_than_days=1):
    """
    Clean up temporary files if they exist.
    
    Args:
        older_than_days (int): Remove files older than this many days
    """
    try:
        import time
        from datetime import timedelta
        
        # Current time minus days
        cutoff_time = time.time() - (older_than_days * 86400)
        
        # Only clean if local saving is disabled
        if not os.getenv('OWL_LOCAL_SAVING', 'False').lower() == 'true':
            if os.path.exists(TEMP_DIR):
                for root, dirs, files in os.walk(TEMP_DIR, topdown=False):
                    for name in files:
                        try:
                            file_path = os.path.join(root, name)
                            # Check file age
                            if os.path.getctime(file_path) < cutoff_time:
                                os.remove(file_path)
                                logging.debug(f"Removed temporary file: {name}")
                        except Exception as e:
                            logging.error(f"Failed to remove temporary file {name}: {e}")
    except Exception as e:
        logging.error(f"Error during temporary file cleanup: {e}")

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
    
        # Check for archive directories
        if not os.path.exists(ARCHIVE_DIR):
            os.makedirs(ARCHIVE_DIR, exist_ok=True)
            
        logging.info("System validation completed successfully")
        return True
        
    except Exception as e:
        logging.error(f"System validation failed: {e}")
        return False
    if __name__ == "__main__":
        logging.basicConfig(level=logging.INFO)
    validate_system()
    cleanup_temp_files()