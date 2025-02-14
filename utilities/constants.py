# File: utilities/constants.py
# Purpose: Centralized path management for the Owl Monitoring System

import os

def get_base_dir():
    """Get the base directory (20_Motion_Detection) by traversing up from the script location"""
    current_dir = os.path.dirname(os.path.abspath(__file__))  # /utilities
    git_repo_dir = os.path.dirname(current_dir)              # /Owly-Fans-Motion-Detection
    git_dir = os.path.dirname(git_repo_dir)                 # /10_GIT
    return os.path.dirname(git_dir)                         # /20_Motion_Detection

# Base directory structure
BASE_DIR = get_base_dir()
INPUT_DIR = os.path.join(BASE_DIR, "20_Input_Files")
OUTPUT_DIR = os.path.join(BASE_DIR, "30_Output_Files")
GIT_DIR = os.path.join(BASE_DIR, "10_GIT", "Owly-Fans-Motion-Detection")

# Git repository paths
SCRIPTS_DIR = os.path.join(GIT_DIR, "scripts")
CONFIGS_DIR = os.path.join(GIT_DIR, "configs")
UTILITIES_DIR = os.path.join(GIT_DIR, "utilities")

# Input paths
BASE_IMAGES_DIR = os.path.join(INPUT_DIR, "base_images")
INPUT_CONFIG_FILES = {
    "config": os.path.join(CONFIGS_DIR, "config.json"),
    "sunrise_sunset": os.path.join(CONFIGS_DIR, "LA_Sunrise_Sunset.txt")
}

# Output paths
SNAPSHOTS_DIR = os.path.join(OUTPUT_DIR, "snapshots")
LOGS_DIR = os.path.join(OUTPUT_DIR, "logs")

# Camera name to type mapping
CAMERA_MAPPINGS = {
    "Bindy Patio Camera": "Owl On Box",
    "Upper Patio Camera": "Owl In Area",
    "Wyze Internal Camera": "Owl In Box"
}

# Camera-specific snapshot directories
CAMERA_SNAPSHOT_DIRS = {
    "Owl In Box": os.path.join(SNAPSHOTS_DIR, "owl_in_box"),
    "Owl On Box": os.path.join(SNAPSHOTS_DIR, "owl_on_box"),
    "Owl In Area": os.path.join(SNAPSHOTS_DIR, "owl_in_area")
}

def ensure_directories_exist():
    """Create all necessary directories if they don't exist"""
    directories = [
        INPUT_DIR,
        OUTPUT_DIR,
        BASE_IMAGES_DIR,
        SNAPSHOTS_DIR,
        LOGS_DIR,
    ] + list(CAMERA_SNAPSHOT_DIRS.values())

    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            print(f"Failed to create directory {directory}: {e}")
            raise

def validate_paths():
    """Validate that all required paths exist"""
    # Check config files
    for name, path in INPUT_CONFIG_FILES.items():
        if not os.path.exists(path):
            print(f"Configuration file missing: {path}")

    # Check directories
    ensure_directories_exist()

if __name__ == "__main__":
    print("Validating directory structure...")
    validate_paths()
    print("Directory validation complete.")