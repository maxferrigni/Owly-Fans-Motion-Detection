# File: utilities/constants.py
# Purpose: Centralized path management for the Owl Monitoring System

import os

def get_base_dir():
    """Get the base directory for local file storage"""
    return "/Users/maxferrigni/Insync/maxferrigni@gmail.com/Google Drive/01 - Owl Box/60_IT/20_Motion_Detection"

# Base directory structure
BASE_DIR = get_base_dir()
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
    return COMPARISON_IMAGE_PATHS.get(alert_type)

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
            print(f"Created/verified directory: {directory}")
        except Exception as e:
            print(f"Failed to create directory {directory}: {e}")
            raise

def validate_paths():
    """Validate that all required paths exist"""
    print("Validating paths and directories...")
    
    # Check config files
    for name, path in INPUT_CONFIG_FILES.items():
        if not os.path.exists(path):
            print(f"Configuration file missing: {path}")

    # Log comparison image paths
    print("Comparison image paths configuration:")
    for alert_type, path in COMPARISON_IMAGE_PATHS.items():
        print(f"Alert Type: {alert_type} -> Path: {path}")

    # Check directories
    ensure_directories_exist()
    print("Path validation complete")

if __name__ == "__main__":
    print("Validating directory structure...")
    validate_paths()
    print("Directory validation complete.")