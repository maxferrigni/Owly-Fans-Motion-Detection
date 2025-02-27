# File: utilities/owl_detection_utils.py
# Purpose: Specialized detection algorithms for owl presence with enhanced metrics and confidence scoring

import cv2
import numpy as np
from PIL import Image
from utilities.logging_utils import get_logger
from utilities.confidence_utils import calculate_owl_confidence, is_owl_detected

logger = get_logger()

def validate_images(new_image, base_image, expected_roi=None, is_test=False):
    """Validate images meet requirements for processing."""
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
                return False, f"Image too small for testing: {new_image.size}"

        return True, "Images validated successfully"

    except Exception as e:
        logger.error(f"Error validating images: {e}")
        return False, f"Validation error: {str(e)}"

def detect_owl_in_box(new_image, base_image, config, is_test=False, sensitivity=1.0, camera_name=None):
    """
    Detect the presence of an owl in the new image compared to the base image.
    Now includes confidence-based detection system.
    
    Args:
        new_image (PIL.Image): New image to check for owl.
        base_image (PIL.Image): Base reference image.
        config (dict): Configuration dictionary.
        is_test (bool): Whether this is a test image.
        sensitivity (float): Owl detection sensitivity.
        camera_name (str): Name of the camera (needed for temporal confidence)
        
    Returns:
        tuple: (bool, dict) - (is_owl_present, detection_info)
    """
    try:
        # Validate images
        is_valid, validation_message = validate_images(
            new_image, base_image, is_test=is_test
        )
        if not is_valid:
            logger.error(f"Image validation failed: {validation_message}")
            return False, {
                "error": validation_message,
                "pixel_change": 0.0,
                "luminance_change": 0.0,
                "is_test": is_test,
                "owl_confidence": 0.0,
                "consecutive_owl_frames": 0,
                "confidence_factors": {
                    "shape_confidence": 0.0,
                    "motion_confidence": 0.0,
                    "temporal_confidence": 0.0,
                    "camera_confidence": 0.0
                }
            }

        logger.info(f"Starting owl detection process (Test Mode: {is_test})")
        logger.info("Starting image preparation for owl detection")

        # Convert images to grayscale numpy arrays
        new_array = np.array(new_image.convert('L'))
        base_array = np.array(base_image.convert('L'))

        # Log image sizes
        logger.info(f"Image sizes - New: {new_array.shape}, Base: {base_array.shape}")

        # Calculate center point for image division
        width = new_array.shape[1]  # Shape is (height, width)
        center_x = width // 2

        # Split the image into left and right compartments
        left_new = new_array[:, :center_x]
        right_new = new_array[:, center_x:]
        left_base = base_array[:, :center_x]
        right_base = base_array[:, center_x:]

        # Calculate absolute differences between new and base images
        left_diff = cv2.absdiff(left_new, left_base)
        right_diff = cv2.absdiff(right_new, right_base)

        # Create full difference array for overall metrics
        full_diff = cv2.absdiff(new_array, base_array)

        # Threshold the differences to highlight significant changes
        threshold = config["motion_detection"]["brightness_threshold"]
        _, left_thresh = cv2.threshold(left_diff, threshold, 255, cv2.THRESH_BINARY)
        _, right_thresh = cv2.threshold(right_diff, threshold, 255, cv2.THRESH_BINARY)

        # Apply noise reduction
        kernel = np.ones((3,3), np.uint8)
        left_thresh = cv2.morphologyEx(left_thresh, cv2.MORPH_OPEN, kernel)
        right_thresh = cv2.morphologyEx(right_thresh, cv2.MORPH_OPEN, kernel)

        # Find contours of the shapes in the thresholded images
        left_contours, _ = cv2.findContours(
            left_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        right_contours, _ = cv2.findContours(
            right_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Combine contours from both compartments
        all_contours = left_contours + right_contours
        total_area = new_array.shape[0] * new_array.shape[1]  # Total image area
        contour_data = []

        # Analyze contours to identify potential owl candidates
        for contour in all_contours:
            area = cv2.contourArea(contour)
            area_ratio = area / total_area
            perimeter = cv2.arcLength(contour, True)
            
            # Calculate shape characteristics
            circularity = (4 * np.pi * area) / (perimeter * perimeter) if perimeter > 0 else 0
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h if h > 0 else 0
            
            # Calculate brightness difference
            mask = np.zeros(new_array.shape, dtype=np.uint8)
            cv2.drawContours(mask, [contour], -1, 255, -1)
            new_mean = cv2.mean(new_array, mask=mask)[0]
            base_mean = cv2.mean(base_array, mask=mask)[0]
            brightness_diff = abs(new_mean - base_mean)

            # Only add contours that meet minimum criteria for owl shape
            if (
                circularity >= config["motion_detection"]["min_circularity"] and
                config["motion_detection"]["min_aspect_ratio"] <= aspect_ratio <= config["motion_detection"]["max_aspect_ratio"] and
                area_ratio >= config["motion_detection"]["min_area_ratio"]
            ):
                logger.info(
                    f"Potential owl contour found - Area Ratio: {area_ratio:.2f}, "
                    f"Circularity: {circularity:.2f}, "
                    f"Aspect Ratio: {aspect_ratio:.2f}, "
                    f"Brightness Diff: {brightness_diff:.2f}"
                )
                contour_data.append({
                    "area_ratio": area_ratio,
                    "circularity": circularity,
                    "aspect_ratio": aspect_ratio,
                    "brightness_diff": brightness_diff,
                    "position": (x, y),
                    "size": (w, h)
                })

        # Calculate overall image metrics
        mean_diff = np.mean(full_diff)
        std_diff = np.std(full_diff)
        significant_pixels = np.sum(full_diff > threshold) / total_area

        # Prepare detection info with metrics for confidence calculation
        owl_candidates = [c for c in contour_data if c["area_ratio"] >= config["motion_detection"]["min_area_ratio"]]
        
        # Prepare region analysis for confidence calculation
        height, width = full_diff.shape
        regions = {
            'top': full_diff[:height//3, :],
            'middle': full_diff[height//3:2*height//3, :],
            'bottom': full_diff[2*height//3:, :]
        }
        
        region_metrics = {}
        for region_name, region_data in regions.items():
            region_metrics[region_name] = {
                'mean_luminance': np.mean(region_data),
                'pixel_change_ratio': np.sum(region_data > threshold) / region_data.size
            }
        
        # Prepare detection metrics
        diff_metrics = {
            "mean_difference": mean_diff,
            "std_difference": std_diff,
            "significant_pixels": significant_pixels,
            "threshold_used": threshold,
            "region_metrics": region_metrics
        }
        
        # Prepare detection info for confidence calculation
        detection_info = {
            "owl_candidates": owl_candidates,
            "diff_metrics": diff_metrics,
            "pixel_change": significant_pixels * 100,  # Convert to percentage
            "luminance_change": mean_diff,
            "is_test": is_test
        }

        # Calculate owl confidence
        if camera_name is None:
            # If camera name not provided, try to infer from config or use a default
            camera_name = "Unknown Camera"
            
        confidence_results = calculate_owl_confidence(detection_info, camera_name, config)
        
        # Determine if owl is present based on confidence
        is_owl_present = is_owl_detected(
            confidence_results["owl_confidence"], 
            camera_name, 
            config
        )
        
        # Update detection info with confidence results
        detection_info.update({
            "is_owl_present": is_owl_present,
            "motion_detected": is_owl_present,  # For backward compatibility
            "owl_confidence": confidence_results["owl_confidence"],
            "consecutive_owl_frames": confidence_results["consecutive_owl_frames"],
            "confidence_factors": confidence_results["confidence_factors"]
        })

        logger.info(
            f"Owl detection completed - Owl Present: {is_owl_present}, "
            f"Confidence: {confidence_results['owl_confidence']:.1f}%, "
            f"Consecutive Frames: {confidence_results['consecutive_owl_frames']}"
        )

        return is_owl_present, detection_info

    except Exception as e:
        logger.error(f"Error in owl detection: {e}")
        return False, {
            "error": str(e),
            "is_test": is_test,
            "pixel_change": 0.0,
            "luminance_change": 0.0,
            "motion_detected": False,
            "is_owl_present": False,
            "owl_confidence": 0.0,
            "consecutive_owl_frames": 0,
            "confidence_factors": {
                "shape_confidence": 0.0,
                "motion_confidence": 0.0,
                "temporal_confidence": 0.0,
                "camera_confidence": 0.0,
                "error": str(e)
            }
        }

if __name__ == "__main__":
    # Test the detection
    try:
        # Create test configuration
        test_config = {
            "motion_detection": {
                "min_circularity": 0.5,
                "min_aspect_ratio": 0.5,
                "max_aspect_ratio": 2.0,
                "min_area_ratio": 0.2,
                "brightness_threshold": 20
            },
            "threshold_percentage": 0.05,
            "luminance_threshold": 40,
            "owl_confidence_threshold": 60
        }

        # Load test images if available
        try:
            test_new = Image.open("test_new.jpg")
            test_base = Image.open("test_base.jpg")

            # Test with is_test=True
            result, info = detect_owl_in_box(
                test_new,
                test_base,
                test_config,
                is_test=True,
                camera_name="Test Camera"
            )

            logger.info(f"Test detection result: {result}")
            logger.info(f"Detection info: {info}")
            logger.info(f"Confidence: {info.get('owl_confidence', 0)}%")

        except FileNotFoundError:
            logger.warning("Test images not found. Create test_new.jpg and test_base.jpg to run tests.")

    except Exception as e:
        logger.error(f"Owl detection test failed: {e}")
        raise