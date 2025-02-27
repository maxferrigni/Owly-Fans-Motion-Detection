# File: utilities/owl_confidence.py
# Purpose: Calculate owl confidence scores based on multiple detection factors

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
        detection_data (dict): Detection information from owl_detection_utils.py
        config (dict): Camera configuration
        
    Returns:
        float: Shape confidence score (0-40%)
    """
    shape_score = 0
    
    if not detection_data.get("owl_candidates", []):
        return 0
    
    # Get best candidate based on area ratio
    best_candidate = max(detection_data["owl_candidates"], key=lambda x: x["area_ratio"])
    
    # Circularity score (0-10%)
    min_circ = config["motion_detection"]["min_circularity"]
    ideal_circ = 0.8  # Ideal owl circularity
    circ_value = best_candidate.get("circularity", 0)
    
    if circ_value >= min_circ:
        # Calculate how close to ideal circularity (higher is better)
        circ_score = min(10, (circ_value / ideal_circ) * 10)
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
        # Calculate how close to ideal aspect ratio (higher is better)
        aspect_deviation = abs(aspect_value - ideal_aspect) / (max_aspect - min_aspect)
        aspect_score = 10 * (1 - min(1, aspect_deviation))
        logger.debug(f"Aspect ratio score: {aspect_score:.1f}% (value: {aspect_value:.2f})")
    else:
        aspect_score = 0
        logger.debug(f"Aspect ratio outside range: {aspect_value:.2f} not in [{min_aspect}-{max_aspect}]")
    
    # Size score (0-20%)
    min_area = config["motion_detection"]["min_area_ratio"]
    ideal_area = 0.2  # Ideal owl size relative to frame
    area_value = best_candidate.get("area_ratio", 0)
    
    if area_value >= min_area:
        # Calculate area score based on how close to ideal size
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
    
    Args:
        detection_data (dict): Detection information from owl_detection_utils.py
        config (dict): Camera configuration
        
    Returns:
        float: Motion confidence score (0-30%)
    """
    # Pixel change score (0-15%)
    pixel_change = detection_data.get("pixel_change", 0) / 100  # Convert from percentage
    ideal_change = 0.3  # 30% is ideal for owl movement
    min_change = config.get("threshold_percentage", 0.05)
    
    if pixel_change >= min_change:
        # Calculate score based on how close to ideal change
        pixel_score = min(15, (pixel_change / ideal_change) * 15)
        logger.debug(f"Pixel change score: {pixel_score:.1f}% (value: {pixel_change:.2f})")
    else:
        pixel_score = 0
        logger.debug(f"Pixel change too low: {pixel_change:.2f} < {min_change}")
    
    # Luminance difference score (0-15%)
    luminance = detection_data.get("luminance_change", 0)
    ideal_luminance = 50  # Ideal luminance difference for owl
    min_luminance = config.get("luminance_threshold", 20)
    
    if luminance >= min_luminance:
        # Calculate score based on how close to ideal luminance
        luminance_score = min(15, (luminance / ideal_luminance) * 15)
        logger.debug(f"Luminance score: {luminance_score:.1f}% (value: {luminance:.1f})")
    else:
        luminance_score = 0
        logger.debug(f"Luminance change too low: {luminance:.1f} < {min_luminance}")
    
    motion_score = pixel_score + luminance_score
    logger.debug(f"Total motion score: {motion_score:.1f}%")
    
    return motion_score

def calculate_temporal_confidence(current_data, frame_history, config):
    """
    Calculate confidence score based on temporal persistence.
    
    Args:
        current_data (dict): Current frame detection information
        frame_history (list): List of previous frame data
        config (dict): Camera configuration
        
    Returns:
        float: Temporal persistence score (0-20%)
    """
    if not frame_history:
        return 0
    
    # Define thresholds
    confidence_threshold = 30  # Minimum primary confidence to consider
    max_frames = 5  # Maximum frames to consider for full score
    
    # Count consecutive frames with significant confidence
    consecutive_frames = 0
    
    # Check previous frames for confidence above threshold
    for frame in reversed(frame_history):
        if frame.get("primary_confidence", 0) >= confidence_threshold:
            consecutive_frames += 1
        else:
            break
    
    # Calculate persistence score (up to 20%)
    persistence_factor = min(consecutive_frames / max_frames, 1.0)
    persistence_score = 20 * persistence_factor
    
    logger.debug(f"Temporal persistence score: {persistence_score:.1f}% ({consecutive_frames} consecutive frames)")
    
    return persistence_score, consecutive_frames

def calculate_camera_specific_confidence(detection_data, camera_name, config):
    """
    Calculate confidence score based on camera-specific factors.
    
    Args:
        detection_data (dict): Detection information
        camera_name (str): Name of the camera
        config (dict): Camera configuration
        
    Returns:
        float: Camera-specific confidence score (0-10%)
    """
    camera_score = 0
    
    if camera_name == "Wyze Internal Camera":  # In-box camera
        # Get region metrics if available
        if "diff_metrics" in detection_data and "region_metrics" in detection_data["diff_metrics"]:
            region_metrics = detection_data["diff_metrics"]["region_metrics"]
            
            # Owls often appear in middle or bottom regions of box
            if region_metrics["middle"]["mean_luminance"] > region_metrics["top"]["mean_luminance"]:
                camera_score += 5
                logger.debug("Middle region more active than top: +5%")
            
            if region_metrics["bottom"]["mean_luminance"] > region_metrics["top"]["mean_luminance"]:
                camera_score += 5
                logger.debug("Bottom region more active than top: +5%")
                
    elif camera_name == "Bindy Patio Camera":  # On-box camera
        # For on-box camera, we check if the motion is consistent with perching
        # This would need more sophisticated position analysis
        # For now, use shape detection as primary indicator
        if detection_data.get("owl_candidates", []):
            camera_score = 10
            logger.debug("On-box camera with shape candidates: +10%")
            
    elif camera_name == "Upper Patio Camera":  # Area camera
        # For area camera, we require more distinct shape characteristics
        # and typically need higher thresholds due to wider field of view
        if detection_data.get("owl_candidates", []):
            best_candidate = max(detection_data["owl_candidates"], key=lambda x: x["area_ratio"])
            # Higher circularity requirement for area camera
            if best_candidate.get("circularity", 0) > 0.7:
                camera_score = 10
                logger.debug("Area camera with high circularity shape: +10%")
            else:
                camera_score = 5
                logger.debug("Area camera with shape candidates: +5%")
    
    logger.debug(f"Camera-specific score for {camera_name}: {camera_score:.1f}%")
    return camera_score

def calculate_owl_confidence(detection_data, camera_name, config, frame_history=None):
    """
    Calculate overall owl confidence score based on multiple factors.
    
    Args:
        detection_data (dict): Detection information from owl_detection_utils.py
        camera_name (str): Name of the camera
        config (dict): Camera configuration
        frame_history (list, optional): List of previous frame data
        
    Returns:
        tuple: (total_confidence, updated_history, confidence_breakdown)
    """
    try:
        # Initialize frame history if not provided
        if frame_history is None:
            frame_history = FRAME_HISTORY.get(camera_name, [])
        
        # Calculate primary confidence (shape and motion)
        shape_confidence = calculate_shape_confidence(detection_data, config)
        motion_confidence = calculate_motion_confidence(detection_data, config)
        primary_confidence = shape_confidence + motion_confidence
        
        # Calculate persistence confidence
        temporal_confidence, consecutive_frames = calculate_temporal_confidence(
            detection_data, frame_history, config
        )
        
        # Calculate camera-specific confidence
        camera_confidence = calculate_camera_specific_confidence(
            detection_data, camera_name, config
        )
        
        # Calculate final confidence score (0-100%)
        total_confidence = primary_confidence + temporal_confidence + camera_confidence
        
        # Create confidence breakdown for logging and storage
        confidence_breakdown = {
            "shape_confidence": shape_confidence,
            "motion_confidence": motion_confidence,
            "primary_confidence": primary_confidence,
            "temporal_confidence": temporal_confidence,
            "camera_confidence": camera_confidence,
            "consecutive_frames": consecutive_frames,
            "total_confidence": total_confidence
        }
        
        # Store this frame's primary confidence in history
        current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
        history_entry = {
            "timestamp": current_time,
            "primary_confidence": primary_confidence,
            "total_confidence": total_confidence
        }
        
        # Update history
        updated_history = frame_history.copy()
        updated_history.append(history_entry)
        
        # Trim history to keep only last N frames
        if len(updated_history) > MAX_FRAME_HISTORY:
            updated_history = updated_history[-MAX_FRAME_HISTORY:]
        
        logger.info(
            f"Owl confidence for {camera_name}: {total_confidence:.1f}% "
            f"(Shape: {shape_confidence:.1f}%, Motion: {motion_confidence:.1f}%, "
            f"Temporal: {temporal_confidence:.1f}%, Camera: {camera_confidence:.1f}%)"
        )
        
        return total_confidence, updated_history, confidence_breakdown
        
    except Exception as e:
        logger.error(f"Error calculating owl confidence: {e}")
        return 0.0, frame_history, {"error": str(e)}

def determine_owl_presence(confidence_score, consecutive_frames, config):
    """
    Determine if an owl is present based on confidence score and frame persistence.
    
    Args:
        confidence_score (float): Overall confidence score (0-100%)
        consecutive_frames (int): Number of consecutive frames with significant confidence
        config (dict): Camera configuration
        
    Returns:
        bool: True if owl is determined to be present
    """
    # Get confidence threshold from config or use default
    confidence_threshold = config.get("owl_confidence_threshold", 60)
    
    # Get consecutive frames threshold from config or use default
    frames_threshold = config.get("consecutive_frames_threshold", 2)
    
    # Determine owl presence based on thresholds
    is_owl_present = (confidence_score >= confidence_threshold and 
                      consecutive_frames >= frames_threshold)
    
    if is_owl_present:
        logger.info(
            f"Owl determined to be present: {confidence_score:.1f}% confidence, "
            f"{consecutive_frames} consecutive frames"
        )
    else:
        if confidence_score < confidence_threshold:
            logger.debug(f"Confidence too low: {confidence_score:.1f}% < {confidence_threshold}%")
        if consecutive_frames < frames_threshold:
            logger.debug(f"Not enough consecutive frames: {consecutive_frames} < {frames_threshold}")
    
    return is_owl_present

# Test the confidence calculation
if __name__ == "__main__":
    # Create test detection data
    test_detection = {
        "owl_candidates": [
            {"circularity": 0.75, "aspect_ratio": 1.2, "area_ratio": 0.15, "brightness_diff": 40}
        ],
        "pixel_change": 25.0,
        "luminance_change": 35.0,
        "diff_metrics": {
            "region_metrics": {
                "top": {"mean_luminance": 10.0},
                "middle": {"mean_luminance": 25.0},
                "bottom": {"mean_luminance": 20.0}
            }
        }
    }
    
    # Create test config
    test_config = {
        "motion_detection": {
            "min_circularity": 0.5,
            "min_aspect_ratio": 0.5,
            "max_aspect_ratio": 2.0,
            "min_area_ratio": 0.1,
            "brightness_threshold": 20
        },
        "threshold_percentage": 0.05,
        "luminance_threshold": 20,
        "owl_confidence_threshold": 60,
        "consecutive_frames_threshold": 2
    }
    
    # Test confidence calculation
    confidence, history, breakdown = calculate_owl_confidence(
        test_detection, 
        "Wyze Internal Camera", 
        test_config
    )
    
    print(f"Owl Confidence: {confidence:.1f}%")
    print("Confidence Breakdown:")
    for factor, value in breakdown.items():
        print(f"  {factor}: {value}")
    
    # Test owl presence determination
    is_owl = determine_owl_presence(confidence, breakdown["consecutive_frames"], test_config)
    print(f"Owl Present: {is_owl}")