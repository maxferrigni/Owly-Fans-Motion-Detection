# File: utilities/owl_detection_utils.py
# Purpose: Specialized detection algorithms for owl presence with enhanced metrics

import cv2
import numpy as np
from PIL import Image
from utilities.logging_utils import get_logger

logger = get_logger()

def validate_images(new_image, base_image, expected_roi=None, is_test=False):
    """Validate images meet requirements for processing."""
    try:
        # Basic image validation
        if not isinstance(new_image, Image.Image) or not isinstance(base_image, Image.Image):
            return False, "Invalid image types provided"

        # Size checks
        if new_image.size!= base_image.size:
            return False, f"Image size mismatch: {new_image.size} vs {base_image.size}"

        # ROI validation if provided
        if expected_roi:
            expected_width = abs(expected_roi - expected_roi)
            expected_height = abs(expected_roi - expected_roi)
            expected_size = (expected_width, expected_height)

            if new_image.size!= expected_size:
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

def detect_owl_in_box(new_image, base_image, config, is_test=False, sensitivity=1.0):
    """
    Detect the presence of an owl in the new image compared to the base image.

    Args:
        new_image (PIL.Image): New image to check for owl.
        base_image (PIL.Image): Base reference image.
        config (dict): Configuration dictionary.
        is_test (bool): Whether this is a test image.
        sensitivity (float): Owl detection sensitivity.

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
            return False, {"error": validation_message}

        logger.info(f"Starting owl detection process (Test Mode: {is_test})")
        logger.info("Starting image preparation for owl detection")

        # Convert images to grayscale numpy arrays
        new_array = np.array(new_image.convert('L'))
        base_array = np.array(base_image.convert('L'))

        # Log image sizes
        logger.info(f"Image sizes - New: {new_array.shape}, Base: {base_array.shape}")

        # Split the image into left and right compartments
        center_x = new_array.shape // 2
        left_new = new_array[:,:center_x]
        right_new = new_array[:, center_x:]
        left_base = base_array[:,:center_x]
        right_base = base_array[:, center_x:]

        # Calculate absolute differences between new and base images
        left_diff = cv2.absdiff(left_new, left_base)
        right_diff = cv2.absdiff(right_new, right_base)

        # Threshold the differences to highlight significant changes
        threshold = config["motion_detection"]["brightness_threshold"]
        _, left_thresh = cv2.threshold(left_diff, threshold, 255, cv2.THRESH_BINARY)
        _, right_thresh = cv2.threshold(right_diff, threshold, 255, cv2.THRESH_BINARY)

        # Find contours of the shapes in the thresholded images
        left_contours, _ = cv2.findContours(
            left_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        right_contours, _ = cv2.findContours(
            right_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Combine contours from both compartments
        all_contours = left_contours + right_contours
        contour_data = []

        # Analyze contours to identify potential owl candidates
        for contour in all_contours:
            area_ratio = cv2.contourArea(contour) / (new_array.shape * new_array.shape)
            circularity = (4 * np.pi * cv2.contourArea(contour)) / (cv2.arcLength(contour, True) ** 2) if cv2.arcLength(contour, True) > 0 else 0
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h if h > 0 else 0
            
            # Calculate brightness difference
            mask = np.zeros(new_array.shape, dtype=np.uint8)
            cv2.drawContours(mask, [contour], -1, 255, -1)
            brightness_diff = cv2.mean(new_array, mask=mask) - cv2.mean(base_array, mask=mask)

            # Log only when a contour meets the criteria
            if (
                circularity >= config["motion_detection"]["min_circularity"] and
                config["motion_detection"]["min_aspect_ratio"] <= aspect_ratio <= config["motion_detection"]["max_aspect_ratio"] and
                area_ratio >= config["motion_detection"]["min_area_ratio"]
            ):
                logger.info(
                    f"Contour metrics - Area Ratio: {area_ratio:.2f}, "
                    f"Circularity: {circularity:.2f}, "
                    f"Aspect Ratio: {aspect_ratio:.2f}, "
                    f"Brightness Diff: {brightness_diff:.2f}"
                )
                contour_data.append({
                    "area_ratio": area_ratio,
                    "circularity": circularity,
                    "aspect_ratio": aspect_ratio,
                    "brightness_diff": brightness_diff
                })

        # Determine owl presence based on detected contours
        is_owl_present = len(contour_data) > 0
        owl_candidates = [c for c in contour_data if c["area_ratio"] >= config["motion_detection"]["min_area_ratio"]]

        # Calculate confidence based on number of candidates and their area ratios
        confidence = sum(c["area_ratio"] for c in owl_candidates)
        
        # Prepare detection metrics
        diff_metrics = {
            "mean_difference": np.mean(left_diff) if left_diff.any() else 0.0,
            "significant_pixels": np.mean(left_thresh) / 255 if left_thresh.any() else 0.0,
            "threshold": threshold
        }
        
        # Prepare detection info
        detection_info = {
            "confidence": confidence,
            "owl_candidates": owl_candidates,
            "largest_candidate": owl_candidates if owl_candidates else None,
            "is_test": is_test,
            "sensitivity_used": sensitivity,
            "diff_metrics": diff_metrics
        }

        logger.info(f"Owl detection completed - Owl Present: {is_owl_present}, "
                   f"Candidates: {len(owl_candidates)}, "
                   f"Total Shapes: {len(contour_data)}")

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
            },
            "threshold_percentage": 0.05,
            "luminance_threshold": 40,
            "interval_seconds": 3
        }

        # Test with is_test=True
        result, info = detect_owl_in_box(
            test_new,
            test_base,
            test_config,
            is_test=True
        )

        print(f"Test detection result: {result}")
        print(f"Detection info: {info}")

    except Exception as e:
        logger.error(f"Owl detection test failed: {e}")
        raise