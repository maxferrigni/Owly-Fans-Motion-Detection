# File: utilities/owl_detection_utils.py
# Purpose: Specialized detection algorithms for owl presence with test support

import cv2
import numpy as np
from PIL import Image
from utilities.logging_utils import get_logger

logger = get_logger()

def validate_images(new_image, base_image, expected_roi=None, is_test=False):
    """
    Validate images meet requirements for processing.
    
    Args:
        new_image (PIL.Image): New image to check
        base_image (PIL.Image): Base image to check
        expected_roi (tuple, optional): Expected dimensions (w, h) from ROI
        is_test (bool): Whether this is a test image
        
    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    try:
        # Basic image validation
        if not isinstance(new_image, Image.Image) or not isinstance(base_image, Image.Image):
            return False, "Invalid image types provided"
            
        # Size checks
        if new_image.size != base_image.size:
            return False, f"Image size mismatch: {new_image.size} vs {base_image.size}"
            
        # ROI validation if provided
        if expected_roi:
            expected_width = abs(expected_roi[2] - expected_roi[0])
            expected_height = abs(expected_roi[3] - expected_roi[1])
            expected_size = (expected_width, expected_height)
            
            if new_image.size != expected_size:
                return False, f"Image does not match ROI dimensions: {new_image.size} vs {expected_size}"
        
        # Additional validation for test images
        if is_test:
            if new_image.mode not in ['RGB', 'L']:
                return False, f"Unsupported image mode for testing: {new_image.mode}"
            
            # Check minimum dimensions
            min_size = 100  # minimum pixel dimension
            if new_image.width < min_size or new_image.height < min_size:
                return False, f"Image too small: minimum {min_size}px required"
        
        return True, "Images validated successfully"
        
    except Exception as e:
        logger.error(f"Error during image validation: {e}")
        return False, f"Validation error: {str(e)}"

def prepare_images(new_image, base_image, expected_roi=None, is_test=False):
    """
    Convert PIL images to OpenCV format and prepare for processing.
    
    Args:
        new_image (PIL.Image): New captured image
        base_image (PIL.Image): Base reference image
        expected_roi (tuple, optional): Expected dimensions from ROI
        is_test (bool): Whether this is a test image
        
    Returns:
        tuple: (new_cv, base_cv) OpenCV format images
    """
    logger.info("Starting image preparation for owl detection")
    
    # Validate images
    is_valid, message = validate_images(new_image, base_image, expected_roi, is_test)
    if not is_valid:
        raise ValueError(message)
    
    # Convert PIL images to OpenCV format
    new_cv = cv2.cvtColor(np.array(new_image), cv2.COLOR_RGB2GRAY)
    base_cv = cv2.cvtColor(np.array(base_image), cv2.COLOR_RGB2GRAY)
    
    logger.info(f"Image sizes - New: {new_cv.shape}, Base: {base_cv.shape}")
    
    return new_cv, base_cv

def split_box_image(image):
    """
    Split box image into left and right compartments.
    Owl only appears in left compartment.
    """
    logger.info("Splitting box image into compartments")
    
    height, width = image.shape
    center = width // 2
    
    logger.info(f"Image dimensions - Height: {height}, Width: {width}, Center: {center}")
    
    left_compartment = image[:, :center]
    right_compartment = image[:, center:]
    
    return left_compartment, right_compartment

def analyze_compartment_differences(new_compartment, base_compartment, sensitivity=1.0):
    """
    Analyze differences between new and base compartment images.
    
    Args:
        new_compartment (np.array): New image compartment
        base_compartment (np.array): Base image compartment
        sensitivity (float): Multiplier for threshold calculation (used in testing)
    """
    try:
        logger.info("Starting compartment difference analysis")
        
        # Calculate absolute difference
        diff = cv2.absdiff(new_compartment, base_compartment)
        
        # Apply Gaussian blur
        blurred_diff = cv2.GaussianBlur(diff, (5, 5), 0)
        
        # Calculate adaptive threshold with sensitivity adjustment
        mean_diff = np.mean(blurred_diff)
        std_diff = np.std(blurred_diff)
        threshold_value = (mean_diff + (2 * std_diff)) * sensitivity
        
        logger.info(f"Difference metrics - Mean: {mean_diff:.2f}, Std: {std_diff:.2f}, "
                   f"Threshold: {threshold_value:.2f}, Sensitivity: {sensitivity}")
        
        # Create binary mask
        _, binary_mask = cv2.threshold(
            blurred_diff,
            threshold_value,
            255,
            cv2.THRESH_BINARY
        )
        
        # Calculate metrics
        significant_pixels = np.sum(binary_mask > 0) / binary_mask.size * 100
        
        diff_metrics = {
            "mean_difference": mean_diff,
            "std_difference": std_diff,
            "threshold_used": threshold_value,
            "significant_pixels": significant_pixels / 100,
            "sensitivity_used": sensitivity
        }
        
        return binary_mask, diff_metrics
        
    except Exception as e:
        logger.error(f"Error analyzing compartment differences: {e}")
        raise

def analyze_contour_shape(contour, compartment_area):
    """
    Analyze a contour for owl-like characteristics.
    """
    try:
        # Calculate basic metrics
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
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
        
        logger.info(f"Contour metrics - Area Ratio: {area_ratio:.2f}, "
                   f"Circularity: {circularity:.2f}, "
                   f"Aspect Ratio: {aspect_ratio:.2f}")
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error analyzing contour shape: {e}")
        raise

def find_owl_contours(binary_mask):
    """
    Find and analyze potential owl contours in binary mask.
    """
    try:
        logger.info("Starting owl contour detection")
        
        contours, _ = cv2.findContours(
            binary_mask, 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        logger.info(f"Found {len(contours)} initial contours")
        
        compartment_area = binary_mask.shape[0] * binary_mask.shape[1]
        
        contour_data = []
        for contour in contours:
            metrics = analyze_contour_shape(contour, compartment_area)
            contour_data.append({
                "contour": contour,
                "metrics": metrics
            })
        
        return contour_data
        
    except Exception as e:
        logger.error(f"Error finding owl contours: {e}")
        raise

def check_brightness(contour, image, base_image, threshold_adjustment=1.0):
    """
    Check if the region inside contour is brighter than base image.
    
    Args:
        contour: OpenCV contour
        image: Current image
        base_image: Base reference image
        threshold_adjustment: Multiplier for brightness threshold (used in testing)
    """
    try:
        logger.info("Checking region brightness")
        
        mask = np.zeros_like(image)
        cv2.drawContours(mask, [contour], 0, 255, -1)
        
        current_brightness = np.mean(image[mask == 255])
        base_brightness = np.mean(base_image[mask == 255])
        
        brightness_diff = current_brightness - base_brightness
        threshold = 20 * threshold_adjustment
        is_brighter = brightness_diff > threshold
        
        logger.info(f"Brightness analysis - Current: {current_brightness:.2f}, "
                   f"Base: {base_brightness:.2f}, Difference: {brightness_diff:.2f}, "
                   f"Threshold: {threshold:.2f}, Is Brighter: {is_brighter}")
        
        return is_brighter, brightness_diff
        
    except Exception as e:
        logger.error(f"Error checking brightness: {e}")
        raise

def detect_owl_in_box(new_image, base_image, config, is_test=False):
    """
    Main function to detect owl presence in box.
    
    Args:
        new_image (PIL.Image): New captured image
        base_image (PIL.Image): Base reference image
        config (dict): Camera configuration parameters
        is_test (bool): Whether this is a test image
        
    Returns:
        tuple: (bool, dict) - (is_owl_present, detection_info)
    """
    try:
        logger.info(f"Starting owl detection process (Test Mode: {is_test})")
        
        # Validate and prepare images
        new_cv, base_cv = prepare_images(
            new_image, 
            base_image,
            expected_roi=config.get("roi") if not is_test else None,
            is_test=is_test
        )
        
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
        
        # Adjust sensitivity for test mode
        sensitivity = 0.8 if is_test else 1.0
        threshold_adjustment = 0.9 if is_test else 1.0
        
        # Analyze differences
        binary_mask, diff_metrics = analyze_compartment_differences(
            new_left, 
            base_left,
            sensitivity=sensitivity
        )
        
        # Find and analyze contours
        contour_data = find_owl_contours(binary_mask)
        
        # Check each candidate contour
        owl_candidates = []
        for data in contour_data:
            is_brighter, brightness_diff = check_brightness(
                data["contour"],
                new_left,
                base_left,
                threshold_adjustment=threshold_adjustment
            )
            
            metrics = data["metrics"]
            if (is_brighter and
                metrics["circularity"] > min_circularity and
                min_aspect_ratio < metrics["aspect_ratio"] < max_aspect_ratio and
                metrics["area_ratio"] > min_area_ratio and
                brightness_diff > brightness_threshold):
                
                owl_candidates.append({
                    **metrics,
                    "brightness_diff": brightness_diff
                })
        
        is_owl_present = len(owl_candidates) > 0
        
        detection_info = {
            "confidence": max([c["area_ratio"] for c in owl_candidates], default=0),
            "location": "left_compartment",
            "candidates": owl_candidates,
            "diff_metrics": diff_metrics,
            "is_test": is_test,
            "sensitivity_used": sensitivity,
            "threshold_adjustment": threshold_adjustment
        }
        
        logger.info(f"Owl detection completed - Owl Present: {is_owl_present}, "
                   f"Candidates: {len(owl_candidates)}, "
                   f"Confidence: {detection_info['confidence']:.2f}")
        
        return is_owl_present, detection_info
        
    except Exception as e:
        logger.error(f"Error in owl detection: {e}")
        return False, {"error": str(e), "is_test": is_test}

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
        
        # Test with is_test=True
        result, info = detect_owl_in_box(
            test_new, 
            test_base, 
            test_config,
            is_test=True
        )
        
        print(f"Test Detection Result: {result}")
        print(f"Test Detection Info: {info}")
        
    except Exception as e:
        print(f"Test failed: {e}")