# File: utilities/owl_detection_utils.py
# Purpose: Detect owls in camera images using advanced shape and motion analysis with confidence metrics

import cv2
import numpy as np
from PIL import Image
import os
import logging
from datetime import datetime
import pytz

# Import utilities
from utilities.logging_utils import get_logger
from utilities.confidence_utils import calculate_owl_confidence, is_owl_detected

# Initialize logger
logger = get_logger()

def analyze_image_differences(base_image, new_image, threshold, config):
    """
    Analyze the differences between base and new images.
    
    Args:
        base_image (PIL.Image): Base reference image
        new_image (PIL.Image): New image to check
        threshold (int): Luminance threshold for change detection
        config (dict): Camera configuration
        
    Returns:
        dict: Analysis results including:
            - pixel_change: Percentage of pixels that changed
            - luminance_change: Average luminance change
            - diff_metrics: Additional difference metrics
    """
    try:
        # Convert to numpy arrays for OpenCV processing
        base_cv = cv2.cvtColor(np.array(base_image), cv2.COLOR_RGB2GRAY)
        new_cv = cv2.cvtColor(np.array(new_image), cv2.COLOR_RGB2GRAY)
        
        # Calculate absolute difference
        diff = cv2.absdiff(new_cv, base_cv)
        
        # Apply Gaussian blur to reduce noise
        blurred_diff = cv2.GaussianBlur(diff, (5, 5), 0)
        
        # Create binary mask of changed pixels
        _, binary_mask = cv2.threshold(
            blurred_diff,
            threshold,
            255,
            cv2.THRESH_BINARY
        )
        
        # Calculate pixel change percentage
        height, width = diff.shape
        total_pixels = height * width
        changed_pixels = np.sum(binary_mask > 0)
        pixel_change_percentage = (changed_pixels / total_pixels) * 100
        
        # Calculate average luminance change
        mean_luminance_change = np.mean(diff)
        max_luminance_change = np.max(diff)
        
        # Calculate region-specific metrics
        # Divide the image into regions (top, middle, bottom)
        regions = {
            'top': diff[:height//3, :],
            'middle': diff[height//3:2*height//3, :],
            'bottom': diff[2*height//3:, :]
        }
        
        region_metrics = {}
        for region_name, region_data in regions.items():
            region_changed = np.sum(region_data > threshold)
            region_total = region_data.size
            
            region_metrics[region_name] = {
                'mean_luminance': np.mean(region_data),
                'max_luminance': np.max(region_data),
                'pixel_change': (region_changed / region_total) * 100
            }
        
        # Return comprehensive results
        results = {
            'pixel_change': pixel_change_percentage,
            'luminance_change': mean_luminance_change,
            'max_luminance': max_luminance_change,
            'diff_metrics': {
                'binary_mask': binary_mask,
                'region_metrics': region_metrics
            }
        }
        
        return results, binary_mask
        
    except Exception as e:
        logger.error(f"Error analyzing image differences: {e}")
        raise

def find_owl_candidates(binary_mask, config):
    """
    Find regions in the binary mask that could potentially be owls.
    
    Args:
        binary_mask (numpy.ndarray): Binary mask of changed pixels
        config (dict): Camera configuration with motion detection parameters
        
    Returns:
        list: List of owl candidate regions with shape characteristics
    """
    try:
        # Find contours in the binary mask
        contours, _ = cv2.findContours(
            binary_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Get configuration parameters for shape filtering
        motion_config = config["motion_detection"]
        min_circularity = motion_config["min_circularity"]
        min_aspect_ratio = motion_config["min_aspect_ratio"]
        max_aspect_ratio = motion_config["max_aspect_ratio"]
        min_area_ratio = motion_config["min_area_ratio"]
        brightness_threshold = motion_config["brightness_threshold"]
        
        # Calculate image dimensions for relative measurements
        height, width = binary_mask.shape
        total_area = height * width
        
        # Filter and analyze contours
        owl_candidates = []
        
        for contour in contours:
            # Calculate contour area and perimeter
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            
            # Skip if area or perimeter is too small
            if area < 10 or perimeter < 10:
                continue
                
            # Calculate shape characteristics
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h if h > 0 else 0
            area_ratio = area / total_area
            
            # Calculate circularity (4π × Area / Perimeter²)
            # A perfect circle has circularity of 1
            circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
            
            # Filter based on shape characteristics
            if (circularity >= min_circularity and 
                min_aspect_ratio <= aspect_ratio <= max_aspect_ratio and
                area_ratio >= min_area_ratio):
                
                # Calculate average brightness within contour
                mask = np.zeros(binary_mask.shape, dtype=np.uint8)
                cv2.drawContours(mask, [contour], 0, 255, -1)
                brightness = np.mean(cv2.bitwise_and(binary_mask, mask))
                
                # Only add if brightness meets threshold
                if brightness >= brightness_threshold:
                    # Add this candidate
                    owl_candidates.append({
                        'contour': contour,
                        'circularity': circularity,
                        'aspect_ratio': aspect_ratio,
                        'area_ratio': area_ratio,
                        'position': (x, y, w, h),
                        'brightness_diff': brightness
                    })
        
        # Sort candidates by area ratio (largest first)
        owl_candidates.sort(key=lambda x: x['area_ratio'], reverse=True)
        
        logger.debug(f"Found {len(owl_candidates)} owl candidates")
        return owl_candidates
        
    except Exception as e:
        logger.error(f"Error finding owl candidates: {e}")
        return []

def detect_owl_in_box(new_image, base_image, config, is_test=False, camera_name=None):
    """
    Detect if an owl is present by comparing base and new images with confidence metrics.
    
    Args:
        new_image (PIL.Image): New image to check
        base_image (PIL.Image): Base reference image
        config (dict): Camera configuration dictionary
        is_test (bool, optional): Whether this is a test detection
        camera_name (str, optional): Name of the camera for tracking
        
    Returns:
        tuple: (is_owl_present, detection_info)
            - is_owl_present (bool): True if owl is detected with sufficient confidence
            - detection_info (dict): Detailed detection information with confidence metrics
    """
    try:
        # Ensure images are in RGB mode
        if new_image.mode != 'RGB':
            new_image = new_image.convert('RGB')
            
        if base_image.mode != 'RGB':
            base_image = base_image.convert('RGB')
            
        # Get threshold from config
        threshold = config.get("luminance_threshold", 30)
        
        # Analyze image differences
        diff_results, binary_mask = analyze_image_differences(
            base_image,
            new_image,
            threshold,
            config
        )
        
        # Find potential owl candidates
        owl_candidates = find_owl_candidates(binary_mask, config)
        
        # Compile detection data for confidence calculation
        detection_data = {
            "pixel_change": diff_results["pixel_change"],
            "luminance_change": diff_results["luminance_change"],
            "max_luminance": diff_results["max_luminance"],
            "owl_candidates": owl_candidates,
            "diff_metrics": diff_results["diff_metrics"]
        }
        
        # Calculate owl confidence score if camera_name is provided
        if camera_name:
            # Use confidence utils to calculate overall confidence
            confidence_results = calculate_owl_confidence(
                detection_data,
                camera_name,
                config
            )
            
            # Extract confidence metrics
            owl_confidence = confidence_results.get("owl_confidence", 0.0)
            consecutive_frames = confidence_results.get("consecutive_owl_frames", 0)
            confidence_factors = confidence_results.get("confidence_factors", {})
            
            # Determine if owl is present based on confidence
            is_owl_present = is_owl_detected(
                owl_confidence,
                camera_name,
                config
            )
            
            # Create comprehensive detection info
            detection_info = {
                "is_owl_present": is_owl_present,
                "owl_confidence": owl_confidence,
                "consecutive_owl_frames": consecutive_frames,
                "confidence_factors": confidence_factors,
                "pixel_change": diff_results["pixel_change"],
                "luminance_change": diff_results["luminance_change"],
                "owl_candidates": owl_candidates,
                "diff_metrics": diff_results["diff_metrics"]
            }
            
            # Log detection result with confidence
            if is_owl_present:
                logger.info(
                    f"Owl detected in {camera_name} with {owl_confidence:.1f}% confidence "
                    f"({consecutive_frames} consecutive frames)"
                )
            else:
                logger.debug(
                    f"No owl detected in {camera_name}: {owl_confidence:.1f}% confidence "
                    f"({confidence_results.get('consecutive_owl_frames', 0)} consecutive frames)"
                )
                
        else:
            # Simplified detection for test mode or when camera_name is not provided
            # In this case, determine presence based on candidates only
            is_owl_present = len(owl_candidates) > 0
            
            # Create basic detection info
            detection_info = {
                "is_owl_present": is_owl_present,
                "owl_confidence": 0.0,  # No confidence calculation
                "consecutive_owl_frames": 0,
                "pixel_change": diff_results["pixel_change"],
                "luminance_change": diff_results["luminance_change"],
                "owl_candidates": owl_candidates,
                "diff_metrics": diff_results["diff_metrics"]
            }
            
            logger.debug(
                f"Test mode detection: Owl present = {is_owl_present}, "
                f"candidates: {len(owl_candidates)}"
            )
                
        return is_owl_present, detection_info
        
    except Exception as e:
        logger.error(f"Error detecting owl: {e}")
        # Return simplified error result
        return False, {
            "is_owl_present": False,
            "error": str(e),
            "pixel_change": 0.0,
            "luminance_change": 0.0,
            "owl_candidates": []
        }

# Test the module
if __name__ == "__main__":
    try:
        # Basic configuration for testing
        test_config = {
            "luminance_threshold": 30,
            "motion_detection": {
                "min_circularity": 0.5,
                "min_aspect_ratio": 0.5,
                "max_aspect_ratio": 2.0,
                "min_area_ratio": 0.01,
                "brightness_threshold": 20
            }
        }
        
        # Log that we're in test mode
        logger.info("Testing owl detection utility...")
        
        # Test with two identical images - should not detect owl
        try:
            import pyautogui
            
            # Capture test image
            test_image = pyautogui.screenshot(region=(0, 0, 640, 480))
            
            # Test detection with identical images
            is_present, info = detect_owl_in_box(
                test_image,
                test_image,
                test_config,
                is_test=True
            )
            
            logger.info(f"Test detection result (identical images): {is_present}")
            logger.info(f"Pixel change: {info['pixel_change']:.2f}%")
            logger.info(f"Number of candidates: {len(info['owl_candidates'])}")
            
        except ImportError:
            logger.warning("Could not import pyautogui, skipping screenshot test")
            
        logger.info("Owl detection utility test complete")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise