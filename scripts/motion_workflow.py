# File: motion_workflow.py
# Purpose: Handle motion detection with adaptive lighting conditions

import os
import time
from datetime import datetime
from PIL import Image
import pyautogui
import pytz
import numpy as np

# Import utilities
from utilities.constants import (
    BASE_IMAGES_DIR,
    TEMP_BASE_IMAGES_DIR,
    get_comparison_image_path,
    CAMERA_MAPPINGS,
    get_archive_comparison_path
)
from utilities.logging_utils import get_logger
from utilities.time_utils import (
    get_current_lighting_condition,
    should_capture_base_image,
    get_luminance_threshold_multiplier
)
from utilities.owl_detection_utils import detect_owl_in_box
from utilities.image_comparison_utils import create_comparison_image
from utilities.alert_manager import AlertManager
from capture_base_images import capture_base_images, get_latest_base_image
# Import from push_to_supabase instead of database_utils
from push_to_supabase import push_log_to_supabase  

# Initialize logger and alert manager
logger = get_logger()
alert_manager = AlertManager()

# Set timezone
PACIFIC_TIME = pytz.timezone("America/Los_Angeles")

def initialize_system(camera_configs, is_test=False):
    """Initialize the motion detection system."""
    try:
        logger.info(f"Initializing motion detection system (Test Mode: {is_test})")
        
        # Verify camera configurations
        if not camera_configs:
            logger.error("No camera configurations provided")
            return False
            
        # Check for required ROIs
        for camera_name, config in camera_configs.items():
            if "roi" not in config or not config["roi"]:
                logger.error(f"Missing ROI configuration for {camera_name}")
                return False
                
        # Verify base images directory based on local saving setting
        local_saving = os.getenv('OWL_LOCAL_SAVING', 'True').lower() == 'true'
        logger.info(f"Local image saving is {'enabled' if local_saving else 'disabled'}")
        
        if not is_test:
            check_dir = BASE_IMAGES_DIR if local_saving else TEMP_BASE_IMAGES_DIR
            if not os.path.exists(check_dir):
                os.makedirs(check_dir, exist_ok=True)
                logger.info(f"Created base images directory: {check_dir}")
            
        logger.info("Motion detection system initialization complete")
        return True
        
    except Exception as e:
        logger.error(f"Error during motion detection system initialization: {e}")
        return False

def capture_real_image(roi):
    """Capture a screenshot of the specified region"""
    try:
        x, y, width, height = roi
        region = (x, y, width - x, height - y)
        logger.debug(f"Capturing screenshot with ROI: {region}")
        screenshot = pyautogui.screenshot(region=region)
        return screenshot.convert("RGB")
    except Exception as e:
        logger.error(f"Error capturing screenshot: {e}")
        raise

def format_detection_metrics(detection_info, config, camera_type):
    """Format detection metrics for database logging"""
    metrics = {
        "detected": False,
        "pixel_change": 0.0,
        "luminance_change": 0.0,
        "threshold_percentage": config.get("threshold_percentage", 0.0),
        "threshold_luminance": config.get("luminance_threshold", 0.0),
        "interval_seconds": config.get("interval_seconds", 0),
        "shapes_count": 0,
        "largest_shape_circularity": 0.0,
        "largest_shape_aspect_ratio": 0.0,
        "largest_shape_area_ratio": 0.0,
        "largest_shape_brightness_diff": 0.0,
        "image_url": "",
        "comparison_url": ""
    }

    if not detection_info:
        return metrics

    # Update with actual detection info
    if camera_type == "Owl In Box":
        metrics.update({
            "detected": detection_info.get("is_owl_present", False),
            "shapes_count": len(detection_info.get("owl_candidates",)),
            "pixel_change": detection_info.get("diff_metrics", {}).get("significant_pixels", 0.0) * 100,
            "luminance_change": detection_info.get("diff_metrics", {}).get("mean_difference", 0.0)
        })
        
        # Get largest shape metrics if any were detected
        if detection_info.get("owl_candidates"):
            largest = max(detection_info["owl_candidates"], 
                        key=lambda x: x.get("area_ratio", 0))
            metrics.update({
                "largest_shape_circularity": largest.get("circularity", 0.0),
                "largest_shape_aspect_ratio": largest.get("aspect_ratio", 0.0),
                "largest_shape_area_ratio": largest.get("area_ratio", 0.0),
                "largest_shape_brightness_diff": largest.get("brightness_diff", 0.0)
            })
    else:
        metrics.update({
            "detected": detection_info.get("motion_detected", False),
            "pixel_change": detection_info.get("pixel_change", 0.0),
            "luminance_change": detection_info.get("luminance_change", 0.0)
        })

    # Add image URLs if available
    if detection_info.get("snapshot_path"):
        metrics["image_url"] = detection_info["snapshot_path"]
    if detection_info.get("comparison_path"):
        metrics["comparison_url"] = detection_info["comparison_path"]

    return metrics

def process_camera(camera_name, config, lighting_info=None, test_images=None):
    """Process motion detection for a specific camera"""
    try:
        logger.info(f"Processing camera: {camera_name} {'(Test Mode)' if test_images else ''}")
        
        # Get or use provided lighting condition
        if lighting_info is None:
            lighting_condition = get_current_lighting_condition()
            threshold_multiplier = get_luminance_threshold_multiplier()
        else:
            lighting_condition = lighting_info['condition']
            threshold_multiplier = lighting_info['threshold_multiplier']
            
        logger.info(f"Current lighting condition: {lighting_condition}")
        
        # Get base image age
        base_image_age = 0
        try:
            base_timestamp = os.path.getctime(get_latest_base_image(camera_name, lighting_condition))
            base_image_age = int(time.time() - base_timestamp)
        except Exception as e:
            logger.warning(f"Could not determine base image age: {e}")
        
        # Get images either from test or capture
        if test_images:
            base_image = test_images['base']
            new_image = test_images['test']
            is_test = True
        else:
            base_image = get_latest_base_image(camera_name, lighting_condition)
            new_image = capture_real_image(config["roi"])
            is_test = False

        # Initialize detection results
        detection_results = {
            "Owl In Box": {},
            "Owl On Box": {},
            "Owl In Area": {}
        }
        
        # Get camera type
        alert_type = CAMERA_MAPPINGS[camera_name]
        
        # Process based on camera type
        detection_info = None
        if alert_type == "Owl In Box":
            is_owl_present, detection_info = detect_owl_in_box(
                new_image, 
                base_image,
                config,
                is_test=is_test
            )
            if is_owl_present:
                comparison_path = create_comparison_image(
                    base_image, 
                    new_image,
                    camera_name=alert_type,
                    threshold=config["luminance_threshold"] * threshold_multiplier,
                    config=config,
                    is_test=is_test
                )
                detection_info["comparison_path"] = comparison_path
        else:
            comparison_path = create_comparison_image(
                base_image, 
                new_image,
                camera_name=alert_type,
                threshold=config["luminance_threshold"] * threshold_multiplier,
                config=config,
                is_test=is_test
            )
            
            if comparison_path:
                detection_info = {
                    "motion_detected": True,
                    "comparison_path": comparison_path
                }

        # Format metrics for database
        metrics = format_detection_metrics(detection_info, config, alert_type)
        detection_results[alert_type] = metrics

        # Push to activity log
        log_entry = push_log_to_supabase(
            detection_results,
            lighting_condition,
            base_image_age
        )

        if log_entry and metrics["detected"] and not is_test:
            # Process alert if motion was detected
            alert_manager.process_detection(
                camera_name,
                {
                    "status": alert_type,
                    "pixel_change": metrics["pixel_change"],
                    "luminance_change": metrics["luminance_change"]
                },
                log_entry["id"]
            )

        return detection_results[alert_type]

    except Exception as e:
        logger.error(f"Error processing {camera_name}: {e}")
        return {
            "status": "Error",
            "error_message": str(e)
        }

def process_cameras(camera_configs, test_images=None):
    """Process all cameras in batch for efficient motion detection"""
    try:
        # Get lighting information once for all cameras
        lighting_condition = get_current_lighting_condition()
        threshold_multiplier = get_luminance_threshold_multiplier()
        
        lighting_info = {
            'condition': lighting_condition,
            'threshold_multiplier': threshold_multiplier
        }
        
        logger.info(f"Processing cameras under {lighting_condition} condition")
        
        # Only verify base images in real-time mode
        if not test_images:
            if should_capture_base_image():
                logger.info("Time to capture new base images")
                capture_base_images(lighting_condition, force_capture=True)
                time.sleep(3)  # Allow system to stabilize after capture
        
        # Process each camera with shared lighting info
        results =  []# Initialize results list here
        for camera_name, config in camera_configs.items():
            try:
                camera_test_images = test_images.get(camera_name) if test_images else None
                result = process_camera(
                    camera_name, 
                    config, 
                    lighting_info,
                    test_images=camera_test_images
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing camera {camera_name}: {e}")
                results.append({
                    "camera": camera_name,
                    "status": "Error",
                    "error_message": str(e)
                })
        
        return results

    except Exception as e:
        logger.error(f"Error in camera processing cycle: {e}")
        raise

if __name__ == "__main__":
    # Test the motion detection
    try:
        from utilities.configs_loader import load_camera_config
        
        # Load test configuration
        test_configs = load_camera_config()
        
        # Initialize system
        if initialize_system(test_configs, is_test=True):
            # Run test detection cycle
            results = process_cameras(test_configs)
            print("Test Results:", results)
    except Exception as e:
        logger.error(f"Motion detection test failed: {e}")
        raise