
# File: capture_base_images.py
# Purpose:
# This script captures and saves base images for each configured camera in the owl monitoring system.
# These base images are used as reference points for motion detection and comparison.
# Features:
# - Loads camera configurations from config.json
# - Captures screenshots based on defined ROIs
# - Clears existing base images before capture
# - Saves images with consistent naming convention
# Typical Usage:
# Run this script to update base images for all cameras:
# `python capture_base_images.py`
# Base images will be saved to the configured input base path


import os
import pyautogui
from PIL import Image
import json

# Paths
INPUT_BASE_PATH = "/Users/maxferrigni/Insync/maxferrigni@gmail.com/Google Drive/01 - Owl Box/60 IT/20 Motion Detection/20 Input Files/60 Camera Base Images"

# Load camera configurations from the JSON file
def load_config():
    config_path = "./20 configs/config.json"
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, 'r') as f:
        return json.load(f)

# Capture an image from the screen based on the ROI
def capture_real_image(roi):
    x, y, width, height = roi
    width = abs(width - x)
    height = abs(height - y)
    print(f"Capturing screenshot: x={x}, y={y}, width={width}, height={height}")
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid ROI dimensions: {roi}")
    return pyautogui.screenshot(region=(x, y, width, height))

# Save base image with a consistent name
def save_base_image(image, camera_name):
    base_folder = INPUT_BASE_PATH
    os.makedirs(base_folder, exist_ok=True)  # Ensure the folder exists
    base_image_path = os.path.join(base_folder, f"{camera_name.replace(' ', '_')}_Base.jpg")
    if image.mode == "RGBA":
        image = image.convert("RGB")
    image.save(base_image_path)
    print(f"Saved base image for {camera_name} at: {base_image_path}")
    return base_image_path

# Delete all existing base images
def clear_base_images():
    if os.path.exists(INPUT_BASE_PATH):
        for file_name in os.listdir(INPUT_BASE_PATH):
            file_path = os.path.join(INPUT_BASE_PATH, file_name)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    print(f"Deleted: {file_path}")
            except Exception as e:
                print(f"Error deleting file {file_path}: {e}")

# Main function to capture base images for all cameras
def capture_base_images():
    print("Starting base image capture...")

    # Clear existing base images
    print("Clearing existing base images...")
    clear_base_images()

    configs = load_config()
    
    for camera_name, config in configs.items():
        if config["roi"] is None:
            print(f"Skipping {camera_name}: No ROI defined.")
            continue
        
        print(f"Capturing base image for {camera_name}...")
        roi = config["roi"]
        base_image = capture_real_image(roi)
        save_base_image(base_image, camera_name)
    
    print("Base image capture completed.")

if __name__ == "__main__":
    capture_base_images()
