# File: utilities/image_comparison_utils.py
# Purpose: Generate and handle three-panel comparison images with clear owl detection results

import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import logging
from utilities.logging_utils import get_logger
from utilities.constants import IMAGE_COMPARISONS_DIR

# Initialize logger
logger = get_logger()

def analyze_shape(contour, total_area, config):
    """
    Analyze if a contour matches owl shape characteristics.
    
    Args:
        contour: OpenCV contour
        total_area: Total image area
        config: Camera configuration with motion parameters
        
    Returns:
        tuple: (is_owl_shape, metrics_dict)
    """
    try:
        # Get motion detection parameters
        motion_config = config.get("motion_detection", {})
        min_circularity = motion_config.get("min_circularity", 0.5)
        min_aspect_ratio = motion_config.get("min_aspect_ratio", 0.5)
        max_aspect_ratio = motion_config.get("max_aspect_ratio", 2.0)
        min_area_ratio = motion_config.get("min_area_ratio", 0.2)

        # Calculate shape metrics
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        x, y, w, h = cv2.boundingRect(contour)
        
        # Calculate shape characteristics
        circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
        aspect_ratio = float(w) / h if h > 0 else 0
        area_ratio = area / total_area
        
        metrics = {
            "area": area,
            "circularity": circularity,
            "aspect_ratio": aspect_ratio,
            "area_ratio": area_ratio,
            "bounds": (x, y, w, h)
        }
        
        # Check if matches owl characteristics
        is_owl_shape = (
            circularity > min_circularity and
            min_aspect_ratio < aspect_ratio < max_aspect_ratio and
            area_ratio > min_area_ratio
        )
        
        return is_owl_shape, metrics
        
    except Exception as e:
        logger.error(f"Error analyzing shape: {e}")
        return False, {}

def create_difference_image(base_image, new_image, threshold, config):
    """
    Create a difference visualization highlighting only detected owl shapes.
    
    Args:
        base_image (PIL.Image): Base reference image
        new_image (PIL.Image): New captured image
        threshold (int): Luminance threshold for change detection
        config (dict): Camera configuration with motion detection parameters
    
    Returns:
        tuple: (PIL.Image, bool, dict) - Result image, owl detected flag, and metrics
    """
    try:
        # Convert PIL images to OpenCV format
        base_cv = cv2.cvtColor(np.array(base_image), cv2.COLOR_RGB2GRAY)
        new_cv = cv2.cvtColor(np.array(new_image), cv2.COLOR_RGB2GRAY)
        
        # Calculate absolute difference
        diff = cv2.absdiff(new_cv, base_cv)
        
        # Apply Gaussian blur to reduce noise
        blurred_diff = cv2.GaussianBlur(diff, (5, 5), 0)
        
        # Create binary mask of changes
        _, binary_mask = cv2.threshold(blurred_diff, threshold, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Create visualization image
        result_image = new_image.copy()
        result_cv = cv2.cvtColor(np.array(result_image), cv2.COLOR_RGB2BGR)
        
        # Initialize metrics
        total_area = base_cv.shape[0] * base_cv.shape[1]
        owl_detected = False
        detection_metrics = {
            "total_contours": len(contours),
            "owl_like_contours": 0,
            "largest_area_ratio": 0,
            "avg_luminance_change": np.mean(diff),
        }
        
        # Analyze each contour
        for contour in contours:
            is_owl, metrics = analyze_shape(contour, total_area, config)
            
            if is_owl:
                owl_detected = True
                detection_metrics["owl_like_contours"] += 1
                detection_metrics["largest_area_ratio"] = max(
                    detection_metrics["largest_area_ratio"],
                    metrics["area_ratio"]
                )
                
                # Draw owl contour and bounding box
                x, y, w, h = metrics["bounds"]
                cv2.rectangle(result_cv, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.drawContours(result_cv, [contour], -1, (0, 0, 255), 2)
        
        # Convert back to PIL
        result_pil = Image.fromarray(cv2.cvtColor(result_cv, cv2.COLOR_BGR2RGB))
        
        return result_pil, owl_detected, detection_metrics
        
    except Exception as e:
        logger.error(f"Error creating difference image: {e}")
        raise

def add_status_overlay(image, owl_detected, metrics, threshold):
    """
    Add status and metrics overlay to difference image.
    
    Args:
        image (PIL.Image): Image to add overlay to
        owl_detected (bool): Whether an owl was detected
        metrics (dict): Detection metrics
        threshold (int): Threshold value used
        
    Returns:
        PIL.Image: Image with overlay added
    """
    try:
        # Create copy to avoid modifying original
        img_with_text = image.copy()
        draw = ImageDraw.Draw(img_with_text)
        
        # Draw main status at top
        status_text = "OWL DETECTED" if owl_detected else "NO OWL DETECTED"
        status_color = "red" if owl_detected else "green"
        
        # Position text
        x = 10
        y = 10
        
        # Draw status with larger text
        draw.text((x, y), status_text, fill=status_color)
        y += 30
        
        # Add metrics if owl detected
        if owl_detected:
            metrics_text = [
                f"Owl-like Shapes: {metrics['owl_like_contours']}",
                f"Largest Area: {metrics['largest_area_ratio']*100:.1f}%",
                f"Avg Luminance Change: {metrics['avg_luminance_change']:.1f}",
                f"Threshold: {threshold}"
            ]
        else:
            metrics_text = [
                f"Total Contours: {metrics['total_contours']}",
                f"Avg Luminance Change: {metrics['avg_luminance_change']:.1f}",
                f"Threshold: {threshold}"
            ]
        
        # Draw metrics in yellow
        for text in metrics_text:
            draw.text((x, y), text, fill='yellow')
            y += 20
            
        return img_with_text
        
    except Exception as e:
        logger.error(f"Error adding status overlay: {e}")
        raise

def create_comparison_image(base_image, new_image, camera_name, threshold, config):
    """
    Create a three-panel comparison image with clear owl detection status.
    
    Args:
        base_image (PIL.Image): Base reference image
        new_image (PIL.Image): New captured image
        camera_name (str): Name of the camera
        threshold (int): Luminance threshold for change detection
        config (dict): Camera configuration
        
    Returns:
        str: Path to saved comparison image
    """
    try:
        # Get image dimensions
        width, height = base_image.size
        
        # Create new image with space for three panels
        comparison = Image.new('RGB', (width * 3, height))
        
        # Process difference image and get detection results
        diff_image, owl_detected, metrics = create_difference_image(
            base_image, new_image, threshold, config
        )
        
        # Add status overlay
        diff_with_overlay = add_status_overlay(
            diff_image, owl_detected, metrics, threshold
        )
        
        # Combine images
        comparison.paste(base_image, (0, 0))  # Left panel
        comparison.paste(new_image, (width, 0))  # Middle panel
        comparison.paste(diff_with_overlay, (width * 2, 0))  # Right panel
        
        # Save comparison image
        os.makedirs(IMAGE_COMPARISONS_DIR, exist_ok=True)
        comparison_path = os.path.join(
            IMAGE_COMPARISONS_DIR,
            f"{camera_name.lower().replace(' ', '_')}_comparison.jpg"
        )
        comparison.save(comparison_path, quality=95)
        
        logger.info(
            f"Created comparison image for {camera_name}. "
            f"Owl detected: {owl_detected}"
        )
        return comparison_path
        
    except Exception as e:
        logger.error(f"Error creating comparison image: {e}")
        raise

if __name__ == "__main__":
    # Test the comparison functionality
    try:
        import pyautogui
        
        # Capture test images
        test_roi = (0, 0, 640, 480)  # Example ROI
        base = pyautogui.screenshot(region=test_roi)
        new = pyautogui.screenshot(region=test_roi)
        
        # Test config
        test_config = {
            "motion_detection": {
                "min_circularity": 0.5,
                "min_aspect_ratio": 0.5,
                "max_aspect_ratio": 2.0,
                "min_area_ratio": 0.2
            }
        }
        
        # Create test comparison
        comparison_path = create_comparison_image(
            base, new, "Test Camera", threshold=30, config=test_config
        )
        
        print(f"Test comparison created: {comparison_path}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise