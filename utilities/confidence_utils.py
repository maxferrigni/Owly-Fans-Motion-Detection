# File: utilities/confidence_utils.py
# Purpose: Calculate and manage owl confidence scores for improved detection

import numpy as np
from datetime import datetime
import pytz
from utilities.logging_utils import get_logger

# Initialize logger
logger = get_logger()

# Initialize frame history tracking (will be imported and used by other modules)
FRAME_HISTORY = {
    "Wyze Internal Camera": [],
    "Bindy Patio Camera": [],
    "Upper Patio Camera": []
}

# Maximum frames to store in history
MAX_FRAME_HISTORY = 10

def calculate_shape_confidence(detection_data, config):
    """
    Calculate confidence score based on shape characteristics.
    
    Args:
        detection_data (dict): Detection data including owl candidates
        config (dict): Camera configuration
        
    Returns:
        float: Shape confidence score (0-40%)
    """
    shape_score = 0
    
    if not detection_data.get("owl_candidates"):
        return 0
        
    # Get best candidate
    best_candidate = max(detection_data["owl_candidates"], key=lambda x: x["area_ratio"])
    
    # Circularity score (0-10%)
    min_circ = config["motion_detection"]["min_circularity"]
    ideal_circ = 0.8  # Ideal owl circularity
    circ_score = min(10, (best_candidate["circularity"] / ideal_circ) * 10)
    
    # Aspect ratio score (0-10%)
    min_aspect = config["motion_detection"]["min_aspect_ratio"]
    max_aspect = config["motion_detection"]["max_aspect_ratio"]
    ideal_aspect = 1.2  # Ideal owl aspect ratio
    aspect_deviation = abs(best_candidate["aspect_ratio"] - ideal_aspect) / (max_aspect - min_aspect)
    aspect_score = 10 * (1 - min(1, aspect_deviation))
    
    # Size score (0-20%)
    min_area = config["motion_detection"]["min_area_ratio"]
    ideal_area = 0.2  # Ideal owl size relative to frame
    area_score = min(20, (best_candidate["area_ratio"] / ideal_area) * 20)
    
    shape_score = circ_score + aspect_score + area_score
    
    logger.debug(f"Shape confidence breakdown - Circularity: {circ_score:.1f}%, Aspect Ratio: {aspect_score:.1f}%, Size: {area_score:.1f}%")
    
    return shape_score

def calculate_motion_confidence(detection_data, config):
    """
    Calculate confidence score based on motion characteristics.
    
    Args:
        detection_data (dict): Detection data including motion metrics
        config (dict): Camera configuration
        
    Returns:
        float: Motion confidence score (0-30%)
    """
    # Pixel change (0-15%)
    pixel_change = detection_data.get("pixel_change", 0) / 100  # Convert from percentage
    ideal_change = 0.3  # 30% is ideal for owl movement
    pixel_score = min(15, (pixel_change / ideal_change) * 15)
    
    # Luminance difference (0-15%)
    luminance = detection_data.get("luminance_change", 0)
    ideal_luminance = 50  # Ideal luminance difference for owl
    luminance_score = min(15, (luminance / ideal_luminance) * 15)
    
    motion_score = pixel_score + luminance_score
    
    logger.debug(f"Motion confidence breakdown - Pixel Change: {pixel_score:.1f}%, Luminance: {luminance_score:.1f}%")
    
    return motion_score

def calculate_temporal_confidence(camera_name, current_confidence):
    """
    Calculate confidence score based on temporal persistence.
    
    Args:
        camera_name (str): Name of the camera
        current_confidence (float): Current primary confidence score
        
    Returns:
        float: Temporal confidence score (0-20%)
        int: Number of consecutive frames with significant confidence
    """
    max_frames = 5  # Maximum frames to consider
    confidence_threshold = 30  # Minimum confidence to consider
    
    # Get frame history for this camera
    history = FRAME_HISTORY.get(camera_name, [])
    
    if not history:
        return 0, 0
    
    # Count consecutive frames with significant confidence
    consecutive_frames = 0
    
    # Include current frame in count if it meets threshold
    if current_confidence >= confidence_threshold:
        consecutive_frames = 1
    
    # Check previous frames
    for frame in reversed(history):
        if frame["primary_confidence"] >= confidence_threshold:
            consecutive_frames += 1
        else:
            break
    
    # Calculate persistence score (up to 20%)
    persistence_factor = min(consecutive_frames / max_frames, 1.0)
    persistence_score = 20 * persistence_factor
    
    logger.debug(f"Temporal confidence: {persistence_score:.1f}% from {consecutive_frames} consecutive frames")
    
    return persistence_score, consecutive_frames

def calculate_camera_specific_confidence(detection_data, camera_name, config):
    """
    Calculate camera-specific confidence factors.
    
    Args:
        detection_data (dict): Detection data
        camera_name (str): Name of the camera
        config (dict): Camera configuration
        
    Returns:
        float: Camera-specific confidence score (0-10%)
    """
    camera_score = 0
    
    if camera_name == "Wyze Internal Camera":  # In-box camera
        # Position analysis - owls tend to be in certain positions in box
        region_metrics = detection_data.get("diff_metrics", {}).get("region_metrics", {})
        
        if region_metrics:
            # Owls often appear in middle or bottom regions of box
            middle = region_metrics.get("middle", {}).get("mean_luminance", 0)
            top = region_metrics.get("top", {}).get("mean_luminance", 0)
            bottom = region_metrics.get("bottom", {}).get("mean_luminance", 0)
            
            if middle > top:
                camera_score += 5
            
            if bottom > top:
                camera_score += 5
                
    elif camera_name == "Bindy Patio Camera":  # On-box camera
        # More weight given to middle region where entry hole is
        region_metrics = detection_data.get("diff_metrics", {}).get("region_metrics", {})
        
        if region_metrics:
            middle = region_metrics.get("middle", {}).get("mean_luminance", 0)
            top = region_metrics.get("top", {}).get("mean_luminance", 0)
            bottom = region_metrics.get("bottom", {}).get("mean_luminance", 0)
            
            if middle > top and middle > bottom:
                camera_score += 10
        
    elif camera_name == "Upper Patio Camera":  # Area camera
        # For area camera, larger shapes get higher confidence
        # since the camera is further away
        if detection_data.get("owl_candidates"):
            best_candidate = max(detection_data["owl_candidates"], key=lambda x: x["area_ratio"])
            if best_candidate["area_ratio"] > 0.05:
                camera_score += 10
            elif best_candidate["area_ratio"] > 0.01:
                camera_score += 5
    
    logger.debug(f"Camera-specific confidence for {camera_name}: {camera_score}%")
    
    return camera_score

def calculate_owl_confidence(detection_data, camera_name, config):
    """
    Calculate the overall owl confidence score.
    
    Args:
        detection_data (dict): Detection data with all metrics
        camera_name (str): Name of the camera
        config (dict): Camera configuration
        
    Returns:
        dict: Confidence results including score and factors
    """
    try:
        # Calculate primary confidence components
        shape_confidence = calculate_shape_confidence(detection_data, config)
        motion_confidence = calculate_motion_confidence(detection_data, config)
        
        # Primary confidence (shape + motion)
        primary_confidence = shape_confidence + motion_confidence
        
        # Calculate temporal confidence based on history
        temporal_confidence, consecutive_frames = calculate_temporal_confidence(
            camera_name, 
            primary_confidence
        )
        
        # Calculate camera-specific confidence
        camera_confidence = calculate_camera_specific_confidence(
            detection_data, 
            camera_name, 
            config
        )
        
        # Final confidence score (0-100%)
        total_confidence = primary_confidence + temporal_confidence + camera_confidence
        
        # Update frame history
        update_frame_history(
            camera_name, 
            primary_confidence, 
            total_confidence
        )
        
        # Prepare confidence results
        confidence_results = {
            "owl_confidence": total_confidence,
            "consecutive_owl_frames": consecutive_frames,
            "confidence_factors": {
                "shape_confidence": shape_confidence,
                "motion_confidence": motion_confidence,
                "temporal_confidence": temporal_confidence,
                "camera_confidence": camera_confidence
            }
        }
        
        logger.info(
            f"Owl confidence for {camera_name}: {total_confidence:.1f}% "
            f"(Shape: {shape_confidence:.1f}%, Motion: {motion_confidence:.1f}%, "
            f"Temporal: {temporal_confidence:.1f}%, Camera: {camera_confidence:.1f}%)"
        )
        
        return confidence_results
        
    except Exception as e:
        logger.error(f"Error calculating owl confidence: {e}")
        return {
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

def update_frame_history(camera_name, primary_confidence, total_confidence):
    """
    Update the frame history for a camera.
    
    Args:
        camera_name (str): Name of the camera
        primary_confidence (float): Primary confidence score
        total_confidence (float): Total confidence score
    """
    # Get existing history
    history = FRAME_HISTORY.get(camera_name, [])
    
    # Add new frame data
    history.append({
        "timestamp": datetime.now(pytz.timezone('America/Los_Angeles')),
        "primary_confidence": primary_confidence,
        "total_confidence": total_confidence
    })
    
    # Trim history to keep only last N frames
    if len(history) > MAX_FRAME_HISTORY:
        history = history[-MAX_FRAME_HISTORY:]
    
    # Update history
    FRAME_HISTORY[camera_name] = history

def is_owl_detected(confidence_score, camera_name, config):
    """
    Determine if an owl is detected based on confidence score and thresholds.
    
    Args:
        confidence_score (float): Calculated owl confidence score
        camera_name (str): Name of the camera
        config (dict): Camera configuration
        
    Returns:
        bool: True if owl is detected, False otherwise
    """
    # Get confidence threshold from config or use default
    confidence_threshold = config.get("owl_confidence_threshold", 60)
    
    return confidence_score >= confidence_threshold

def reset_frame_history():
    """Reset all frame history (typically called on system restart)."""
    global FRAME_HISTORY
    FRAME_HISTORY = {
        "Wyze Internal Camera": [],
        "Bindy Patio Camera": [],
        "Upper Patio Camera": []
    }
    logger.info("Frame history reset")

# For testing
if __name__ == "__main__":
    # Test the confidence calculation
    test_detection_data = {
        "owl_candidates": [
            {
                "area_ratio": 0.15,
                "circularity": 0.75,
                "aspect_ratio": 1.3,
                "brightness_diff": 45
            }
        ],
        "pixel_change": 25.0,
        "luminance_change": 30.0,
        "diff_metrics": {
            "region_metrics": {
                "top": {"mean_luminance": 10.0},
                "middle": {"mean_luminance": 30.0},
                "bottom": {"mean_luminance": 20.0}
            }
        }
    }
    
    test_config = {
        "motion_detection": {
            "min_circularity": 0.5,
            "min_aspect_ratio": 0.5,
            "max_aspect_ratio": 2.0,
            "min_area_ratio": 0.1,
            "brightness_threshold": 20
        },
        "owl_confidence_threshold": 60
    }
    
    test_camera = "Wyze Internal Camera"
    
    # Add some test history
    FRAME_HISTORY[test_camera] = [
        {
            "timestamp": datetime.now(pytz.timezone('America/Los_Angeles')),
            "primary_confidence": 45.0,
            "total_confidence": 55.0
        }
    ]
    
    # Calculate confidence
    results = calculate_owl_confidence(
        test_detection_data,
        test_camera,
        test_config
    )
    
    print(f"Test results: {results}")
    print(f"Is owl detected: {is_owl_detected(results['owl_confidence'], test_camera, test_config)}")