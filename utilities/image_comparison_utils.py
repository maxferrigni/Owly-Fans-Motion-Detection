# File: utilities/image_comparison_utils.py
# Purpose: Generate and handle three-panel comparison images for motion detection

import os
from PIL import Image, ImageDraw, ImageFont, ImageChops
import numpy as np
from utilities.logging_utils import get_logger
from utilities.constants import IMAGE_COMPARISONS_DIR

# Initialize logger
logger = get_logger()

def create_difference_image(base_image, new_image, threshold):
    """
    Create a difference visualization image with changed pixels highlighted in red.
    
    Args:
        base_image (PIL.Image): Base reference image
        new_image (PIL.Image): New captured image
        threshold (int): Luminance threshold for change detection
    
    Returns:
        tuple: (PIL.Image, float, float) - Difference image, pixel change percentage, avg luminance change
    """
    try:
        # Ensure images are in RGB mode
        base_rgb = base_image.convert('RGB')
        new_rgb = new_image.convert('RGB')
        
        # Create difference image
        diff = ImageChops.difference(base_rgb, new_rgb)
        diff_gray = diff.convert('L')
        
        # Calculate metrics
        total_pixels = diff_gray.size[0] * diff_gray.size[1]
        pixels_array = np.array(diff_gray)
        changed_pixels = np.sum(pixels_array > threshold)
        pixel_change_pct = (changed_pixels / total_pixels) * 100
        avg_luminance_change = np.mean(pixels_array)
        
        # Create visualization
        diff_highlight = new_rgb.copy()
        draw = ImageDraw.Draw(diff_highlight)
        
        # Highlight changed pixels in red
        width, height = diff_gray.size
        for x in range(width):
            for y in range(height):
                if diff_gray.getpixel((x, y)) > threshold:
                    draw.point((x, y), fill='red')
        
        return diff_highlight, pixel_change_pct, avg_luminance_change
        
    except Exception as e:
        logger.error(f"Error creating difference image: {e}")
        raise

def add_metrics_overlay(image, pixel_change, luminance_change, threshold):
    """
    Add metrics text overlay to an image.
    
    Args:
        image (PIL.Image): Image to add overlay to
        pixel_change (float): Percentage of pixels changed
        luminance_change (float): Average luminance change
        threshold (int): Threshold value used
        
    Returns:
        PIL.Image: Image with overlay added
    """
    try:
        # Create copy to avoid modifying original
        img_with_text = image.copy()
        draw = ImageDraw.Draw(img_with_text)
        
        # Prepare text
        metrics_text = [
            f"Pixel Changes: {pixel_change:.2f}%",
            f"Avg Luminance Change: {luminance_change:.2f}",
            f"Threshold: {threshold} pixels, Luminance > {threshold}"
        ]
        
        # Position text in top-right corner with yellow color
        x = 10
        y = 10
        for text in metrics_text:
            draw.text((x, y), text, fill='yellow')
            y += 20
            
        return img_with_text
        
    except Exception as e:
        logger.error(f"Error adding metrics overlay: {e}")
        raise

def create_comparison_image(base_image, new_image, camera_name, threshold):
    """
    Create a three-panel comparison image showing base image, new image, and differences.
    
    Args:
        base_image (PIL.Image): Base reference image
        new_image (PIL.Image): New captured image
        camera_name (str): Name of the camera
        threshold (int): Luminance threshold for change detection
        
    Returns:
        str: Path to saved comparison image
    """
    try:
        # Get image dimensions
        width, height = base_image.size
        
        # Create new image with space for three panels
        comparison = Image.new('RGB', (width * 3, height))
        
        # Process difference image and metrics
        diff_image, pixel_change, luminance_change = create_difference_image(
            base_image, new_image, threshold
        )
        
        # Add metrics overlay to difference image
        diff_with_metrics = add_metrics_overlay(
            diff_image, pixel_change, luminance_change, threshold
        )
        
        # Combine images
        comparison.paste(base_image, (0, 0))  # Left panel
        comparison.paste(new_image, (width, 0))  # Middle panel
        comparison.paste(diff_with_metrics, (width * 2, 0))  # Right panel
        
        # Save comparison image
        os.makedirs(IMAGE_COMPARISONS_DIR, exist_ok=True)
        comparison_path = os.path.join(
            IMAGE_COMPARISONS_DIR,
            f"{camera_name.lower().replace(' ', '_')}_comparison.jpg"
        )
        comparison.save(comparison_path, quality=95)
        
        logger.info(f"Created comparison image: {comparison_path}")
        return comparison_path
        
    except Exception as e:
        logger.error(f"Error creating comparison image: {e}")
        raise

def get_image_metrics(comparison_path):
    """
    Extract metrics from a saved comparison image.
    
    Args:
        comparison_path (str): Path to comparison image
        
    Returns:
        dict: Dictionary containing metrics
    """
    try:
        with Image.open(comparison_path) as img:
            # Get the right third of the image (diff panel)
            width = img.size[0] // 3
            diff_panel = img.crop((width * 2, 0, width * 3, img.size[1]))
            
            # Convert to grayscale for analysis
            diff_gray = diff_panel.convert('L')
            
            # Calculate metrics
            pixels_array = np.array(diff_gray)
            red_pixels = np.sum(pixels_array > 200)  # Threshold for red pixels
            total_pixels = pixels_array.size
            
            return {
                'pixel_change_pct': (red_pixels / total_pixels) * 100,
                'avg_luminance': np.mean(pixels_array)
            }
            
    except Exception as e:
        logger.error(f"Error getting image metrics: {e}")
        return None

if __name__ == "__main__":
    # Test the comparison functionality
    try:
        import pyautogui
        
        # Capture test images
        test_roi = (0, 0, 640, 480)  # Example ROI
        base = pyautogui.screenshot(region=test_roi)
        new = pyautogui.screenshot(region=test_roi)
        
        # Create test comparison
        comparison_path = create_comparison_image(
            base, new, "Test Camera", threshold=30
        )
        
        # Get and print metrics
        metrics = get_image_metrics(comparison_path)
        print(f"Test comparison metrics: {metrics}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise