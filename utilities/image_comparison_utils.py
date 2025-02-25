# File: utilities/image_comparison_utils.py
# Purpose: Generate and handle three-panel comparison images with enhanced metrics

import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import logging
from datetime import datetime
import pytz
from utilities.logging_utils import get_logger
from utilities.constants import IMAGE_COMPARISONS_DIR, CAMERA_MAPPINGS, get_comparison_image_path, get_saved_image_path, COMPARISON_IMAGE_FILENAMES

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

def create_difference_visualization(base_image, new_image, threshold, config):
    """Create enhanced difference visualization."""
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
        
        # Draw contours with different colors based on size
        for i, contour in enumerate(contours):
            color = (0, 0, 255) if i == 0 else (0, 255, 0)
            cv2.drawContours(diff_color, [contour], -1, color, 2)
            
            # Add bounding box and metrics for largest contour
            if i == 0:
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(diff_color, (x, y), (x + w, y + h), (255, 0, 0), 2)
                
                # Calculate metrics for annotation
                area = cv2.contourArea(contour)
                area_ratio = area / (height * width)
                cv2.putText(
                    diff_color,
                    f"Area: {area_ratio:.2%}",
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1
                )
        
        return Image.fromarray(diff_color), binary_mask
        
    except Exception as e:
        logger.error(f"Error creating difference visualization: {e}")
        raise

def add_status_overlay(image, metrics, threshold, is_test=False):
    """Add enhanced status and metrics overlay."""
    try:
        # Create copy to avoid modifying original
        img_with_text = image.copy()
        draw = ImageDraw.Draw(img_with_text)
        
        # Determine detection status
        significant_motion = metrics['pixel_change_ratio'] > 0.05  # 5% threshold
        status_text = "MOTION DETECTED" if significant_motion else "NO SIGNIFICANT MOTION"
        if is_test:
            status_text = f"TEST MODE - {status_text}"
        
        # Position text
        x, y = 10, 10
        line_height = 20
        
        # Draw status
        draw.text((x, y), status_text, fill="red" if significant_motion else "green")
        y += line_height * 2
        
        # Draw detailed metrics
        metrics_text = [
            f"Pixel Change: {metrics['pixel_change_ratio']*100:.1f}%",
            f"Mean Luminance: {metrics['mean_luminance']:.1f}",
            f"Max Luminance: {metrics['max_luminance']:.1f}",
            f"Threshold: {metrics['threshold_used']}",
            "",
            "Region Analysis:",
            f"Top: {metrics['region_metrics']['top']['mean_luminance']:.1f}",
            f"Middle: {metrics['region_metrics']['middle']['mean_luminance']:.1f}",
            f"Bottom: {metrics['region_metrics']['bottom']['mean_luminance']:.1f}"
        ]
        
        for text in metrics_text:
            draw.text((x, y), text, fill="yellow")
            y += line_height
            
        return img_with_text
        
    except Exception as e:
        logger.error(f"Error adding status overlay: {e}")
        raise

def create_comparison_image(base_image, new_image, camera_name, threshold, config, is_test=False, timestamp=None):
    """Create enhanced three-panel comparison image."""
    try:
        # Validate images
        is_valid, message = validate_comparison_images(base_image, new_image)
        if not is_valid:
            raise ValueError(message)
        
        # Get image dimensions
        width, height = base_image.size
        
        # Create visualization
        diff_image, binary_mask = create_difference_visualization(
            base_image,
            new_image,
            threshold,
            config
        )
        
        # Analyze metrics
        change_metrics = analyze_change_metrics(diff_image, threshold, config)
        motion_chars = analyze_motion_characteristics(binary_mask, config)
        
        # Add metrics to change_metrics
        change_metrics.update({
            'motion_characteristics': motion_chars,
            'camera_name': camera_name,
            'is_test': is_test
        })
        
        # Add overlay
        diff_with_overlay = add_status_overlay(
            diff_image,
            change_metrics,
            threshold,
            is_test=is_test
        )
        
        # Create comparison image
        comparison = Image.new('RGB', (width * 3, height))
        comparison.paste(base_image, (0, 0))
        comparison.paste(new_image, (width, 0))
        comparison.paste(diff_with_overlay, (width * 2, 0))
        
        # Get the alert type for this camera
        alert_type = CAMERA_MAPPINGS.get(camera_name)
        if not alert_type:
            alert_type = "Unknown"
        
        # Ensure timestamp is set
        if not timestamp:
            timestamp = datetime.now(pytz.timezone('America/Los_Angeles'))
            
        # Get the fixed path for this type of comparison
        comparison_path = get_comparison_image_path(camera_name)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(comparison_path), exist_ok=True)
        
        # Save the comparison image to the fixed location
        comparison.save(comparison_path, quality=95)
        
        # Check if motion was detected and local saving is enabled
        motion_detected = change_metrics['pixel_change_ratio'] > 0.05
        local_saving = os.getenv('OWL_LOCAL_SAVING', 'False').lower() == 'true'
        
        # If motion detected and local saving enabled, save a copy to logs
        if motion_detected and local_saving:
            saved_path = get_saved_image_path(camera_name, "comparison", timestamp)
            comparison.save(saved_path, quality=95)
            logger.info(f"Motion detected - saved copy to logs: {saved_path}")
        
        logger.info(
            f"Created comparison image for {camera_name}. "
            f"Motion detected: {motion_detected} "
            f"{'(Test Mode)' if is_test else ''}"
        )
        
        # Return the fixed path - this is what the rest of the code expects
        return comparison_path
        
    except Exception as e:
        logger.error(f"Error creating comparison image: {e}")
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
        
        # Capture test images
        test_roi = (0, 0, 640, 480)
        base = pyautogui.screenshot(region=test_roi)
        new = pyautogui.screenshot(region=test_roi)
        
        # Test comparison
        comparison_path = create_comparison_image(
            base,
            new,
            "Test Camera",
            threshold=30,
            config=test_config,
            is_test=True
        )
        
        print(f"Test comparison created: {comparison_path}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise