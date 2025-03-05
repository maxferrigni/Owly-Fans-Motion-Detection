# File: capture_base_images.py
# Purpose: Capture and manage base images for motion detection system
#
# March 4, 2025 Update - Version 1.1.0
# - Limited base image captures to only true day and true night conditions
# - Added transition period handling with appropriate messaging
# - Implemented base image capture on startup during true day/night
# - Updated to use dedicated base_images bucket in Supabase

import os
import pyautogui
from PIL import Image
import json
from datetime import datetime
import pytz
import shutil
import time
import tkinter as tk
from tkinter import messagebox

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
    record_base_image_capture,
    is_transition_period,
    get_lighting_info
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
        # In v1.1.0, we don't handle transition lighting conditions
        if lighting_condition == 'transition':
            logger.info(f"Cannot get base image during transition period")
            raise FileNotFoundError(f"No base image for transition period")
        
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
        # In v1.1.0, we don't save base images during transition periods
        if lighting_condition == 'transition':
            logger.info(f"Skipping base image save during transition period")
            return None, None
        
        # Generate timestamp in consistent format
        timestamp = datetime.now(pytz.timezone('America/Los_Angeles'))
        
        # Get the fixed path for this base image
        base_path = get_base_image_path(camera_name, lighting_condition)
        if not base_path:
            logger.warning(f"No base path available for {camera_name} in {lighting_condition} condition")
            return None, None
        
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

def capture_base_images(lighting_condition=None, force_capture=False, show_ui_message=False):
    """
    Capture new base images for all cameras.
    
    Args:
        lighting_condition (str, optional): Override current lighting condition
        force_capture (bool): Force capture regardless of timing conditions
        show_ui_message (bool): Whether to show UI messages about transition periods
        
    Returns:
        list: List of dictionaries containing capture results
    """
    logger.info("Starting base image capture process...")

    try:
        # Get current lighting condition if not provided
        if not lighting_condition:
            lighting_condition = get_current_lighting_condition()
        
        logger.info(f"Using lighting condition: {lighting_condition}")
        
        # In v1.1.0, we don't capture base images during transition periods
        if lighting_condition == 'transition' and not force_capture:
            message = "Currently in lighting transition period - base images will not be captured until true day or true night"
            logger.info(message)
            
            # Show UI message if requested
            if show_ui_message:
                try:
                    # Use messagebox if tkinter is available
                    messagebox.showinfo("Base Image Capture", message)
                except Exception:
                    # Otherwise just log it
                    logger.debug("Could not show UI message - tkinter may not be initialized")
                
            return []
        
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
                
                # Skip if save failed (could be due to transition period)
                if not local_path:
                    logger.warning(f"Base image save skipped for {camera_name}")
                    continue
                
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
        
        # In v1.1.0, we don't capture during transitions
        if new_condition == 'transition':
            logger.info("Entered transition period - will not capture base images")
            return
            
        # If exiting a transition period to a stable condition
        if old_condition == 'transition' and new_condition in ['day', 'night']:
            # Wait for the new lighting condition to stabilize before capturing
            wait_time = 300  # 5 minutes
            logger.info(f"Exited transition period to {new_condition}. Waiting {wait_time} seconds for lighting to stabilize...")
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

def should_capture_startup_base_images():
    """
    Determine if base images should be captured on startup.
    New in v1.1.0: Capture base images if it's true day or true night when starting up.
    
    Returns:
        bool: True if base images should be captured on startup
    """
    try:
        # Get detailed lighting info
        lighting_info = get_lighting_info()
        condition = lighting_info['condition']
        
        # Only capture if we're in a stable condition (day or night, not transition)
        if condition != 'transition':
            # Check if condition is stable
            if is_lighting_condition_stable():
                logger.info(f"Stable {condition} condition detected at startup - will capture base images")
                return True
            else:
                logger.info(f"Condition {condition} not stable yet - waiting to capture base images")
                return False
        else:
            logger.info("In transition period at startup - will not capture base images")
            return False
            
    except Exception as e:
        logger.error(f"Error checking startup base image capture: {e}")
        return False

def notify_transition_period(root=None):
    """
    Display a notification that we're in a transition period.
    New in v1.1.0 to inform users why base images aren't being captured.
    
    Args:
        root (tk.Tk, optional): Tkinter root window to attach notification to
    """
    try:
        message = "Currently in lighting transition period.\nBase images will only be captured during true day or true night."
        
        if root:
            # If we have a root window, create a proper notification
            from tkinter import Label, RIDGE
            
            # Create a notification frame
            notification = tk.Toplevel(root)
            notification.title("Lighting Transition")
            notification.geometry("400x100")
            notification.resizable(False, False)
            
            # Create notification label
            label = Label(
                notification, 
                text=message,
                font=("Arial", 12),
                padx=20,
                pady=20,
                relief=RIDGE,
                bg="#FFF9E0"  # Light yellow background
            )
            label.pack(fill="both", expand=True)
            
            # Auto-close after 10 seconds
            notification.after(10000, notification.destroy)
            
            # Position next to main window
            if hasattr(root, 'winfo_x') and hasattr(root, 'winfo_y'):
                x = root.winfo_x() + root.winfo_width() // 2 - 200
                y = root.winfo_y() + 100
                notification.geometry(f"+{x}+{y}")
            
            # Make it stay on top
            notification.attributes('-topmost', True)
        else:
            # If no root window, just use messagebox if possible
            try:
                messagebox.showinfo("Lighting Transition", message)
            except Exception:
                # Just log if we can't show a UI message
                logger.info(message)
                
    except Exception as e:
        logger.error(f"Error displaying transition notification: {e}")

if __name__ == "__main__":
    try:
        # When run directly, check the current lighting condition
        current_condition = get_current_lighting_condition()
        
        # In v1.1.0, we check if we're in a transition period
        if is_transition_period():
            logger.info("Currently in transition period - base images will not be captured")
            notify_transition_period()
        else:
            # Only proceed if lighting condition is stable
            if is_lighting_condition_stable():
                capture_base_images(current_condition, force_capture=True, show_ui_message=True)
            else:
                logger.info(f"Lighting condition {current_condition} is not stable, waiting...")
    except Exception as e:
        logger.error(f"Base image capture failed: {e}")
        raise