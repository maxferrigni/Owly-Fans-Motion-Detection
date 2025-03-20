# File: utilities/confidence_utils.py
# Purpose: Calculate and manage owl confidence scores for improved detection without decision-making
# 
# Updates:
# - Adjusted motion confidence calculation to be less generous with small changes
# - Made shape confidence scoring more stringent
# - Improved temporal confidence to require higher quality detections
# - Enhanced camera-specific confidence factors for night conditions

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
    Modified to be more stringent with shape requirements.
    
    Args:
        detection_data (dict): Detection data including owl candidates
        config (dict): Camera configuration
        
    Returns:
        float: Shape confidence score (0-40%)
    """
    shape_score = 0
    
    if not detection_data.get("owl_candidates"):
        return 0
        
    # Get best candidate based on area ratio
    best_candidate = max(detection_data["owl_candidates"], key=lambda x: x["area_ratio"])
    
    # Circularity score (0-10%)
    min_circ = config["motion_detection"]["min_circularity"]
    ideal_circ = 0.8  # Ideal owl circularity
    circ_value = best_candidate.get("circularity", 0)
    
    if circ_value >= min_circ:
        # More stringent scoring curve - requires closer to ideal circularity
        # Use quadratic scaling to penalize values further from ideal
        circ_distance = abs(circ_value - ideal_circ)
        circ_score = min(10, 10 * (1 - (circ_distance * 2)))
        logger.debug(f"Circularity score: {circ_score:.1f}% (value: {circ_value:.2f})")
    else:
        circ_score = 0
        logger.debug(f"Circularity too low: {circ_value:.2f} < {min_circ}")
    
    # Aspect ratio score (0-10%)
    min_aspect = config["motion_detection"]["min_aspect_ratio"]
    max_aspect = config["motion_detection"]["max_aspect_ratio"]
    ideal_aspect = 1.2  # Ideal owl aspect ratio
    aspect_value = best_candidate.get("aspect_ratio", 0)
    
    if min_aspect <= aspect_value <= max_aspect:
        # More stringent scaling - use quadratic distance from ideal
        aspect_deviation = abs(aspect_value - ideal_aspect) / (max_aspect - min_aspect)
        aspect_score = 10 * (1 - min(1, aspect_deviation * 1.5))  # Multiply by 1.5 to make more stringent
        logger.debug(f"Aspect ratio score: {aspect_score:.1f}% (value: {aspect_value:.2f})")
    else:
        aspect_score = 0
        logger.debug(f"Aspect ratio outside range: {aspect_value:.2f} not in [{min_aspect}-{max_aspect}]")
    
    # Size score (0-20%)
    min_area = config["motion_detection"]["min_area_ratio"]
    ideal_area = 0.2  # Ideal owl size relative to frame
    area_value = best_candidate.get("area_ratio", 0)
    
    if area_value >= min_area:
        # More stringent size scoring
        # For very small shapes, reduce score significantly
        if area_value < min_area * 2:
            area_score = min(10, (area_value / ideal_area) * 10)
        else:
            area_score = min(20, (area_value / ideal_area) * 20)
        logger.debug(f"Area score: {area_score:.1f}% (value: {area_value:.2f})")
    else:
        area_score = 0
        logger.debug(f"Area too small: {area_value:.2f} < {min_area}")
    
    shape_score = circ_score + aspect_score + area_score
    logger.debug(f"Total shape score: {shape_score:.1f}%")
    
    return shape_score

def calculate_motion_confidence(detection_data, config):
    """
    Calculate confidence score based on motion characteristics.
    Modified to require more substantial motion for high scores.
    
    Args:
        detection_data (dict): Detection data including motion metrics
        config (dict): Camera configuration
        
    Returns:
        float: Motion confidence score (0-30%)
    """
    # Pixel change (0-15%)
    pixel_change = detection_data.get("pixel_change", 0) / 100  # Convert from percentage
    ideal_change = 0.3  # 30% is ideal for owl movement
    min_change = config.get("threshold_percentage", 0.05)
    
    if pixel_change >= min_change:
        # More stringent scoring curve - requires closer to ideal change
        # Apply quadratic scaling based on distance from minimum threshold
        scale_factor = min(1.0, (pixel_change - min_change) / (ideal_change - min_change))
        pixel_score = min(15, 15 * scale_factor * scale_factor)  # Square it for quadratic scaling
        logger.debug(f"Pixel change score: {pixel_score:.1f}% (value: {pixel_change:.2f})")
    else:
        pixel_score = 0
        logger.debug(f"Pixel change too low: {pixel_change:.2f} < {min_change}")
    
    # Luminance difference (0-15%)
    luminance = detection_data.get("luminance_change", 0)
    ideal_luminance = 50  # Ideal luminance difference for owl
    min_luminance = config.get("luminance_threshold", 20)
    
    if luminance >= min_luminance:
        # More stringent luminance scoring
        # Apply quadratic scaling based on distance from minimum threshold
        scale_factor = min(1.0, (luminance - min_luminance) / (ideal_luminance - min_luminance))
        luminance_score = min(15, 15 * scale_factor * scale_factor)  # Square it for quadratic scaling
        logger.debug(f"Luminance score: {luminance_score:.1f}% (value: {luminance:.1f})")
    else:
        luminance_score = 0
        logger.debug(f"Luminance change too low: {luminance:.1f} < {min_luminance}")
    
    motion_score = pixel_score + luminance_score
    logger.debug(f"Total motion score: {motion_score:.1f}%")
    
    return motion_score

def calculate_temporal_confidence(camera_name, current_confidence):
    """
    Calculate confidence score based on temporal persistence.
    Modified to require higher quality detections for temporal confidence.
    
    Args:
        camera_name (str): Name of the camera
        current_confidence (float): Current primary confidence score
        
    Returns:
        tuple: (temporal_confidence, consecutive_frames)
    """
    max_frames = 5  # Maximum frames to consider
    
    # Increase minimum confidence required for temporal persistence
    # This prevents low-quality detections from accumulating temporal confidence
    confidence_threshold = 40  # Increased from 30 - higher minimum confidence to consider
    
    # Get frame history for this camera
    history = FRAME_HISTORY.get(camera_name, [])
    
    if not history:
        return 0, 0
    
    # Count consecutive frames with significant confidence
    consecutive_frames = 0
    
    # Include current frame in count if it meets threshold
    if current_confidence >= confidence_threshold:
        consecutive_frames = 1
    
    # Check previous frames with more stringent requirements
    quality_sum = 0
    for frame in reversed(history):
        frame_confidence = frame.get("primary_confidence", 0)
        if frame_confidence >= confidence_threshold:
            consecutive_frames += 1
            # Track the quality of detections for scaling
            quality_sum += (frame_confidence / 100)  # Normalize to 0-1 range
        else:
            break
    
    if consecutive_frames == 0:
        return 0, 0
    
    # Calculate persistence score (up to 20%)
    # Make scaling more stringent - require more frames for full score
    frames_factor = min(consecutive_frames / max_frames, 1.0)
    
    # Add quality scaling - higher quality detections get more temporal confidence
    quality_factor = quality_sum / consecutive_frames if consecutive_frames > 0 else 0
    
    # Combined scaling - both frame count and quality matter
    persistence_score = 20 * frames_factor * quality_factor
    
    logger.debug(f"Temporal confidence: {persistence_score:.1f}% from {consecutive_frames} consecutive frames (quality factor: {quality_factor:.2f})")
    
    return persistence_score, consecutive_frames

def calculate_camera_specific_confidence(detection_data, camera_name, config):
    """
    Calculate camera-specific confidence factors.
    Modified for more accurate camera-specific assessments.
    
    Args:
        detection_data (dict): Detection data
        camera_name (str): Name of the camera
        config (dict): Camera configuration
        
    Returns:
        float: Camera-specific confidence score (0-10%)
    """
    camera_score = 0
    lighting_condition = detection_data.get("lighting_condition", "unknown")
    
    if camera_name == "Wyze Internal Camera":  # In-box camera
        # Get region metrics
        region_metrics = detection_data.get("diff_metrics", {}).get("region_metrics", {})
        
        if region_metrics:
            # More refined position analysis for Wyze Internal Camera
            middle = region_metrics.get("middle", {}).get("mean_luminance", 0)
            top = region_metrics.get("top", {}).get("mean_luminance", 0)
            bottom = region_metrics.get("bottom", {}).get("mean_luminance", 0)
            
            # Owls typically appear in middle or bottom, rarely just at top
            # Night scoring - more stringent for infrared/night conditions
            if lighting_condition == "night":
                # Require stronger contrast between regions at night
                if middle > top * 1.5 and middle > 15:  # Middle must be 50% brighter than top and above minimum
                    camera_score += 3
                    logger.debug("Night mode: Middle region active and sufficiently bright: +3%")
                
                if bottom > top * 1.5 and bottom > 15:  # Bottom must be 50% brighter than top and above minimum
                    camera_score += 3
                    logger.debug("Night mode: Bottom region active and sufficiently bright: +3%")
                    
                # Additional check for overall activity level - night footage should have significant contrast
                avg_luminance = (top + middle + bottom) / 3
                if avg_luminance > 20:  # Higher minimum for good owl detection at night
                    camera_score += 4
                    logger.debug(f"Night mode: Sufficient overall luminance ({avg_luminance:.1f}): +4%")
            else:
                # Day scoring - standard checks
                if middle > top:
                    camera_score += 5
                    logger.debug("Middle region more active than top: +5%")
                
                if bottom > top:
                    camera_score += 5
                    logger.debug("Bottom region more active than top: +5%")
                
    elif camera_name == "Bindy Patio Camera":  # On-box camera
        # Check shape characteristics with higher requirements for Bindy camera
        if detection_data.get("owl_candidates", []):
            best_candidate = max(detection_data["owl_candidates"], key=lambda x: x["area_ratio"])
            
            # More stringent requirements for night mode
            if lighting_condition == "night":
                if best_candidate.get("circularity", 0) > 0.7 and best_candidate.get("area_ratio", 0) > 0.15:
                    camera_score = 10
                    logger.debug("Night mode - High quality shape on Bindy camera: +10%")
                elif best_candidate.get("circularity", 0) > 0.6:
                    camera_score = 5
                    logger.debug("Night mode - Medium quality shape on Bindy camera: +5%")
            else:
                # Day mode - standard checks
                if best_candidate.get("circularity", 0) > 0.6:
                    camera_score = 10
                    logger.debug("Day mode - Good shape on Bindy camera: +10%")
            
    elif camera_name == "Upper Patio Camera":  # Area camera
        # More precise criteria for area camera
        if detection_data.get("owl_candidates", []):
            best_candidate = max(detection_data["owl_candidates"], key=lambda x: x["area_ratio"])
            
            # Night mode - more stringent for area camera at night
            if lighting_condition == "night":
                if (best_candidate.get("circularity", 0) > 0.75 and 
                    best_candidate.get("area_ratio", 0) > 0.03):
                    camera_score = 10
                    logger.debug("Night mode - Excellent shape on area camera: +10%")
                elif best_candidate.get("circularity", 0) > 0.65:
                    camera_score = 5
                    logger.debug("Night mode - Good shape on area camera: +5%")
            else:
                # Day mode
                if best_candidate.get("circularity", 0) > 0.7:
                    camera_score = 10
                    logger.debug("Day mode - High circularity on area camera: +10%")
                elif best_candidate.get("circularity", 0) > 0.6:
                    camera_score = 5
                    logger.debug("Day mode - Good circularity on area camera: +5%")
    
    logger.debug(f"Camera-specific confidence for {camera_name} ({lighting_condition}): {camera_score}%")
    return camera_score

def calculate_owl_confidence(detection_data, camera_name, config):
    """
    Calculate the overall owl confidence score without making detection decisions.
    
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
    Check if an owl is detected based on confidence score and camera config.
    This function only performs the check without making alert decisions.
    
    Args:
        confidence_score (float): The calculated confidence score (0-100%)
        camera_name (str): Name of the camera
        config (dict): Camera configuration dictionary
        
    Returns:
        bool: True if owl is detected, False otherwise
    """
    # Get camera-specific threshold or use default
    confidence_threshold = config.get("owl_confidence_threshold", 60.0)
    
    # Check if confidence meets threshold
    is_detected = confidence_score >= confidence_threshold
    
    if is_detected:
        logger.info(f"Owl detected for {camera_name} with {confidence_score:.1f}% confidence (threshold: {confidence_threshold:.1f}%)")
    else:
        logger.debug(f"No owl detected for {camera_name} - {confidence_score:.1f}% confidence below threshold of {confidence_threshold:.1f}%")
    
    return is_detected

def reset_frame_history():
    """Reset all frame history (typically called on system restart)."""
    global FRAME_HISTORY
    FRAME_HISTORY = {
        "Wyze Internal Camera": [],
        "Bindy Patio Camera": [],
        "Upper Patio Camera": []
    }
    logger.info("Frame history reset")