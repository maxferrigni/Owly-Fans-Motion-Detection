# File: utilities/owl_detection_utils.py
# Purpose: Specialized detection algorithms for owl presence

import cv2
import numpy as np
from PIL import Image
from utilities.logging_utils import get_logger

logger = get_logger()

def prepare_images(new_image, base_image):
    """
    Convert PIL images to OpenCV format and prepare for processing.
    
    Args:
        new_image (PIL.Image): New captured image
        base_image (PIL.Image): Base reference image
        
    Returns:
        tuple: (new_cv, base_cv) OpenCV format images
    """
    # Convert PIL images to OpenCV format
    new_cv = cv2.cvtColor(np.array(new_image), cv2.COLOR_RGB2GRAY)
    base_cv = cv2.cvtColor(np.array(base_image), cv2.COLOR_RGB2GRAY)
    
    # Ensure images are the same size
    if new_cv.shape != base_cv.shape:
        logger.error("Image sizes don't match")
        raise ValueError("Images must be the same size")
        
    return new_cv, base_cv

def split_box_image(image):
    """
    Split box image into left and right compartments.
    Owl only appears in left compartment.
    
    Args:
        image (np.array): OpenCV format image
        
    Returns:
        tuple: (left_compartment, right_compartment)
    """
    # Find the center divider by looking for vertical line
    height, width = image.shape
    center = width // 2
    
    # Get left and right compartments
    left_compartment = image[:, :center]
    right_compartment = image[:, center:]
    
    return left_compartment, right_compartment

def analyze_compartment_differences(new_compartment, base_compartment):
    """
    Analyze differences between new and base compartment images.
    
    Args:
        new_compartment (np.array): New image compartment
        base_compartment (np.array): Base image compartment
        
    Returns:
        tuple: (binary_mask, diff_metrics)
    """
    try:
        # Calculate absolute difference between images
        diff = cv2.absdiff(new_compartment, base_compartment)
        
        # Apply Gaussian blur to reduce noise
        blurred_diff = cv2.GaussianBlur(diff, (5, 5), 0)
        
        # Calculate adaptive threshold
        mean_diff = np.mean(blurred_diff)
        std_diff = np.std(blurred_diff)
        threshold_value = mean_diff + (2 * std_diff)  # Adjust multiplier as needed
        
        # Create binary mask of significant changes
        _, binary_mask = cv2.threshold(
            blurred_diff,
            threshold_value,
            255,
            cv2.THRESH_BINARY
        )
        
        # Calculate difference metrics
        diff_metrics = {
            "mean_difference": mean_diff,
            "std_difference": std_diff,
            "threshold_used": threshold_value,
            "significant_pixels": np.sum(binary_mask > 0) / binary_mask.size
        }
        
        return binary_mask, diff_metrics
        
    except Exception as e:
        logger.error(f"Error analyzing compartment differences: {e}")
        raise

def analyze_contour_shape(contour, compartment_area):
    """
    Analyze a contour for owl-like characteristics.
    
    Args:
        contour: OpenCV contour
        compartment_area: Total area of compartment
        
    Returns:
        dict: Shape metrics
    """
    try:
        # Calculate basic metrics
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        
        # Get bounding box
        x, y, w, h = cv2.boundingRect(contour)
        
        # Calculate shape metrics
        circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
        aspect_ratio = float(w) / h if h > 0 else 0
        area_ratio = area / compartment_area
        
        return {
            "area": area,
            "perimeter": perimeter,
            "circularity": circularity,
            "aspect_ratio": aspect_ratio,
            "area_ratio": area_ratio,
            "position": (x, y),
            "size": (w, h)
        }
    except Exception as e:
        logger.error(f"Error analyzing contour shape: {e}")
        raise

def find_owl_contours(binary_mask):
    """
    Find and analyze potential owl contours in binary mask.
    
    Args:
        binary_mask: Binary image mask
        
    Returns:
        list: List of contours and their metrics
    """
    try:
        # Find contours in binary mask
        contours, _ = cv2.findContours(
            binary_mask, 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Calculate compartment area
        compartment_area = binary_mask.shape[0] * binary_mask.shape[1]
        
        # Analyze each contour
        contour_data = []
        for contour in contours:
            metrics = analyze_contour_shape(contour, compartment_area)
            
            # Filter for owl-like characteristics
            if (metrics["circularity"] > 0.5 and  # Fairly round
                0.5 < metrics["aspect_ratio"] < 2.0 and  # Not too elongated
                metrics["area_ratio"] > 0.2):  # Large enough
                
                contour_data.append({
                    "contour": contour,
                    "metrics": metrics
                })
        
        return contour_data
        
    except Exception as e:
        logger.error(f"Error finding owl contours: {e}")
        raise

def check_brightness(contour, image, base_image):
    """
    Check if the region inside contour is brighter than base image.
    
    Args:
        contour: OpenCV contour
        image: Current image
        base_image: Base reference image
        
    Returns:
        tuple: (is_brighter, brightness_diff)
    """
    try:
        # Create mask for contour region
        mask = np.zeros_like(image)
        cv2.drawContours(mask, [contour], 0, 255, -1)
        
        # Calculate average brightness in region
        current_brightness = np.mean(image[mask == 255])
        base_brightness = np.mean(base_image[mask == 255])
        
        brightness_diff = current_brightness - base_brightness
        is_brighter = brightness_diff > 20  # Threshold for significant brightness
        
        return is_brighter, brightness_diff
        
    except Exception as e:
        logger.error(f"Error checking brightness: {e}")
        raise

def detect_owl_in_box(new_image, base_image):
    """
    Main function to detect owl presence in box.
    
    Args:
        new_image (PIL.Image): New captured image
        base_image (PIL.Image): Base reference image
        
    Returns:
        tuple: (bool, dict) - (is_owl_present, detection_info)
    """
    try:
        # Convert and prepare images
        new_cv, base_cv = prepare_images(new_image, base_image)
        
        # Split into compartments
        new_left, new_right = split_box_image(new_cv)
        base_left, base_right = split_box_image(base_cv)
        
        # Analyze differences in left compartment
        binary_mask, diff_metrics = analyze_compartment_differences(
            new_left, base_left
        )
        
        # Find and analyze contours
        contour_data = find_owl_contours(binary_mask)
        
        # Check each candidate contour
        owl_candidates = []
        for data in contour_data:
            # Check if region is brighter than base image
            is_brighter, brightness_diff = check_brightness(
                data["contour"],
                new_left,
                base_left
            )
            
            if is_brighter:
                owl_candidates.append({
                    **data["metrics"],
                    "brightness_diff": brightness_diff
                })
        
        # Determine if owl is present based on candidates
        is_owl_present = len(owl_candidates) > 0
        
        # Prepare detection info
        detection_info = {
            "confidence": max([c["area_ratio"] for c in owl_candidates], default=0),
            "location": "left_compartment",
            "candidates": owl_candidates,
            "diff_metrics": diff_metrics,
        }
        
        return is_owl_present, detection_info
        
    except Exception as e:
        logger.error(f"Error in owl detection: {e}")
        return False, {"error": str(e)}

if __name__ == "__main__":
    # Test the detection
    try:
        test_new = Image.open("test_new.jpg")
        test_base = Image.open("test_base.jpg")
        result, info = detect_owl_in_box(test_new, test_base)
        print(f"Detection result: {result}")
        print(f"Detection info: {info}")
    except Exception as e:
        print(f"Test failed: {e}")