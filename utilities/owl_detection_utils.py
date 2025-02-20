# File: utilities/owl_detection_utils.py
# Purpose: Specialized detection algorithms for owl presence

# Debug information
import sys
print("Debug - Python Path in owl_detection_utils.py:")
print(f"Executable: {sys.executable}")
print(f"Version: {sys.version}")
print(f"Path: {sys.path}")

# Main imports
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
    logger.info("Starting image preparation for owl detection")
    
    # Convert PIL images to OpenCV format
    new_cv = cv2.cvtColor(np.array(new_image), cv2.COLOR_RGB2GRAY)
    base_cv = cv2.cvtColor(np.array(base_image), cv2.COLOR_RGB2GRAY)
    
    # Log image sizes
    logger.info(f"Image sizes - New: {new_cv.shape}, Base: {base_cv.shape}")
    
    # Ensure images are the same size
    if new_cv.shape != base_cv.shape:
        logger.error("Image sizes don't match")
        raise ValueError("Images must be the same size")
    
    logger.info("Image preparation completed successfully")
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
    logger.info("Splitting box image into compartments")
    
    # Find the center divider by looking for vertical line
    height, width = image.shape
    center = width // 2
    
    logger.info(f"Image dimensions - Height: {height}, Width: {width}, Center: {center}")
    
    # Get left and right compartments
    left_compartment = image[:, :center]
    right_compartment = image[:, center:]
    
    logger.info("Box image split completed")
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
        logger.info("Starting compartment difference analysis")
        
        # Calculate absolute difference between images
        diff = cv2.absdiff(new_compartment, base_compartment)
        
        # Apply Gaussian blur to reduce noise
        blurred_diff = cv2.GaussianBlur(diff, (5, 5), 0)
        
        # Calculate adaptive threshold
        mean_diff = np.mean(blurred_diff)
        std_diff = np.std(blurred_diff)
        threshold_value = mean_diff + (2 * std_diff)
        
        logger.info(f"Difference metrics - Mean: {mean_diff:.2f}, Std: {std_diff:.2f}, Threshold: {threshold_value:.2f}")
        
        # Create binary mask of significant changes
        _, binary_mask = cv2.threshold(
            blurred_diff,
            threshold_value,
            255,
            cv2.THRESH_BINARY
        )
        
        # Calculate percentage of changed pixels
        significant_pixels = np.sum(binary_mask > 0) / binary_mask.size * 100
        logger.info(f"Percentage of significantly changed pixels: {significant_pixels:.2f}%")
        
        # Calculate difference metrics
        diff_metrics = {
            "mean_difference": mean_diff,
            "std_difference": std_diff,
            "threshold_used": threshold_value,
            "significant_pixels": significant_pixels / 100  # Convert back to decimal
        }
        
        logger.info("Compartment difference analysis completed")
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
        
        metrics = {
            "area": area,
            "perimeter": perimeter,
            "circularity": circularity,
            "aspect_ratio": aspect_ratio,
            "area_ratio": area_ratio,
            "position": (x, y),
            "size": (w, h)
        }
        
        logger.info(f"Contour metrics - Area Ratio: {area_ratio:.2f}, Circularity: {circularity:.2f}, "
                   f"Aspect Ratio: {aspect_ratio:.2f}")
        
        return metrics
        
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
        logger.info("Starting owl contour detection")
        
        # Find contours in binary mask
        contours, _ = cv2.findContours(
            binary_mask, 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        logger.info(f"Found {len(contours)} initial contours")
        
        # Calculate compartment area
        compartment_area = binary_mask.shape[0] * binary_mask.shape[1]
        
        # Analyze each contour
        contour_data = []
        for i, contour in enumerate(contours):
            metrics = analyze_contour_shape(contour, compartment_area)
            contour_data.append({
                "contour": contour,
                "metrics": metrics
            })
        
        logger.info(f"Analyzed {len(contour_data)} contours")
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
        logger.info("Checking region brightness")
        
        # Create mask for contour region
        mask = np.zeros_like(image)
        cv2.drawContours(mask, [contour], 0, 255, -1)
        
        # Calculate average brightness in region
        current_brightness = np.mean(image[mask == 255])
        base_brightness = np.mean(base_image[mask == 255])
        
        brightness_diff = current_brightness - base_brightness
        is_brighter = brightness_diff > 20  # Base threshold for significant brightness
        
        logger.info(f"Brightness analysis - Current: {current_brightness:.2f}, "
                   f"Base: {base_brightness:.2f}, Difference: {brightness_diff:.2f}, "
                   f"Is Brighter: {is_brighter}")
        
        return is_brighter, brightness_diff
        
    except Exception as e:
        logger.error(f"Error checking brightness: {e}")
        raise

def detect_owl_in_box(new_image, base_image, config):
    """
    Main function to detect owl presence in box.
    
    Args:
        new_image (PIL.Image): New captured image
        base_image (PIL.Image): Base reference image
        config (dict): Camera configuration parameters
        
    Returns:
        tuple: (bool, dict) - (is_owl_present, detection_info)
    """
    try:
        logger.info("Starting owl detection process")
        
        # Convert and prepare images
        new_cv, base_cv = prepare_images(new_image, base_image)
        
        # Split into compartments
        new_left, new_right = split_box_image(new_cv)
        base_left, base_right = split_box_image(base_cv)
        
        # Get configuration parameters
        motion_config = config.get("motion_detection", {})
        min_circularity = motion_config.get("min_circularity", 0.5)
        min_aspect_ratio = motion_config.get("min_aspect_ratio", 0.5)
        max_aspect_ratio = motion_config.get("max_aspect_ratio", 2.0)
        min_area_ratio = motion_config.get("min_area_ratio", 0.2)
        brightness_threshold = motion_config.get("brightness_threshold", 20)
        
        # Analyze differences in left compartment
        binary_mask, diff_metrics = analyze_compartment_differences(
            new_left, base_left
        )
        
        # Find and analyze contours
        contour_data = find_owl_contours(binary_mask)
        
        # Check each candidate contour
        owl_candidates = []
        for i, data in enumerate(contour_data):
            # Check if region is brighter than base image
            is_brighter, brightness_diff = check_brightness(
                data["contour"],
                new_left,
                base_left
            )
            
            # Apply configured thresholds
            metrics = data["metrics"]
            if (is_brighter and
                metrics["circularity"] > min_circularity and
                min_aspect_ratio < metrics["aspect_ratio"] < max_aspect_ratio and
                metrics["area_ratio"] > min_area_ratio and
                brightness_diff > brightness_threshold):
                
                logger.info(f"Found bright owl-like candidate {i+1}")
                owl_candidates.append({
                    **metrics,
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
        
        logger.info(f"Owl detection completed - Owl Present: {is_owl_present}, "
                   f"Candidates: {len(owl_candidates)}, "
                   f"Confidence: {detection_info['confidence']:.2f}")
        
        return is_owl_present, detection_info
        
    except Exception as e:
        logger.error(f"Error in owl detection: {e}")
        return False, {"error": str(e)}

if __name__ == "__main__":
    # Test the detection
    try:
        test_new = Image.open("test_new.jpg")
        test_base = Image.open("test_base.jpg")
        test_config = {
            "motion_detection": {
                "min_circularity": 0.5,
                "min_aspect_ratio": 0.5,
                "max_aspect_ratio": 2.0,
                "min_area_ratio": 0.2,
                "brightness_threshold": 20
            }
        }
        result, info = detect_owl_in_box(test_new, test_base, test_config)
        print(f"Detection result: {result}")
        print(f"Detection info: {info}")
    except Exception as e:
        print(f"Test failed: {e}")