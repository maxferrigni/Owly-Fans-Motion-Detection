# File: utilities/confidence_utils.py
# Purpose: Calculate and manage owl confidence scores for improved detection without decision-making
# 
# Updates:
# - Adjusted motion confidence calculation to be less generous with small changes
# - Made shape confidence scoring more stringent
# - Improved temporal confidence to require higher quality detections
# - Enhanced camera-specific confidence factors for night conditions
# - Updated shape confidence calculation with better weighting of important factors including solidity
# - Modified to use more permissive and additive approach for v1.9 update
# - Changed confidence calculation to allow strong signals in one area to compensate for weak ones
# - Added cap for confidence score at 100% for v1.91 update

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
    Modified to be more permissive and give higher weight to substantial motion.
    
    Args:
        detection_data (dict): Detection data including motion metrics
        config (dict): Camera configuration
        
    Returns:
        float: Motion confidence score (0-25%)
    """
    # MODIFIED: Pixel change (0-25%) - increased from 0-15%
    pixel_change = detection_data.get("pixel_change", 0) / 100  # Convert from percentage
    ideal_change = 0.2  # 20% is ideal for owl movement (reduced from 30%)
    # Reduce minimum threshold to detect smaller movements
    min_change = min(config.get("threshold_percentage", 0.05), 0.03)  # Reduced from 0.05
    
    if pixel_change >= min_change:
        # More permissive scoring curve with bonus for very significant changes
        scale_factor = min(1.0, (pixel_change - min_change) / (ideal_change - min_change))
        pixel_score = min(25, 25 * scale_factor)  # Increased from 15 to 25
        
        # Add bonus for very high pixel changes
        if pixel_change > ideal_change * 1.5:
            pixel_score += min(10, (pixel_change - ideal_change * 1.5) * 100)
        logger.debug(f"Pixel change score: {pixel_score:.1f}% (value: {pixel_change:.2f})")
    else:
        pixel_score = 0
        logger.debug(f"Pixel change too low: {pixel_change:.2f} < {min_change}")
    
    # MODIFIED: Luminance difference (0-15%) - unchanged weight but more lenient
    luminance = detection_data.get("luminance_change", 0)
    ideal_luminance = 40  # Ideal luminance difference (lowered from 50)
    # Reduce minimum luminance threshold
    min_luminance = min(config.get("luminance_threshold", 20), 10)  # Lowered from 15
    
    if luminance >= min_luminance:
        # More lenient luminance scoring
        scale_factor = min(1.0, (luminance - min_luminance) / (ideal_luminance - min_luminance))
        luminance_score = min(15, 15 * scale_factor)
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
    Modified to give higher weight to persistence even with fewer frames.
    
    Args:
        camera_name (str): Name of the camera
        current_confidence (float): Current primary confidence score
        
    Returns:
        tuple: (temporal_confidence, consecutive_frames)
    """
    # MODIFIED: Lower max frames required for full temporal score
    max_frames = 2  # Was 3 - Need even fewer frames to get full score
    
    # MODIFIED: Lower minimum confidence required for temporal persistence
    confidence_threshold = 25  # Was 35 - Much lower threshold to be more permissive
    
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
    
    # MODIFIED: Calculate persistence score (up to 30%) with more generous scaling - increased from 20%
    # Make scaling more lenient - require fewer frames for full score
    frames_factor = min(consecutive_frames / max_frames, 1.0)
    
    # Add quality scaling but be more generous
    quality_factor = max(0.8, quality_sum / consecutive_frames) if consecutive_frames > 0 else 0  # Increased from 0.7
    
    # MODIFIED: Combined scaling - more generous formula that gives higher scores
    persistence_score = 30 * frames_factor * quality_factor  # Increased from 20 to 30
    
    logger.debug(f"Temporal confidence: {persistence_score:.1f}% from {consecutive_frames} consecutive frames (quality factor: {quality_factor:.2f})")
    
    return persistence_score, consecutive_frames

def calculate_camera_specific_confidence(detection_data, camera_name, config):
    """
    Calculate camera-specific confidence factors.
    Modified for much more lenient camera-specific assessments, especially for Wyze camera.
    
    Args:
        detection_data (dict): Detection data
        camera_name (str): Name of the camera
        config (dict): Camera configuration
        
    Returns:
        float: Camera-specific confidence score (0-20%)
    """
    camera_score = 0
    lighting_condition = detection_data.get("lighting_condition", "unknown")
    
    if camera_name == "Wyze Internal Camera":  # In-box camera
        # Get region metrics
        region_metrics = detection_data.get("diff_metrics", {}).get("region_metrics", {})
        
        if region_metrics:
            # MODIFIED: Much more lenient position analysis for Wyze Internal Camera
            middle = region_metrics.get("middle", {}).get("mean_luminance", 0)
            top = region_metrics.get("top", {}).get("mean_luminance", 0)
            bottom = region_metrics.get("bottom", {}).get("mean_luminance", 0)
            
            # MODIFIED: ANY significant activity in middle or bottom should score highly
            if lighting_condition == "night":
                # Middle/bottom activity is highly indicative of owl at night
                if middle > 5:  # Was 10 - extremely permissive
                    camera_score += 10  # Was 3 - much higher score
                    logger.debug("Night mode: Middle region active: +10%")
                
                if bottom > 5:  # Was 10 - extremely permissive
                    camera_score += 10  # Was 3 - much higher score
                    logger.debug("Night mode: Bottom region active: +10%")
            else:
                # Day mode - still be very permissive
                if middle > top * 0.5:  # Was 0.8 - extremely permissive
                    camera_score += 10  # Was 5 - doubled
                    logger.debug("Middle region more active than top: +10%")
                
                if bottom > top * 0.5:  # Was 0.8 - extremely permissive
                    camera_score += 10  # Was 5 - doubled
                    logger.debug("Bottom region more active than top: +10%")
            
            # NEW: Add high bonus for significant light changes anywhere in the box
            pixel_change = detection_data.get("pixel_change", 0)
            if pixel_change > 30:
                camera_score = max(camera_score, 15)  # Ensure at least 15% score for high pixel change
                logger.debug(f"High pixel change detected ({pixel_change:.1f}%): +15%")
                
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
    Calculate the overall owl confidence score with a more permissive approach.
    Modified to use a layered scoring system rather than requiring all factors simultaneously.
    
    Args:
        detection_data (dict): Detection data with all metrics
        camera_name (str): Name of the camera
        config (dict): Camera configuration
        
    Returns:
        dict: Confidence results including score and factors
    """
    try:
        # Calculate primary confidence components
        shape_confidence = calculate_shape_confidence(detection_data.get("owl_candidates", []), config)
        motion_confidence = calculate_motion_confidence(detection_data, config)
        
        # MODIFIED: Primary confidence calculation - ensure motion alone can trigger detection
        # Use higher of shape_confidence or motion_confidence as base, rather than sum
        # This ensures that strong signals in one area can compensate for weak ones in another
        primary_confidence = max(shape_confidence, motion_confidence * 1.5)
        
        # Add a portion of the other confidence metric to reward having both
        if shape_confidence > 0 and motion_confidence > 0:
            primary_confidence += min(shape_confidence, motion_confidence) * 0.5
        
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
        
        # Add motion pattern bonus
        motion_pattern_bonus = 0
        if "motion_pattern_score" in detection_data and detection_data["motion_pattern_score"] > 0:
            motion_pattern_bonus = detection_data["motion_pattern_score"] * 0.8  # Increased from 0.5
            logger.debug(f"Adding enhanced motion pattern bonus: +{motion_pattern_bonus:.1f}%")
        
        # MODIFIED: Add a bonus for high pixel change percentage regardless of other factors
        pixel_change_bonus = 0
        pixel_change = detection_data.get("pixel_change", 0)
        if pixel_change > 30:
            # Linear bonus from 0% to 15% for pixel changes between 30% and 60%
            pixel_change_bonus = min(15, (pixel_change - 30) * 0.5)
            logger.debug(f"Adding pixel change bonus: +{pixel_change_bonus:.1f}%")
        
        # MODIFIED: Add position-based bonus for internal camera - highly weighted
        position_bonus = 0
        if camera_name == "Wyze Internal Camera":
            region_metrics = detection_data.get("diff_metrics", {}).get("region_metrics", {})
            if region_metrics:
                middle = region_metrics.get("middle", {}).get("pixel_change", 0)
                bottom = region_metrics.get("bottom", {}).get("pixel_change", 0)
                
                # If significant activity in middle or bottom, add a strong position bonus
                if middle > 10 or bottom > 10:
                    position_bonus = min(20, max(middle, bottom) * 0.8)
                    logger.debug(f"Adding position bonus for {camera_name}: +{position_bonus:.1f}%")
        
        # MODIFIED: Final confidence score with additive bonuses
        total_confidence = primary_confidence + temporal_confidence + camera_confidence + motion_pattern_bonus + pixel_change_bonus + position_bonus
        
        # MODIFIED: Apply override rules for obvious detections
        lighting_condition = detection_data.get("lighting_condition", "day")
        
        # Override 1: High motion with consecutive frames should always detect
        if motion_confidence > 40 and consecutive_frames >= 1:
            total_confidence = max(total_confidence, 65.0)
            logger.info(f"Applied high motion override: Confidence set to minimum 65%")
        
        # Override 2: Very high pixel change should always trigger detection
        if pixel_change > 50:
            total_confidence = max(total_confidence, 60.0)
            logger.info(f"Applied high pixel change override: Confidence set to minimum 60%")
        
        # Override 3: Camera-specific overrides - especially for Wyze camera
        if camera_name == "Wyze Internal Camera":
            region_metrics = detection_data.get("diff_metrics", {}).get("region_metrics", {})
            if region_metrics:
                middle = region_metrics.get("middle", {}).get("pixel_change", 0)
                bottom = region_metrics.get("bottom", {}).get("pixel_change", 0)
                
                # For Wyze, persistent motion in the lower half should be enough
                if (middle > 15 or bottom > 15) and consecutive_frames >= 1:
                    total_confidence = max(total_confidence, 55.0)
                    logger.info(f"Applied Wyze position override: Confidence set to minimum 55%")
        
        # Update frame history
        update_frame_history(
            camera_name, 
            primary_confidence, 
            total_confidence
        )
        
        # Log the raw confidence for debugging
        logger.info(
            f"Owl confidence for {camera_name} (raw): {total_confidence:.1f}% "
            f"(Shape: {shape_confidence:.1f}%, Motion: {motion_confidence:.1f}%, "
            f"Temporal: {temporal_confidence:.1f}%, Camera: {camera_confidence:.1f}%, "
            f"Pattern: {motion_pattern_bonus:.1f}%, Pixel: {pixel_change_bonus:.1f}%, "
            f"Position: {position_bonus:.1f}%)"
        )
        
        # Cap confidence at 100% before returning the result
        capped_confidence = min(100.0, total_confidence)
        
        if total_confidence > 100.0:
            logger.info(f"Capped confidence from {total_confidence:.1f}% to 100.0%")
        
        # Prepare comprehensive confidence results
        confidence_results = {
            "owl_confidence": capped_confidence,
            "consecutive_owl_frames": consecutive_frames,
            "confidence_factors": {
                "shape_confidence": shape_confidence,
                "motion_confidence": motion_confidence,
                "temporal_confidence": temporal_confidence,
                "camera_confidence": camera_confidence,
                "motion_pattern_bonus": motion_pattern_bonus,
                "pixel_change_bonus": pixel_change_bonus,
                "position_bonus": position_bonus
            }
        }
        
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
    Modified to use much lower thresholds, especially at night and for the Wyze camera.
    
    Args:
        confidence_score (float): The calculated confidence score (0-100%)
        camera_name (str): Name of the camera
        config (dict): Camera configuration dictionary
        
    Returns:
        bool: True if owl is detected, False otherwise
    """
    # MODIFIED: Get camera-specific threshold with much lower fallback threshold
    confidence_threshold = config.get("owl_confidence_threshold", 45.0)  # Lowered default from 50.0
    
    # MODIFIED: Special case for Wyze Internal Camera - use even lower threshold
    lighting_condition = config.get("lighting_condition", "day")
    if camera_name == "Wyze Internal Camera":
        if lighting_condition == "night":
            # Apply a 25% reduction to the threshold for Wyze camera at night
            confidence_threshold = confidence_threshold * 0.75  # Was 0.9 - much more reduction
            logger.debug(f"Using greatly reduced threshold for Wyze camera at night: {confidence_threshold:.1f}%")
        else:
            # Also reduce for day but less drastically
            confidence_threshold = confidence_threshold * 0.85  # Was not reduced before
            logger.debug(f"Using reduced threshold for Wyze camera in day: {confidence_threshold:.1f}%")
    
    # MODIFIED: Cap the maximum threshold to ensure reasonable sensitivity
    confidence_threshold = min(confidence_threshold, 40.0)  # Was 45.0 - even lower cap
    
    # Check if confidence meets threshold
    is_detected = confidence_score >= confidence_threshold
    
    # MODIFIED: Special case for high near-miss cases
    # If we're within 15% of the threshold, log it as a near-miss for debugging
    if not is_detected and confidence_score >= (confidence_threshold * 0.85):  # Was 0.9 - wider near-miss window
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