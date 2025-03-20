# File: utilities/owl_detection_utils.py
# Purpose: Detect owls in camera images using advanced shape and motion analysis with improved confidence metrics
# 
# Updates:
# - Enhanced shape detection parameters for more accurate owl identification
# - Improved night mode detection to reduce false positives
# - Updated region analysis for more precise location-based detection
# - Made threshold adjustments more dynamic based on lighting conditions

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
from utilities.time_utils import get_current_lighting_condition

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
        # Get current lighting condition for logging
        lighting_condition = get_current_lighting_condition()
        
        # Convert to numpy arrays for OpenCV processing
        base_cv = cv2.cvtColor(np.array(base_image), cv2.COLOR_RGB2GRAY)
        new_cv = cv2.cvtColor(np.array(new_image), cv2.COLOR_RGB2GRAY)
        
        # Calculate absolute difference
        diff = cv2.absdiff(new_cv, base_cv)
        
        # Apply Gaussian blur to reduce noise
        blurred_diff = cv2.GaussianBlur(diff, (5, 5), 0)
        
        # Create binary mask of changed pixels
        # For night mode, use a more aggressive threshold to reduce noise
        if lighting_condition == "night":
            # Apply more aggressive threshold for night mode to reduce noise
            adjusted_threshold = threshold * 1.2  # 20% higher threshold at night
            _, binary_mask = cv2.threshold(
                blurred_diff,
                adjusted_threshold,
                255,
                cv2.THRESH_BINARY
            )
        else:
            # Standard threshold for day mode
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
            },
            'lighting_condition': lighting_condition
        }
        
        return results, binary_mask
        
    except Exception as e:
        logger.error(f"Error analyzing image differences: {e}")
        raise

def find_owl_candidates(binary_mask, config, lighting_condition=None):
    """
    Find regions in the binary mask that could potentially be owls.
    Updated with more stringent criteria and lighting-specific adjustments.
    
    Args:
        binary_mask (numpy.ndarray): Binary mask of changed pixels
        config (dict): Camera configuration with motion detection parameters
        lighting_condition (str, optional): Current lighting condition
        
    Returns:
        list: List of owl candidate regions with shape characteristics
    """
    try:
        # If lighting condition not provided, get it
        if lighting_condition is None:
            lighting_condition = get_current_lighting_condition()
        
        # Get the appropriate settings based on lighting condition
        if lighting_condition == 'day' and 'day_settings' in config and 'motion_detection' in config['day_settings']:
            motion_config = config['day_settings']['motion_detection']
            logger.debug(f"Using day motion detection settings")
        elif lighting_condition == 'night' and 'night_settings' in config and 'motion_detection' in config['night_settings']:
            motion_config = config['night_settings']['motion_detection']
            logger.debug(f"Using night motion detection settings")
        else:
            # Fall back to standard motion detection config
            motion_config = config.get("motion_detection", {})
            logger.debug(f"Using standard motion detection settings")
        
        # Apply morphological operations to clean up noise
        # More aggressive cleaning for night mode
        if lighting_condition == 'night':
            # Use a larger kernel for night mode to remove more noise
            kernel = np.ones((5, 5), np.uint8)
            binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel)
            binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel)
        else:
            # Standard cleaning for day mode
            kernel = np.ones((3, 3), np.uint8)
            binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel)
            binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours in the binary mask
        contours, _ = cv2.findContours(
            binary_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Get configuration parameters for shape filtering
        min_circularity = motion_config.get("min_circularity", 0.5)
        min_aspect_ratio = motion_config.get("min_aspect_ratio", 0.5)
        max_aspect_ratio = motion_config.get("max_aspect_ratio", 2.0)
        min_area_ratio = motion_config.get("min_area_ratio", 0.01)
        brightness_threshold = motion_config.get("brightness_threshold", 20)
        
        # Apply more stringent criteria for night mode to reduce false positives
        if lighting_condition == 'night':
            min_circularity *= 1.1  # 10% higher circularity requirement
            min_area_ratio *= 1.2   # 20% higher minimum area
            brightness_threshold *= 1.1  # 10% higher brightness threshold
        
        # Log parameters being used
        logger.debug(
            f"Motion parameters ({lighting_condition}): circularity: {min_circularity}, "
            f"aspect ratio: {min_aspect_ratio}-{max_aspect_ratio}, "
            f"area ratio: {min_area_ratio}, brightness: {brightness_threshold}"
        )
        
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
        
        logger.debug(f"Found {len(owl_candidates)} owl candidates in {lighting_condition} condition")
        return owl_candidates
        
    except Exception as e:
        logger.error(f"Error finding owl candidates: {e}")
        return []

def detect_owl_in_box(new_image, base_image, config, is_test=False, camera_name=None):
    """
    Detect if an owl is present by comparing base and new images with confidence metrics.
    Updated with improved lighting-specific detection and false positive reduction.
    
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
            
        # Get current lighting condition
        lighting_condition = get_current_lighting_condition()
        
        # Skip detection during transition periods unless in test mode
        if lighting_condition == 'transition' and not is_test:
            logger.info(f"Skipping detection for {camera_name} during transition period")
            return False, {
                "is_owl_present": False,
                "owl_confidence": 0.0,
                "consecutive_owl_frames": 0,
                "pixel_change": 0.0,
                "luminance_change": 0.0,
                "lighting_condition": lighting_condition
            }
        
        # Get lighting-specific threshold settings
        if lighting_condition == 'day' and 'day_settings' in config:
            threshold = config['day_settings'].get("luminance_threshold", 30)
            logger.debug(f"Using day luminance threshold: {threshold}")
        elif lighting_condition == 'night' and 'night_settings' in config:
            threshold = config['night_settings'].get("luminance_threshold", 30)
            logger.debug(f"Using night luminance threshold: {threshold}")
        else:
            # Fallback to standard threshold
            threshold = config.get("luminance_threshold", 30)
            logger.debug(f"Using standard luminance threshold: {threshold}")
        
        # Apply special adjustments for Wyze Internal Camera at night
        # This camera is particularly prone to false positives at night
        if camera_name == "Wyze Internal Camera" and lighting_condition == "night":
            # Increase threshold for Wyze internal camera at night to reduce false positives
            threshold = threshold * 1.2  # 20% higher threshold
            logger.debug(f"Applied Wyze-specific night threshold boost: {threshold:.1f}")
        
        # Analyze image differences with improved thresholding
        diff_results, binary_mask = analyze_image_differences(
            base_image,
            new_image,
            threshold,
            config
        )
        
        # Find potential owl candidates using appropriate settings
        owl_candidates = find_owl_candidates(binary_mask, config, lighting_condition)
        
        # Compile detection data for confidence calculation
        detection_data = {
            "pixel_change": diff_results["pixel_change"],
            "luminance_change": diff_results["luminance_change"],
            "max_luminance": diff_results["max_luminance"],
            "owl_candidates": owl_candidates,
            "diff_metrics": diff_results["diff_metrics"],
            "lighting_condition": lighting_condition
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
            
            # Get appropriate confidence threshold based on lighting condition
            if lighting_condition == 'day' and 'day_settings' in config:
                threshold = config['day_settings'].get("owl_confidence_threshold", 60.0)
            elif lighting_condition == 'night' and 'night_settings' in config:
                threshold = config['night_settings'].get("owl_confidence_threshold", 60.0)
            else:
                threshold = config.get("owl_confidence_threshold", 60.0)
                
            # Update config with current threshold for is_owl_detected
            detection_config = config.copy()
            detection_config["owl_confidence_threshold"] = threshold
            
            # Determine if owl is present based on confidence
            is_owl_present = is_owl_detected(
                owl_confidence,
                camera_name,
                detection_config
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
                "diff_metrics": diff_results["diff_metrics"],
                "lighting_condition": lighting_condition,
                "threshold_used": threshold
            }
            
            # Log detection result with confidence
            if is_owl_present:
                logger.info(
                    f"Owl detected in {camera_name} with {owl_confidence:.1f}% confidence "
                    f"({consecutive_frames} consecutive frames) - {lighting_condition} mode"
                )
            else:
                logger.debug(
                    f"No owl detected in {camera_name}: {owl_confidence:.1f}% confidence "
                    f"({confidence_results.get('consecutive_owl_frames', 0)} consecutive frames) - {lighting_condition} mode"
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
                "diff_metrics": diff_results["diff_metrics"],
                "lighting_condition": lighting_condition
            }
            
            logger.debug(
                f"Test mode detection: Owl present = {is_owl_present}, "
                f"candidates: {len(owl_candidates)}, lighting: {lighting_condition}"
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
            "owl_candidates": [],
            "lighting_condition": get_current_lighting_condition()
        }

# Test the module
if __name__ == "__main__":
    try:
        # Basic configuration for testing
        test_config = {
            "day_settings": {
                "luminance_threshold": 30,
                "motion_detection": {
                    "min_circularity": 0.5,
                    "min_aspect_ratio": 0.5,
                    "max_aspect_ratio": 2.0,
                    "min_area_ratio": 0.01,
                    "brightness_threshold": 20
                }
            },
            "night_settings": {
                "luminance_threshold": 20,
                "motion_detection": {
                    "min_circularity": 0.6,
                    "min_aspect_ratio": 0.6,
                    "max_aspect_ratio": 1.8,
                    "min_area_ratio": 0.02,
                    "brightness_threshold": 25
                }
            }
        }
        
        # Log that we're in test mode
        logger.info("Testing owl detection utility with day/night settings...")
        
        # Test with two identical images - should not detect owl
        try:
            import pyautogui
            
            # Capture test image
            test_image = pyautogui.screenshot(region=(0, 0, 640, 480))
            
            # Test detection with identical images for day settings
            logger.info("Testing with day settings...")
            is_present_day, info_day = detect_owl_in_box(
                test_image,
                test_image,
                test_config,
                is_test=True
            )
            
            logger.info(f"Day detection result (identical images): {is_present_day}")
            logger.info(f"Day pixel change: {info_day['pixel_change']:.2f}%")
            logger.info(f"Day number of candidates: {len(info_day['owl_candidates'])}")
            
            # Test night settings
            logger.info("Testing with night settings...")
            is_present_night, info_night = detect_owl_in_box(
                test_image,
                test_image,
                test_config,
                is_test=True
            )
            
            logger.info(f"Night detection result (identical images): {is_present_night}")
            logger.info(f"Night pixel change: {info_night['pixel_change']:.2f}%")
            logger.info(f"Night number of candidates: {len(info_night['owl_candidates'])}")
            
        except ImportError:
            logger.warning("Could not import pyautogui, skipping screenshot test")
            
        logger.info("Owl detection utility test complete")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise