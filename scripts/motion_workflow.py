# File: motion_workflow.py
# Purpose:
# This script handles motion detection by comparing base images with new snapshots 
# captured from specified regions of interest (ROIs). It logs motion events and 
# saves snapshots when motion is detected.
# Features:
# - Load base images for motion detection.
# - Capture screenshots from predefined ROIs.
# - Detect motion using luminance and pixel thresholds.
# - Save snapshots and log motion events.

import os
from datetime import datetime
from PIL import Image, ImageChops
import pyautogui
import pytz

# Constants for paths
PACIFIC_TIME = pytz.timezone("America/Los_Angeles")
BASE_PATHS = {
    "input": "./base_images",
    "snapshots": "./snapshots",
}

def load_base_image(camera_name):
    """
    Load the base image for a specific camera.
    """
    base_image_path = os.path.join(BASE_PATHS["input"], f"{camera_name}_base.jpg")
    if not os.path.exists(base_image_path):
        raise FileNotFoundError(f"Base image not found for {camera_name}")
    return Image.open(base_image_path).convert("RGB")

def capture_real_image(roi):
    """
    Capture a screenshot of the region specified by the camera's ROI.
    """
    x, y, width, height = roi
    region = (x, y, width - x, height - y)
    screenshot = pyautogui.screenshot(region=region)
    return screenshot.convert("RGB")

def detect_motion(base_image, new_image, threshold_percentage, luminance_threshold):
    """
    Compare the base image and the new image to detect motion.
    """
    diff = ImageChops.difference(base_image, new_image).convert("L")
    total_pixels = diff.size[0] * diff.size[1]
    significant_pixels = sum(1 for pixel in diff.getdata() if pixel > luminance_threshold)
    avg_luminance_change = sum(diff.getdata()) / total_pixels
    threshold_pixels = total_pixels * threshold_percentage
    motion_detected = significant_pixels > threshold_pixels
    return motion_detected, significant_pixels, avg_luminance_change, total_pixels

def save_snapshot(image, camera_name):
    """
    Save the captured image as a snapshot for the camera.
    """
    snapshot_folder = os.path.join(BASE_PATHS["snapshots"], camera_name)
    os.makedirs(snapshot_folder, exist_ok=True)
    snapshot_name = f"{datetime.now(PACIFIC_TIME).strftime('%Y%m%d%H%M%S')}.jpg"
    snapshot_path = os.path.join(snapshot_folder, snapshot_name)
    image.save(snapshot_path)
    return snapshot_path

def process_camera(camera_name, config):
    """
    Process motion detection for a specific camera.
    Returns a dictionary with detection results for Supabase logging.
    """
    try:
        base_image = load_base_image(camera_name)
        new_image = capture_real_image(config["roi"])
        
        motion_detected, significant_pixels, avg_luminance_change, total_pixels = detect_motion(
            base_image,
            new_image,
            config["threshold_percentage"],
            config["luminance_threshold"],
        )
        
        snapshot_path = save_snapshot(new_image, camera_name) if motion_detected else ""
        pixel_change = significant_pixels / total_pixels
        status = config["alert_type"] if motion_detected else "No Motion"

        # Return detection results for Supabase logging
        result = {
            "status": status,
            "pixel_change": pixel_change,
            "luminance_change": avg_luminance_change,
            "snapshot_path": snapshot_path
        }

        if motion_detected:
            print(f"Motion detected for {camera_name}: {status}. Snapshot saved at {snapshot_path}")
        else:
            print(f"No motion detected for {camera_name}")

        return result

    except Exception as e:
        print(f"Error processing {camera_name}: {e}")
        return {
            "status": "Error",
            "error_message": str(e),
            "pixel_change": 0.0,
            "luminance_change": 0.0,
            "snapshot_path": ""
        }