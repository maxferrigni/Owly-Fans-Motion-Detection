# File: utilities/image_comparison_utils.py
# Purpose: Generate and handle image analysis for owl detection
#
# March 18, 2025 Update - Version 1.4.3
# - Added support for individual image components (base, current, analysis)
# - Updated terminology: "comparison image" → "3-panel composite"
# - "Analysis image" used for the difference visualization component
# - Removed text overlays, added red outlines for owl shapes

import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import logging
from datetime import datetime
import pytz
from utilities.logging_utils import get_logger
from utilities.constants import (
    BASE_IMAGES_DIR, 
    IMAGE_COMPARISONS_DIR, 
    CAMERA_MAPPINGS, 
    get_comparison_image_path, 
    get_saved_image_path,
    COMPARISON_IMAGE_FILENAMES
)

# Initialize logger
logger = get_logger()

def validate_comparison_images(base_image, new_image, expected_size=None):
    """Validate images for comparison."""
    try:
        # Check image types
        if not isinstance(base_image, Image.Image) or not isinstance(new_image, Image.Image):
            return False, "Invalid image types provided"
            
        # Check image sizes match
        if base_image.size != new_image.size:
            return False, f"Image size mismatch: {base_image.size} vs {new_image.size}"
            
        # Check expected size if provided
        if expected_size and base_image.size != expected_size:
            return False, f"Images do not match expected size: {base_image.size} vs {expected_size}"
            
        # Check image modes
        if base_image.mode not in ['RGB', 'L'] or new_image.mode not in ['RGB', 'L']:
            return False, "Images must be in RGB or grayscale mode"
            
        return True, "Images validated successfully"
        
    except Exception as e:
        logger.error(f"Error validating images: {e}")
        return False, f"Validation error: {str(e)}"

def analyze_change_metrics(diff_image, threshold, config):
    """Analyze pixel and luminance changes in difference image."""
    try:
        # Convert to numpy array for calculations
        diff_array = np.array(diff_image.convert('L'))
        total_pixels = diff_array.size
        
        # Calculate pixel change metrics
        changed_pixels = np.sum(diff_array > threshold)
        pixel_change_ratio = changed_pixels / total_pixels
        
        # Calculate luminance metrics
        mean_luminance = np.mean(diff_array)
        max_luminance = np.max(diff_array)
        std_luminance = np.std(diff_array)
        
        # Calculate region-specific metrics
        height, width = diff_array.shape
        regions = {
            'top': diff_array[:height//3, :],
            'middle': diff_array[height//3:2*height//3, :],
            'bottom': diff_array[2*height//3:, :]
        }
        
        region_metrics = {}
        for region_name, region_data in regions.items():
            region_metrics[region_name] = {
                'mean_luminance': np.mean(region_data),
                'pixel_change_ratio': np.sum(region_data > threshold) / region_data.size
            }
        
        return {
            'pixel_change_ratio': pixel_change_ratio,
            'mean_luminance': mean_luminance,
            'max_luminance': max_luminance,
            'std_luminance': std_luminance,
            'region_metrics': region_metrics,
            'threshold_used': threshold
        }
        
    except Exception as e:
        logger.error(f"Error analyzing change metrics: {e}")
        raise

def analyze_motion_characteristics(binary_mask, config):
    """Analyze motion characteristics in binary mask."""
    try:
        # Find contours
        contours, _ = cv2.findContours(
            binary_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        total_area = binary_mask.shape[0] * binary_mask.shape[1]
        motion_data = []
        
        for contour in contours:
            # Calculate basic metrics
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            x, y, w, h = cv2.boundingRect(contour)
            
            # Calculate shape characteristics
            circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
            aspect_ratio = float(w) / h if h > 0 else 0
            area_ratio = area / total_area
            extent = area / (w * h) if w * h > 0 else 0
            
            motion_data.append({
                'area': area,
                'area_ratio': area_ratio,
                'circularity': circularity,
                'aspect_ratio': aspect_ratio,
                'extent': extent,
                'position': (x, y),
                'size': (w, h)
            })
        
        # Sort by area ratio
        motion_data.sort(key=lambda x: x['area_ratio'], reverse=True)
        
        return {
            'total_regions': len(contours),
            'regions': motion_data,
            'largest_region': motion_data[0] if motion_data else None
        }
        
    except Exception as e:
        logger.error(f"Error analyzing motion characteristics: {e}")
        raise

def create_analysis_image(base_image, new_image, threshold, config):
    """
    Create analysis image that highlights changes with red outlines around owl shapes.
    
    Args:
        base_image (PIL.Image): Base reference image
        new_image (PIL.Image): New current image
        threshold (int): Threshold value
        config (dict): Camera configuration
        
    Returns:
        tuple: (analysis_image, binary_mask, contains_owl_shapes)
    """
    try:
        # Convert to OpenCV format
        base_cv = cv2.cvtColor(np.array(base_image), cv2.COLOR_RGB2GRAY)
        new_cv = cv2.cvtColor(np.array(new_image), cv2.COLOR_RGB2GRAY)
        
        # Calculate absolute difference
        diff = cv2.absdiff(new_cv, base_cv)
        
        # Apply Gaussian blur to reduce noise
        blurred_diff = cv2.GaussianBlur(diff, (5, 5), 0)
        
        # Create binary mask
        _, binary_mask = cv2.threshold(
            blurred_diff,
            threshold,
            255,
            cv2.THRESH_BINARY
        )
        
        # Create visualization
        diff_color = cv2.cvtColor(diff, cv2.COLOR_GRAY2BGR)
        height, width = diff.shape
        
        # Draw detection regions
        contours, _ = cv2.findContours(
            binary_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Sort contours by area
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        
        # Filter contours to only include owl-like shapes
        owl_contours = []
        for contour in contours:
            # Calculate contour properties
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue
                
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h if h > 0 else 0
            area_ratio = area / (height * width)
            
            # Check if this contour meets our owl criteria
            min_circularity = config["motion_detection"]["min_circularity"]
            min_aspect_ratio = config["motion_detection"]["min_aspect_ratio"]
            max_aspect_ratio = config["motion_detection"]["max_aspect_ratio"]
            min_area_ratio = config["motion_detection"]["min_area_ratio"]
            
            if (circularity >= min_circularity and 
                min_aspect_ratio <= aspect_ratio <= max_aspect_ratio and
                area_ratio >= min_area_ratio):
                owl_contours.append((contour, (x, y, w, h), circularity, area_ratio))
        
        # Draw only contours that resemble owls with RED outlines
        for i, (contour, (x, y, w, h), circularity, area_ratio) in enumerate(owl_contours):
            # Use red color for owl shape highlighting
            owl_highlight_color = (0, 0, 255)  # RED in BGR
            
            # Draw ellipse instead of irregular contour for cleaner visualization
            if len(contour) >= 5:  # Minimum 5 points required for ellipse fitting
                ellipse = cv2.fitEllipse(contour)
                cv2.ellipse(diff_color, ellipse, owl_highlight_color, 2)
                
                # Draw a simple "X" mark in the center to indicate owl detection point
                center_x = int(x + w/2)
                center_y = int(y + h/2)
                marker_size = 10
                cv2.line(diff_color, 
                         (center_x - marker_size, center_y - marker_size),
                         (center_x + marker_size, center_y + marker_size),
                         owl_highlight_color, 2)
                cv2.line(diff_color, 
                         (center_x + marker_size, center_y - marker_size),
                         (center_x - marker_size, center_y + marker_size),
                         owl_highlight_color, 2)
            else:
                # Fallback to drawing a simple rectangle
                cv2.rectangle(diff_color, (x, y), (x+w, y+h), owl_highlight_color, 2)
        
        # Convert back to PIL image
        analysis_image = Image.fromarray(diff_color)
        
        return analysis_image, binary_mask, len(owl_contours) > 0
        
    except Exception as e:
        logger.error(f"Error creating analysis image: {e}")
        raise

def get_component_image_path(camera_name, image_type):
    """
    Get the path for saving/loading individual image components.
    
    Args:
        camera_name (str): Name of the camera
        image_type (str): Type of image ("base", "current", or "analysis")
        
    Returns:
        str: Path to the image file
    """
    # Create camera-specific directory if it doesn't exist
    camera_dir = os.path.join(IMAGE_COMPARISONS_DIR, camera_name.replace(" ", "_"))
    os.makedirs(camera_dir, exist_ok=True)
    
    # Create filenames for each component
    component_filenames = {
        "base": f"{camera_name.replace(' ', '_')}_base.jpg",
        "current": f"{camera_name.replace(' ', '_')}_current.jpg",
        "analysis": f"{camera_name.replace(' ', '_')}_analysis.jpg"
    }
    
    return os.path.join(camera_dir, component_filenames.get(image_type, "unknown.jpg"))

def save_component_images(base_image, current_image, analysis_image, camera_name):
    """
    Save the individual image components for display.
    
    Args:
        base_image (PIL.Image): Base reference image
        current_image (PIL.Image): Current/new image
        analysis_image (PIL.Image): Analysis image with highlighting
        camera_name (str): Name of the camera
        
    Returns:
        dict: Paths to the saved component images
    """
    try:
        components = {
            "base": base_image,
            "current": current_image, 
            "analysis": analysis_image
        }
        
        paths = {}
        
        # Save each component
        for component_type, img in components.items():
            path = get_component_image_path(camera_name, component_type)
            img.save(path, quality=95)
            paths[component_type] = path
            
        logger.debug(f"Saved individual component images for {camera_name}")
        return paths
        
    except Exception as e:
        logger.error(f"Error saving component images: {e}")
        return {}

def save_local_image_set(base_image, new_image, analysis_image, three_panel_image, camera_name, timestamp):
    """
    Save a complete set of images locally with matching timestamps.
    
    Args:
        base_image (PIL.Image): The base reference image
        new_image (PIL.Image): The newly captured image
        analysis_image (PIL.Image): The analysis image with highlighting
        three_panel_image (PIL.Image): The 3-panel composite image
        camera_name (str): Name of the camera
        timestamp (datetime): Timestamp to use for all images
    """
    try:
        from utilities.constants import SAVED_IMAGES_DIR
        
        # Ensure the directory exists
        os.makedirs(SAVED_IMAGES_DIR, exist_ok=True)
        
        # Format camera name and timestamp
        camera_name_clean = camera_name.lower().replace(' ', '_')
        ts_str = timestamp.strftime('%Y%m%d_%H%M%S')
        
        # Create filenames for all images with matching timestamps
        base_filename = f"{camera_name_clean}_base_{ts_str}.jpg"
        current_filename = f"{camera_name_clean}_current_{ts_str}.jpg"
        analysis_filename = f"{camera_name_clean}_analysis_{ts_str}.jpg"
        composite_filename = f"{camera_name_clean}_composite_{ts_str}.jpg"
        
        # Create full paths
        base_path = os.path.join(SAVED_IMAGES_DIR, base_filename)
        current_path = os.path.join(SAVED_IMAGES_DIR, current_filename)
        analysis_path = os.path.join(SAVED_IMAGES_DIR, analysis_filename)
        composite_path = os.path.join(SAVED_IMAGES_DIR, composite_filename)
        
        # Save all images
        base_image.save(base_path, quality=95)
        new_image.save(current_path, quality=95)
        analysis_image.save(analysis_path, quality=95)
        three_panel_image.save(composite_path, quality=95)
        
        logger.info(f"Saved complete image set for {camera_name} with timestamp {ts_str}")
        
        return {
            "base_path": base_path,
            "current_path": current_path,
            "analysis_path": analysis_path,
            "composite_path": composite_path
        }
        
    except Exception as e:
        logger.error(f"Error saving local image set: {e}")
        return None

def create_comparison_image(base_image, new_image, camera_name, threshold, config, detection_info=None, is_test=False, timestamp=None):
    """
    Create 3-panel composite image and save individual components.
    The three panels are: base image, current image, and analysis image.
    
    Args:
        base_image (PIL.Image): Base reference image
        new_image (PIL.Image): New image to check
        camera_name (str): Name of the camera
        threshold (int): Threshold value
        config (dict): Camera configuration
        detection_info (dict): Detection information including confidence scores
        is_test (bool): Whether this is a test image
        timestamp (datetime): Timestamp for image
        
    Returns:
        str: Path to saved 3-panel composite image
    """
    try:
        # Validate images
        is_valid, message = validate_comparison_images(base_image, new_image)
        if not is_valid:
            raise ValueError(message)
        
        # Get image dimensions
        width, height = base_image.size
        
        # Create analysis image with red owl shape highlighting
        analysis_image, binary_mask, contains_owl_shapes = create_analysis_image(
            base_image,
            new_image,
            threshold,
            config
        )
        
        # Analyze metrics
        change_metrics = analyze_change_metrics(analysis_image, threshold, config)
        motion_chars = analyze_motion_characteristics(binary_mask, config)
        
        # Add metrics to change_metrics (for logging/storage)
        change_metrics.update({
            'motion_characteristics': motion_chars,
            'camera_name': camera_name,
            'is_test': is_test
        })
        
        # Create 3-panel composite image
        three_panel_image = Image.new('RGB', (width * 3, height))
        three_panel_image.paste(base_image, (0, 0))
        three_panel_image.paste(new_image, (width, 0))
        three_panel_image.paste(analysis_image, (width * 2, 0))
        
        # Ensure timestamp is set
        if not timestamp:
            timestamp = datetime.now(pytz.timezone('America/Los_Angeles'))
            
        # Save the individual component images for the UI
        component_paths = save_component_images(
            base_image,
            new_image,
            analysis_image,
            camera_name
        )
        
        # Get the fixed path for the 3-panel composite image
        composite_path = get_comparison_image_path(camera_name)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(composite_path), exist_ok=True)
        
        # Save the 3-panel composite image to the fixed location
        three_panel_image.save(composite_path, quality=95)
        
        # Check if local saving is enabled
        local_saving = os.getenv('OWL_LOCAL_SAVING', 'False').lower() == 'true'
        
        # If local saving is enabled, save a complete set of images with the same timestamp
        if local_saving:
            saved_paths = save_local_image_set(
                base_image, 
                new_image, 
                analysis_image,
                three_panel_image,
                camera_name,
                timestamp
            )
            
        is_owl_detected = detection_info.get("is_owl_present", False) if detection_info else contains_owl_shapes
        confidence = detection_info.get("owl_confidence", 0.0) if detection_info else 0.0
        
        logger.info(
            f"Created images for {camera_name}. "
            f"Owl detected: {is_owl_detected}, "
            f"Confidence: {confidence:.1f}% "
            f"{'(Test Mode)' if is_test else ''}"
        )
        
        # Return both the composite path and component paths
        return {
            "composite_path": composite_path,
            "component_paths": component_paths,
            "contains_owl_shapes": contains_owl_shapes
        }
        
    except Exception as e:
        logger.error(f"Error creating images: {e}")
        raise

if __name__ == "__main__":
    # Test the comparison functionality
    try:
        import pyautogui
        
        # Test configuration
        test_config = {
            "motion_detection": {
                "min_circularity": 0.5,
                "min_aspect_ratio": 0.5,
                "max_aspect_ratio": 2.0,
                "min_area_ratio": 0.2,
                "brightness_threshold": 20
            }
        }
        
        # Test detection info with confidence
        test_detection_info = {
            "is_owl_present": True,
            "owl_confidence": 75.5,
            "consecutive_owl_frames": 3,
            "confidence_factors": {
                "shape_confidence": 30.0,
                "motion_confidence": 25.5,
                "temporal_confidence": 15.0,
                "camera_confidence": 5.0
            }
        }
        
        # Capture test images
        test_roi = (0, 0, 640, 480)
        base = pyautogui.screenshot(region=test_roi)
        new = pyautogui.screenshot(region=test_roi)
        
        # Test comparison
        result = create_comparison_image(
            base,
            new,
            "Test Camera",
            threshold=30,
            config=test_config,
            detection_info=test_detection_info,
            is_test=True
        )
        
        print(f"Test results: {result}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise