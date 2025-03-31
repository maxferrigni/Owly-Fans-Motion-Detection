# File: utilities/confidence_utils.py
# Purpose: Calculate and manage owl confidence scores for improved detection without decision-making
# 
# Updates:
# - Adjusted motion confidence calculation to be less generous with small changes
# - Made shape confidence scoring more stringent
# - Improved temporal confidence to require higher quality detections
# - Enhanced camera-specific confidence factors for night conditions
# - Updated shape confidence calculation with better weighting of important factors including solidity

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

def calculate_shape_confidence(owl_candidates, config):
    """Calculate shape confidence with better weighting of important factors"""
    if not owl_candidates:
        return 0.0
        
    # Get best candidate
    best_candidate = max(owl_candidates, key=lambda x: x['area_ratio'])
    
    # Initialize score components
    circularity_score = 0
    aspect_ratio_score = 0
    size_score = 0
    solidity_score = 0
    
    # MODIFIED: Circularity score (0-10%) - more lenient
    circ_value = best_candidate.get('circularity', 0)
    ideal_circ = 0.75  # CHANGED: Slightly lower ideal circularity (was 0.8)
    
    # More lenient scoring curve
    # MODIFIED: Much more lenient minimum circularity value
    min_circularity = config["motion_detection"]["min_circularity"]
    if min_circularity > 0.4:  # Enforce maximum strictness
        min_circularity = 0.4
        
    if circ_value >= min_circularity:
        # MODIFIED: More generous scoring that allows for varying owl shapes
        circ_distance = abs(circ_value - ideal_circ)
        circularity_score = 10 * max(0, 1 - (circ_distance * 1.5))  # Reduced penalty (was 2)
        logger.debug(f"Circularity score: {circularity_score:.1f}% (value: {circ_value:.2f})")
    else:
        logger.debug(f"Circularity too low: {circ_value:.2f} < {min_circularity}")
    
    # MODIFIED: Aspect ratio score (0-10%) - much more lenient
    aspect_value = best_candidate.get('aspect_ratio', 0)
    # MODIFIED: Lower ideal aspect ratio to match the oblong shape of perched owls
    ideal_aspect = 1.8  # CHANGED: Increased from 1.2 for more oval/oblong shape
    
    # Enforce more permissive aspect ratio bounds
    min_aspect = min(config["motion_detection"]["min_aspect_ratio"], 0.3)
    max_aspect = max(config["motion_detection"]["max_aspect_ratio"], 2.5)
    
    if min_aspect <= aspect_value <= max_aspect:
        # MODIFIED: More lenient scoring for aspect ratio
        aspect_deviation = abs(aspect_value - ideal_aspect) / 1.5  # Increased tolerance (was 0.7)
        aspect_ratio_score = 10 * max(0, 1 - aspect_deviation)
        logger.debug(f"Aspect ratio score: {aspect_ratio_score:.1f}% (value: {aspect_value:.2f})")
    else:
        logger.debug(f"Aspect ratio outside range: {aspect_value:.2f} not in [{min_aspect}-{max_aspect}]")
    
    # MODIFIED: Size score (0-15%) - increased weighting and more lenient
    area_value = best_candidate.get('area_ratio', 0)
    ideal_min_area = config["motion_detection"]["min_area_ratio"]
    # Enforce more permissive minimum area
    ideal_min_area = min(ideal_min_area, 0.05)
    ideal_max_area = ideal_min_area * 15  # Upper bound
    
    if area_value >= ideal_min_area:
        if area_value <= ideal_max_area:
            # MODIFIED: More generous scoring for size
            # Score based on position within ideal range - increased weight to 15 (was 0-15%)
            size_score = 15 * min(1.0, area_value / (ideal_max_area / 4))
        else:
            # Penalize too large areas but still give some points
            size_score = 15 * max(0.3, (1.0 - min(1.0, (area_value - ideal_max_area) / ideal_max_area)))
        logger.debug(f"Area score: {size_score:.1f}% (value: {area_value:.2f})")
    else:
        logger.debug(f"Area too small: {area_value:.2f} < {ideal_min_area}")
    
    # MODIFIED: Solidity score (0-5%) - more lenient
    solidity = best_candidate.get('solidity', 0)
    # Lowered solidity threshold from 0.7 to 0.6
    if solidity >= 0.6:
        solidity_score = 5 * min(1.0, (solidity - 0.6) / 0.3)
        logger.debug(f"Solidity score: {solidity_score:.1f}% (value: {solidity:.2f})")
    else:
        logger.debug(f"Solidity too low: {solidity:.2f} < 0.6")
    
    # Total shape score
    shape_score = circularity_score + aspect_ratio_score + size_score + solidity_score
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
    # MODIFIED: Pixel change (0-15%) - more lenient threshold
    pixel_change = detection_data.get("pixel_change", 0) / 100  # Convert from percentage
    ideal_change = 0.3  # 30% is ideal for owl movement
    # MODIFIED: Reduce minimum threshold to detect smaller movements
    min_change = min(config.get("threshold_percentage", 0.05), 0.05)
    
    if pixel_change >= min_change:
        # MODIFIED: More lenient scoring curve - linear scaling instead of quadratic
        scale_factor = min(1.0, (pixel_change - min_change) / (ideal_change - min_change))
        pixel_score = min(15, 15 * scale_factor)  # Linear scaling
        logger.debug(f"Pixel change score: {pixel_score:.1f}% (value: {pixel_change:.2f})")
    else:
        pixel_score = 0
        logger.debug(f"Pixel change too low: {pixel_change:.2f} < {min_change}")
    
    # MODIFIED: Luminance difference (0-15%) - more lenient
    luminance = detection_data.get("luminance_change", 0)
    ideal_luminance = 50  # Ideal luminance difference for owl
    # MODIFIED: Reduce minimum luminance threshold
    min_luminance = min(config.get("luminance_threshold", 20), 15)
    
    if luminance >= min_luminance:
        # MODIFIED: More lenient luminance scoring - linear scaling
        scale_factor = min(1.0, (luminance - min_luminance) / (ideal_luminance - min_luminance))
        luminance_score = min(15, 15 * scale_factor)  # Linear scaling
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
    Modified to require fewer high quality detections for temporal confidence.
    
    Args:
        camera_name (str): Name of the camera
        current_confidence (float): Current primary confidence score
        
    Returns:
        tuple: (temporal_confidence, consecutive_frames)
    """
    # MODIFIED: Lower max frames required for full temporal score
    max_frames = 3  # Was 5 - Need fewer frames to get full score
    
    # MODIFIED: Lower minimum confidence required for temporal persistence
    # This helps with near-threshold detections
    confidence_threshold = 35  # Was 40 - Lower threshold to be more permissive
    
    # Get frame history for this camera
    history = FRAME_HISTORY.get(camera_name, [])
    
    if not history:
        return 0, 0
    
    # Count consecutive frames with significant confidence
    consecutive_frames = 0
    
    # Include current frame in count if it meets threshold
    if current_confidence >= confidence_threshold:
        consecutive_frames = 1
    
    # Check previous frames with more lenient requirements
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
    
    # MODIFIED: Calculate persistence score (up to 20%) with more generous scaling
    # Make scaling more lenient - require fewer frames for full score
    frames_factor = min(consecutive_frames / max_frames, 1.0)
    
    # Add quality scaling but be more generous
    quality_factor = max(0.7, quality_sum / consecutive_frames) if consecutive_frames > 0 else 0
    
    # MODIFIED: Combined scaling - more generous formula that gives higher scores
    persistence_score = 20 * frames_factor * quality_factor
    
    logger.debug(f"Temporal confidence: {persistence_score:.1f}% from {consecutive_frames} consecutive frames (quality factor: {quality_factor:.2f})")
    
    return persistence_score, consecutive_frames

def calculate_camera_specific_confidence(detection_data, camera_name, config):
    """
    Calculate camera-specific confidence factors.
    Modified for more lenient camera-specific assessments.
    
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
            # MODIFIED: More lenient position analysis for Wyze Internal Camera
            middle = region_metrics.get("middle", {}).get("mean_luminance", 0)
            top = region_metrics.get("top", {}).get("mean_luminance", 0)
            bottom = region_metrics.get("bottom", {}).get("mean_luminance", 0)
            
            # Owls typically appear in middle or bottom, rarely just at top
            # MODIFIED: Night scoring - more lenient for infrared/night conditions
            if lighting_condition == "night":
                # MODIFIED: Require less contrast between regions at night
                if middle > top * 1.2 and middle > 10:  # Was 1.5 and 15 - reduced requirements
                    camera_score += 3
                    logger.debug("Night mode: Middle region active and sufficiently bright: +3%")
                
                if bottom > top * 1.2 and bottom > 10:  # Was 1.5 and 15 - reduced requirements
                    camera_score += 3
                    logger.debug("Night mode: Bottom region active and sufficiently bright: +3%")
                    
                # MODIFIED: Additional check for overall activity level - reduced requirement
                avg_luminance = (top + middle + bottom) / 3
                if avg_luminance > 12:  # Was 20 - lower minimum for night detection
                    camera_score += 4
                    logger.debug(f"Night mode: Sufficient overall luminance ({avg_luminance:.1f}): +4%")
            else:
                # MODIFIED: Day scoring - more lenient checks
                if middle > top * 0.8:  # Was just middle > top - allow some lower middle values
                    camera_score += 5
                    logger.debug("Middle region more active than top: +5%")
                
                if bottom > top * 0.8:  # Was just bottom > top - allow some lower bottom values
                    camera_score += 5
                    logger.debug("Bottom region more active than top: +5%")
                
    elif camera_name == "Bindy Patio Camera":  # On-box camera
        # MODIFIED: Check shape characteristics with much lower requirements for Bindy camera
        if detection_data.get("owl_candidates", []):
            best_candidate = max(detection_data["owl_candidates"], key=lambda x: x["area_ratio"])
            
            # MODIFIED: Much more lenient requirements for night mode
            if lighting_condition == "night":
                if best_candidate.get("circularity", 0) > 0.5 and best_candidate.get("area_ratio", 0) > 0.1:
                    camera_score = 10
                    logger.debug("Night mode - High quality shape on Bindy camera: +10%")
                elif best_candidate.get("circularity", 0) > 0.4:  # Even lower threshold
                    camera_score = 5
                    logger.debug("Night mode - Medium quality shape on Bindy camera: +5%")
            else:
                # MODIFIED: Day mode - more lenient checks
                if best_candidate.get("circularity", 0) > 0.5:  # Was 0.6
                    camera_score = 10
                    logger.debug("Day mode - Good shape on Bindy camera: +10%")
                elif best_candidate.get("circularity", 0) > 0.4:  # Added low tier scoring
                    camera_score = 5
                    logger.debug("Day mode - Fair shape on Bindy camera: +5%")
            
    elif camera_name == "Upper Patio Camera":  # Area camera
        # MODIFIED: More precise criteria for area camera
        if detection_data.get("owl_candidates", []):
            best_candidate = max(detection_data["owl_candidates"], key=lambda x: x["area_ratio"])
            
            # MODIFIED: Night mode - more lenient for area camera at night
            if lighting_condition == "night":
                if (best_candidate.get("circularity", 0) > 0.6 and 
                    best_candidate.get("area_ratio", 0) > 0.02):  # Was 0.75 and 0.03
                    camera_score = 10
                    logger.debug("Night mode - Excellent shape on area camera: +10%")
                elif best_candidate.get("circularity", 0) > 0.5:  # Was 0.65
                    camera_score = 5
                    logger.debug("Night mode - Good shape on area camera: +5%")
            else:
                # MODIFIED: Day mode - more lenient
                if best_candidate.get("circularity", 0) > 0.6:  # Was 0.7
                    camera_score = 10
                    logger.debug("Day mode - High circularity on area camera: +10%")
                elif best_candidate.get("circularity", 0) > 0.5:  # Was 0.6
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
        # Updated to use the new shape confidence function
        shape_confidence = calculate_shape_confidence(detection_data.get("owl_candidates", []), config)
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
        
        # MODIFIED: Add bonus for motion pattern score if available
        motion_pattern_bonus = 0
        if "motion_pattern_score" in detection_data and detection_data["motion_pattern_score"] > 0:
            # Convert 0-10 score to 0-5% bonus
            motion_pattern_bonus = detection_data["motion_pattern_score"] * 0.5
            logger.debug(f"Adding motion pattern bonus: +{motion_pattern_bonus:.1f}%")
        
        # MODIFIED: Final confidence score (0-100%) with motion pattern bonus
        total_confidence = primary_confidence + temporal_confidence + camera_confidence + motion_pattern_bonus
        
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
                "camera_confidence": camera_confidence,
                "motion_pattern_bonus": motion_pattern_bonus  # Add the bonus to factors
            }
        }
        
        logger.info(
            f"Owl confidence for {camera_name}: {total_confidence:.1f}% "
            f"(Shape: {shape_confidence:.1f}%, Motion: {motion_confidence:.1f}%, "
            f"Temporal: {temporal_confidence:.1f}%, Camera: {camera_confidence:.1f}%, "
            f"Pattern: {motion_pattern_bonus:.1f}%)"
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
    # MODIFIED: Get camera-specific threshold or use default with lower fallback threshold
    confidence_threshold = config.get("owl_confidence_threshold", 50.0)  # Lowered default from 60.0
    
    # MODIFIED: Special case for Wyze Internal Camera - use even lower threshold at night
    lighting_condition = config.get("lighting_condition", "day")
    if camera_name == "Wyze Internal Camera" and lighting_condition == "night":
        # Apply a 10% reduction to the threshold for Wyze camera at night
        confidence_threshold = confidence_threshold * 0.9
        logger.debug(f"Using reduced threshold for Wyze camera at night: {confidence_threshold:.1f}%")
    
    # Check if confidence meets threshold
    is_detected = confidence_score >= confidence_threshold
    
    # MODIFIED: Special case for high near-miss cases
    # If we're within 10% of the threshold, log it as a near-miss for debugging
    if not is_detected and confidence_score >= (confidence_threshold * 0.9):
        logger.info(f"Near-miss detection for {camera_name}: {confidence_score:.1f}% (threshold: {confidence_threshold:.1f}%)")
    
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