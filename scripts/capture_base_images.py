# File: capture_base_images.py
# Purpose: Capture and manage base images for motion detection system
#
# March 6, 2025 Update - Version 1.2.1
# - Modified to allow base image captures during transition periods
# - Added separation between "pure" condition base images and transition images
# - Updated messaging to reflect transition window of 30 minutes
# - Added additional image annotation for transition period captures

import os
import pyautogui
from PIL import Image, ImageDraw, ImageFont
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
    get_lighting_info,
    is_pure_lighting_condition,  # New in v1.2.1
    format_time_until,  # New in v1.2.1
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
    Updated in v1.2.1 to handle pure and transition condition images.
    
    Args:
        camera_name (str): Name of the camera
        lighting_condition (str): Current lighting condition
        
    Returns:
        str: Path to the base image
        
    Raises:
        FileNotFoundError: If the base image doesn't exist
    """
    try:
        # Get the fixed path for this camera and lighting condition
        image_path = get_base_image_path(camera_name, lighting_condition)
        
        # Check if the file exists
        if not os.path.exists(image_path):
            # In v1.2.1, if transition image doesn't exist, fall back to the closest pure condition
            if lighting_condition == 'transition':
                # Try to determine if it's closer to day or night based on lighting info
                lighting_info = get_lighting_info()
                detailed = lighting_info.get('detailed_condition', '')
                
                # If it's dawn, try night first then day
                if detailed == 'dawn':
                    try:
                        night_path = get_base_image_path(camera_name, 'night')
                        if os.path.exists(night_path):
                            logger.info(f"Using night base image for dawn transition: {night_path}")
                            return night_path
                    except:
                        pass
                    
                    try:
                        day_path = get_base_image_path(camera_name, 'day')
                        if os.path.exists(day_path):
                            logger.info(f"Using day base image for dawn transition: {day_path}")
                            return day_path
                    except:
                        pass
                
                # If it's dusk, try day first then night
                elif detailed == 'dusk':
                    try:
                        day_path = get_base_image_path(camera_name, 'day')
                        if os.path.exists(day_path):
                            logger.info(f"Using day base image for dusk transition: {day_path}")
                            return day_path
                    except:
                        pass
                    
                    try:
                        night_path = get_base_image_path(camera_name, 'night')
                        if os.path.exists(night_path):
                            logger.info(f"Using night base image for dusk transition: {night_path}")
                            return night_path
                    except:
                        pass
            
            # If we get here, we couldn't find a suitable base image
            raise FileNotFoundError(f"No base image found for {camera_name} under {lighting_condition} condition")
            
        logger.info(f"Using base image: {image_path}")
        return image_path
        
    except Exception as e:
        logger.error(f"Error getting base image: {e}")
        raise

def add_lighting_annotation(image, lighting_condition, is_transition=False):
    """
    Add an annotation to the image indicating its lighting condition.
    New in v1.2.1 to differentiate pure vs. transition conditions.
    
    Args:
        image (PIL.Image): The image to annotate
        lighting_condition (str): The lighting condition
        is_transition (bool): Whether this is a transition period image
        
    Returns:
        PIL.Image: The annotated image
    """
    try:
        # Create a copy to avoid modifying the original
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        
        # Get image dimensions
        width, height = image.size
        
        # Try to load a font, fall back to default if not available
        try:
            font = ImageFont.truetype("Arial.ttf", 16)
        except:
            font = ImageFont.load_default()
        
        # Format timestamp with timezone
        timestamp = datetime.now(pytz.timezone('America/Los_Angeles')).strftime("%Y-%m-%d %H:%M:%S %Z")
        
        # Different annotations for pure vs transition conditions
        if is_transition:
            # Get more detailed lighting information
            lighting_info = get_lighting_info()
            detailed = lighting_info.get('detailed_condition', 'unknown')
            progress = lighting_info.get('transition_percentage', 0)
            
            # Draw background for better visibility
            draw.rectangle([0, 0, width, 40], fill=(0, 0, 0, 128))
            
            # Draw condition text
            condition_text = f"TRANSITION ({detailed.upper()}) - {progress:.1f}% complete"
            draw.text((10, 5), condition_text, fill=(255, 200, 0), font=font)
            
            # Draw timestamp
            draw.text((10, 22), timestamp, fill=(255, 255, 255), font=font)
            
            # Add countdown info if available
            if detailed == 'dawn':
                if lighting_info['countdown']['to_true_day'] is not None:
                    countdown = format_time_until(lighting_info['countdown']['to_true_day'])
                    draw.text((width - 150, 5), f"True Day in: {countdown}", fill=(255, 200, 0), font=font)
            elif detailed == 'dusk':
                if lighting_info['countdown']['to_true_night'] is not None:
                    countdown = format_time_until(lighting_info['countdown']['to_true_night'])
                    draw.text((width - 160, 5), f"True Night in: {countdown}", fill=(255, 200, 0), font=font)
                    
        else:
            # Pure condition - simpler annotation
            draw.rectangle([0, 0, width, 25], fill=(0, 0, 0, 128))
            condition_text = f"{lighting_condition.upper()} - PURE CONDITION"
            draw.text((10, 5), condition_text, fill=(0, 255, 0), font=font)
            
        return annotated
        
    except Exception as e:
        logger.warning(f"Error adding annotation: {e}")
        return image  # Return original if annotation fails

def save_base_image(image, camera_name, lighting_condition):
    """
    Save base image to fixed location and upload to Supabase.
    If local saving is enabled, also save a copy to the saved_images directory.
    Updated in v1.2.1 to handle transition images and add annotations.
    
    Args:
        image (PIL.Image): The base image to save
        camera_name (str): Name of the camera
        lighting_condition (str): Current lighting condition
        
    Returns:
        tuple: (local_path, supabase_url)
    """
    try:
        # Generate timestamp in consistent format
        timestamp = datetime.now(pytz.timezone('America/Los_Angeles'))
        
        # Get the fixed path for this base image
        base_path = get_base_image_path(camera_name, lighting_condition)
        if not base_path:
            logger.warning(f"No base path available for {camera_name} in {lighting_condition} condition")
            return None, None
        
        # Ensure base images directory exists
        os.makedirs(BASE_IMAGES_DIR, exist_ok=True)
        
        # Check if we're in a transition period
        is_transition = lighting_condition == 'transition'
        
        # Add annotation based on lighting condition
        annotated_image = add_lighting_annotation(image, lighting_condition, is_transition)
        
        # Save to the fixed location
        if annotated_image.mode == "RGBA":
            annotated_image = annotated_image.convert("RGB")
            
        annotated_image.save(base_path)
        logger.info(f"Saved base image: {base_path}")
        
        # Check if local saving is enabled to save a copy to logs
        local_saving = os.getenv('OWL_LOCAL_SAVING', 'False').lower() == 'true'
        if local_saving:
            # Save a copy with timestamp to the saved_images folder
            saved_path = get_saved_image_path(camera_name, "base", timestamp)
            annotated_image.save(saved_path)
            logger.info(f"Saved copy to logs: {saved_path}")
        
        # Upload to Supabase with consistent timestamp format
        condition_label = lighting_condition
        if is_transition:
            # Add more specificity for transition uploads
            lighting_info = get_lighting_info()
            detailed = lighting_info.get('detailed_condition', '')
            condition_label = f"transition_{detailed}"
            
        supabase_filename = f"{camera_name.lower().replace(' ', '_')}_{condition_label}_base_{timestamp.strftime('%Y%m%d%H%M%S')}.jpg"
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
    Updated in v1.2.1 to handle transition periods and pure condition tracking.
    
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
        
        # Check if lighting condition is stable and it's a good time to capture
        # In v1.2.1, we can still capture during transitions if timing is right
        if not force_capture:
            should_capture, condition = should_capture_base_image()
            if not should_capture:
                logger.info(f"Not the optimal time to capture base images, skipping")
                return []
        
        # Check if we're in a transition period
        is_transition = lighting_condition == 'transition'
        
        # Check if this is a pure lighting condition
        is_pure = is_pure_lighting_condition()
        
        # Log diagnostic information
        if is_transition:
            logger.info(f"Capturing base images during transition period (pure condition: {is_pure})")
            
            # Show UI message if requested and in transition
            if show_ui_message:
                try:
                    # Get lighting information for countdown
                    lighting_info = get_lighting_info()
                    detailed = lighting_info.get('detailed_condition', 'unknown')
                    progress = lighting_info.get('transition_percentage', 0)
                    
                    # Create appropriate message based on timing
                    if detailed == 'dawn':
                        countdown_text = ""
                        if lighting_info['countdown']['to_true_day'] is not None:
                            countdown = format_time_until(lighting_info['countdown']['to_true_day'])
                            countdown_text = f"\nTime until true day: {countdown}"
                        
                        message = (f"Capturing base images during dawn transition period.\n"
                                  f"Current progress: {progress:.1f}% complete{countdown_text}\n\n"
                                  f"These images will be marked as transition images.")
                    elif detailed == 'dusk':
                        countdown_text = ""
                        if lighting_info['countdown']['to_true_night'] is not None:
                            countdown = format_time_until(lighting_info['countdown']['to_true_night'])
                            countdown_text = f"\nTime until true night: {countdown}"
                        
                        message = (f"Capturing base images during dusk transition period.\n"
                                  f"Current progress: {progress:.1f}% complete{countdown_text}\n\n"
                                  f"These images will be marked as transition images.")
                    else:
                        message = "Capturing base images during transition period."
                    
                    # Use messagebox if tkinter is available
                    messagebox.showinfo("Base Image Capture", message)
                except Exception:
                    # Otherwise just log it
                    logger.debug("Could not show UI message - tkinter may not be initialized")
        elif is_pure:
            logger.info(f"Capturing base images during pure {lighting_condition} condition")
        
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
                
                # Check if save was successful
                if not local_path:
                    logger.warning(f"Base image save failed for {camera_name}")
                    continue
                
                results.append({
                    'camera': camera_name,
                    'local_path': local_path,
                    'supabase_url': supabase_url,
                    'lighting_condition': lighting_condition,
                    'is_transition': is_transition,
                    'is_pure': is_pure,
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
    Updated in v1.2.1 to handle new transition logic.
    
    Args:
        old_condition (str): Previous lighting condition
        new_condition (str): New lighting condition
    """
    try:
        logger.info(f"Handling lighting transition: {old_condition} -> {new_condition}")
        
        # Handle entering a transition period
        if new_condition == 'transition':
            logger.info("Entered transition period - will capture transition-specific base images")
            
            # Capture base images for the transition period
            # Enable force_capture to ensure we get images at the start of transition
            capture_base_images(lighting_condition=new_condition, force_capture=True)
            return
            
        # If exiting a transition period to a stable condition
        if old_condition == 'transition' and new_condition in ['day', 'night']:
            # Wait for the new lighting condition to stabilize before capturing
            wait_time = 60  # 1 minute (reduced from 5 in v1.2.1)
            logger.info(f"Exited transition period to {new_condition}. Waiting {wait_time} seconds for lighting to stabilize...")
            time.sleep(wait_time)
            
            # Only capture if the lighting condition is still the same after waiting
            current_condition = get_current_lighting_condition()
            if current_condition == new_condition:
                # Check if we're in a pure condition for high-quality base images
                if is_pure_lighting_condition():
                    logger.info(f"Capturing pure {new_condition} base images after transition")
                    capture_base_images(lighting_condition=new_condition, force_capture=True)
                else:
                    logger.info(f"Not in pure condition yet, waiting for better lighting before capture")
            else:
                logger.info(f"Lighting condition changed again to {current_condition}, skipping capture")
        
    except Exception as e:
        logger.error(f"Error handling lighting transition: {e}")
        raise

def should_capture_startup_base_images():
    """
    Determine if base images should be captured on startup.
    Updated in v1.2.1: Always capture startup images.
    
    Returns:
        bool: True if base images should be captured on startup
    """
    try:
        # Get detailed lighting info
        lighting_info = get_lighting_info()
        condition = lighting_info['condition']
        
        logger.info(f"Current lighting condition on startup: {condition}")
        
        # In v1.2.1, we always want to capture startup images
        return True
            
    except Exception as e:
        logger.error(f"Error checking startup base image capture: {e}")
        return False

def notify_transition_period(root=None):
    """
    Display a notification that we're in a transition period.
    Updated in v1.2.1 to show more detailed information.
    
    Args:
        root (tk.Tk, optional): Tkinter root window to attach notification to
    """
    try:
        # Get detailed lighting information for better messaging
        lighting_info = get_lighting_info()
        detailed = lighting_info.get('detailed_condition', 'unknown')
        progress = lighting_info.get('transition_percentage', 0)
        
        # Build countdown message
        countdown_text = ""
        if detailed == 'dawn':
            if lighting_info['countdown']['to_true_day'] is not None:
                countdown = format_time_until(lighting_info['countdown']['to_true_day'])
                countdown_text = f"\nTime until true day: {countdown}"
        elif detailed == 'dusk':
            if lighting_info['countdown']['to_true_night'] is not None:
                countdown = format_time_until(lighting_info['countdown']['to_true_night'])
                countdown_text = f"\nTime until true night: {countdown}"
        
        message = f"Currently in lighting transition period ({detailed}).\nTransition progress: {progress:.1f}%{countdown_text}"
        
        if root:
            # If we have a root window, create a proper notification
            from tkinter import Label, RIDGE
            
            # Create a notification frame
            notification = tk.Toplevel(root)
            notification.title("Lighting Transition")
            notification.geometry("400x150")  # Made taller for more content
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
        
        # Get detailed lighting information for better messaging
        lighting_info = get_lighting_info()
        is_transition = lighting_info['is_transition']
        
        if is_transition:
            logger.info("Currently in transition period - capturing transition base images")
            notify_transition_period()
        
        # In v1.2.1, we capture base images regardless of transition period
        # But we log differently and annotate the images
        results = capture_base_images(current_condition, force_capture=True, show_ui_message=True)
        
        if results:
            # Count successful captures
            success_count = sum(1 for r in results if r['status'] == 'success')
            transition_count = sum(1 for r in results if r['status'] == 'success' and r.get('is_transition', False))
            pure_count = sum(1 for r in results if r['status'] == 'success' and r.get('is_pure', False))
            
            # Show appropriate message
            if is_transition:
                messagebox.showinfo(
                    "Base Image Capture",
                    f"Successfully captured {success_count} transition base images for {current_condition} condition."
                )
            elif pure_count > 0:
                messagebox.showinfo(
                    "Base Image Capture",
                    f"Successfully captured {pure_count} pure base images for {current_condition} condition."
                )
            else:
                messagebox.showinfo(
                    "Base Image Capture",
                    f"Successfully captured {success_count} base images for {current_condition} condition."
                )
        else:
            messagebox.showinfo(
                "Base Image Capture",
                "No base images were captured. Please check the logs for details."
            )
                
    except Exception as e:
        logger.error(f"Base image capture failed: {e}")
        messagebox.showerror("Error", f"Base image capture failed: {e}")
        raise