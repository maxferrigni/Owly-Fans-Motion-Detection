# File: push_to_supabase.py
# Purpose: Log owl detection data with confidence metrics to Supabase database and manage subscribers

import os
import datetime
import json
import supabase
from dotenv import load_dotenv

# Import utilities
from utilities.logging_utils import get_logger

# Import from database_utils
from utilities.database_utils import get_subscribers

# Initialize logger
logger = get_logger()

# Load environment variables from .env file
load_dotenv()

# Retrieve Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")

# Validate credentials
if not all([SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET]):
    error_msg = "Supabase credentials are missing. Check the .env file."
    logger.error(error_msg)
    raise ValueError(error_msg)

# Initialize Supabase client
try:
    supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {e}")
    raise

# Track uploaded entries to prevent duplicates
last_uploaded_entries = {}

def get_last_alert_time(alert_type):
    """
    Retrieve the last time a specific alert was sent from Supabase.

    Args:
        alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area")

    Returns:
        datetime or None: Last alert time or None if no alert found
    """
    try:
        # Fetch the last alert time for the given alert_type
        response = supabase_client.table('alerts') \
                                 .select('alert_sent_at') \
                                 .eq('alert_type', alert_type) \
                                 .order('alert_sent_at', desc=True) \
                                 .limit(1) \
                                 .execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]['alert_sent_at']
        else:
            return None

    except Exception as e:
        logger.error(f"Error getting last alert time: {e}")
        return None

def check_alert_eligibility(alert_type, cooldown_minutes):
    """
    Check if enough time has passed since the last alert of the specified type.

    Args:
        alert_type (str): Type of alert
        cooldown_minutes (int): Cooldown period in minutes

    Returns:
        tuple: (bool, dict or None) - (is_eligible, last_alert_data)
    """
    try:
        last_alert_time = get_last_alert_time(alert_type)
        if last_alert_time:
            # Ensure the timestamp has timezone information
            if 'Z' in last_alert_time or '+' in last_alert_time:
                # ISO format with timezone
                last_alert_time = datetime.datetime.fromisoformat(last_alert_time.replace('Z', '+00:00'))
            else:
                # Assume UTC if no timezone info
                last_alert_time = datetime.datetime.fromisoformat(last_alert_time)
                last_alert_time = last_alert_time.replace(tzinfo=datetime.timezone.utc)
            
            # Always use timezone-aware now
            now = datetime.datetime.now(datetime.timezone.utc)
            
            # Calculate time difference and check against cooldown
            time_diff = now - last_alert_time
            if time_diff < datetime.timedelta(minutes=cooldown_minutes):
                return False, {'last_alert_time': last_alert_time}
            else:
                return True, {'last_alert_time': last_alert_time}
        else:
            return True, None

    except Exception as e:
        logger.error(f"Error checking alert eligibility: {e}")
        return False, None

def create_alert_entry(alert_type, activity_log_id=None):
    """
    Create a new alert entry in Supabase.

    Args:
        alert_type (str): Type of alert
        activity_log_id (int, optional): ID of the related activity log entry

    Returns:
        dict or None: The created alert entry or None if creation failed
    """
    try:
        # Set priority based on alert type
        priority_map = {
            "Owl In Box": 3,
            "Owl On Box": 2,
            "Owl In Area": 1
        }
        
        # Set default cooldown minutes
        base_cooldown_minutes = 30
        
        # Calculate cooldown end time
        now = datetime.datetime.now(datetime.timezone.utc)
        cooldown_ends_at = now + datetime.timedelta(minutes=base_cooldown_minutes)
        
        # Create new alert entry
        alert_data = {
            'alert_type': alert_type,
            'alert_priority': priority_map.get(alert_type, 1),
            'alert_sent': True,
            'alert_sent_at': now.isoformat(),
            'base_cooldown_minutes': base_cooldown_minutes,
            'cooldown_ends_at': cooldown_ends_at.isoformat(),
            'suppressed': False
        }
        
        # Add activity log ID if provided
        if activity_log_id:
            alert_data['owl_activity_log_id'] = activity_log_id

        # Insert into Supabase
        response = supabase_client.table('alerts').insert(alert_data).execute()
        
        if response.data and len(response.data) > 0:
            logger.info(f"Created new alert entry for {alert_type}")
            return response.data[0]
        else:
            logger.error("Failed to create alert entry in Supabase")
            return None

    except Exception as e:
        logger.error(f"Error creating alert entry: {e}")
        return None

def update_alert_status(
    alert_id,
    email_count=None,
    sms_count=None,
    previous_alert_id=None,
    priority_override=None,
    owl_confidence_score=None,
    consecutive_owl_frames=None,
    confidence_breakdown=None,
    threshold_used=None
):
    """
    Update the status of an existing alert entry in Supabase.

    Args:
        alert_id (int): ID of the alert entry to update
        email_count (int, optional): Number of email notifications sent
        sms_count (int, optional): Number of SMS notifications sent
        previous_alert_id (int, optional): ID of the previous alert that was overridden
        priority_override (bool, optional): Whether this alert overrides a previous alert
        owl_confidence_score (float, optional): Confidence score for the owl detection
        consecutive_owl_frames (int, optional): Number of consecutive frames with owl detection
        confidence_breakdown (str, optional): String representation of confidence factors
        threshold_used (float, optional): Confidence threshold that was applied
    """
    try:
        # Build update data
        update_data = {}
        
        if email_count is not None:
            update_data['email_recipients_count'] = email_count
        if sms_count is not None:
            update_data['sms_recipients_count'] = sms_count
        if previous_alert_id is not None:
            update_data['previous_alert_id'] = previous_alert_id
        if priority_override is not None:
            update_data['priority_override'] = priority_override
        if owl_confidence_score is not None:
            update_data['owl_confidence_score'] = owl_confidence_score
        if consecutive_owl_frames is not None:
            update_data['consecutive_owl_frames'] = consecutive_owl_frames
        if confidence_breakdown is not None:
            update_data['confidence_breakdown'] = confidence_breakdown
        if threshold_used is not None:
            update_data['threshold_used'] = threshold_used

        # Only update if we have data
        if update_data:
            supabase_client.table('alerts').update(update_data).eq('id', alert_id).execute()
            logger.info(f"Updated alert status for alert ID {alert_id}")
        else:
            logger.warning(f"No data provided to update alert ID {alert_id}")

    except Exception as e:
        logger.error(f"Error updating alert status: {e}")

def format_confidence_factors(confidence_factors):
    """
    Format confidence factors to ensure they can be properly serialized to JSON.
    Extracts only the numeric values we care about.
    
    Args:
        confidence_factors (dict): Raw confidence factors
        
    Returns:
        dict: Cleaned confidence factors with only serializable values
    """
    try:
        # Return early if no confidence factors
        if not confidence_factors:
            return {}
        
        # Create a new dictionary with only numeric values
        clean_factors = {}
        
        # These are the factors we want to keep
        expected_factors = [
            "shape_confidence", 
            "motion_confidence", 
            "temporal_confidence", 
            "camera_confidence"
        ]
        
        for factor in expected_factors:
            if factor in confidence_factors:
                # Ensure it's a float (prevents serialization issues)
                clean_factors[factor] = float(confidence_factors[factor])
        
        return clean_factors
    except Exception as e:
        logger.error(f"Error formatting confidence factors: {e}")
        return {}  # Return empty dict on error to prevent issues down the line

def push_log_to_supabase(detection_results, lighting_condition=None, base_image_age=None):
    """
    Push detection results to the owl_activity_log table in Supabase.
    Checks for duplicates to prevent multiple uploads of the same data.
    Now includes confidence metrics.
    
    Args:
        detection_results (dict): Dictionary containing detection results with confidence
        lighting_condition (str, optional): Current lighting condition
        base_image_age (int, optional): Age of base image in seconds
        
    Returns:
        dict: The created log entry or None if failed
    """
    try:
        # Validate detection results
        if 'camera' not in detection_results or 'status' not in detection_results:
            logger.error("Missing required camera or status field in detection results")
            return None

        # Get camera and status
        camera_name = detection_results.get('camera')
        alert_type = detection_results.get('status')
        timestamp = detection_results.get('timestamp')
        
        # Check if we've already uploaded this entry
        entry_key = f"{camera_name}_{alert_type}_{timestamp}"
        if entry_key in last_uploaded_entries:
            logger.debug(f"Skipping duplicate upload for {entry_key}")
            return last_uploaded_entries[entry_key]
        
        # Validate alert type
        if alert_type not in ["Owl In Box", "Owl On Box", "Owl In Area"]:
            logger.error(f"Invalid alert type: {alert_type}")
            return None
            
        # Convert alert_type to snake_case field prefix
        field_prefix = alert_type.lower().replace(" ", "_")
        
        # Prepare the basic log entry
        log_entry = {
            # Environmental context
            "lighting_condition": lighting_condition,
            "base_image_age_seconds": base_image_age,
            
            # Initialize all boolean flags to false - specifically using Python booleans
            "owl_in_box": False,
            "owl_on_box": False,
            "owl_in_area": False
        }
        
        # Set the specific alert type to true if owl was detected
        is_owl_present = detection_results.get('is_owl_present', False)
        if field_prefix == "owl_in_box":
            log_entry["owl_in_box"] = is_owl_present
        elif field_prefix == "owl_on_box":
            log_entry["owl_on_box"] = is_owl_present
        elif field_prefix == "owl_in_area":
            log_entry["owl_in_area"] = is_owl_present
        
        # Add metrics specific to this alert type
        pixel_change = float(detection_results.get('pixel_change', 0.0))
        luminance_change = float(detection_results.get('luminance_change', 0.0))
        
        log_entry[f"pixel_change_{field_prefix}"] = pixel_change
        log_entry[f"luminance_change_{field_prefix}"] = luminance_change
        
        # Add image URL if available
        if 'comparison_path' in detection_results:
            log_entry[f"{field_prefix}_image_comparison_url"] = detection_results['comparison_path']
            
        # Add confidence metrics
        owl_confidence = float(detection_results.get('owl_confidence', 0.0))
        consecutive_frames = int(detection_results.get('consecutive_owl_frames', 0))
        threshold_used = float(detection_results.get('threshold_used', 60.0))
        
        # Add confidence metrics to log entry
        log_entry["owl_confidence_score"] = owl_confidence
        log_entry["consecutive_owl_frames"] = consecutive_frames
        log_entry["threshold_used"] = threshold_used
        
        # Handle confidence factors properly for JSONB storage
        confidence_factors = detection_results.get('confidence_factors', {})
        if confidence_factors:
            # Clean and format the confidence factors to ensure they're serializable
            formatted_factors = format_confidence_factors(confidence_factors)
            
            # Store as properly formatted JSON
            log_entry["confidence_factors"] = formatted_factors
        
        # Log the entry for debugging
        logger.debug(f"Prepared log entry for Supabase: {log_entry}")
        
        # Send to Supabase - explicitly using insert to handle nested structures
        response = supabase_client.table('owl_activity_log').insert(log_entry).execute()
        
        if response.data and len(response.data) > 0:
            logger.info(
                f"Successfully uploaded {alert_type} data to owl_activity_log "
                f"with {owl_confidence:.1f}% confidence, {consecutive_frames} consecutive frames"
            )
            # Store this entry to prevent duplicates
            last_uploaded_entries[entry_key] = response.data[0]
            # Keep only the last 100 entries to prevent memory growth
            if len(last_uploaded_entries) > 100:
                # Remove oldest entries
                keys_to_remove = list(last_uploaded_entries.keys())[:-100]
                for key in keys_to_remove:
                    del last_uploaded_entries[key]
            return response.data[0]
        else:
            logger.error("Failed to insert into owl_activity_log")
            return None

    except Exception as e:
        logger.error(f"Failed to upload log to Supabase: {str(e)}")
        return None

def format_detection_results(detection_result):
    """
    Format detection results into a dictionary suitable for logging to Supabase.
    Now includes confidence metrics.
    
    Args:
        detection_result (dict): Dictionary containing detection results
        
    Returns:
        dict: Formatted log entry
    """
    try:
        # Extract required fields
        camera = detection_result.get("camera")
        status = detection_result.get("status", "Unknown")
        is_test = detection_result.get("is_test", False)
        is_owl_present = detection_result.get("is_owl_present", False)
        
        # Ensure numeric metrics are properly formatted as floats
        formatted_entry = {
            "camera": camera,
            "status": status,
            "is_test": is_test,
            "is_owl_present": is_owl_present,
            "pixel_change": float(detection_result.get("pixel_change", 0.0)),
            "luminance_change": float(detection_result.get("luminance_change", 0.0)),
            "timestamp": detection_result.get("timestamp"),  # Preserve timestamp
            "threshold_used": float(detection_result.get("threshold_used", 60.0))  # Add threshold that was used
        }
        
        # Add image paths if available
        if "snapshot_path" in detection_result:
            formatted_entry["snapshot_path"] = detection_result["snapshot_path"]
        if "comparison_path" in detection_result:
            formatted_entry["comparison_path"] = detection_result["comparison_path"]

        # Add error message if present
        if "error_message" in detection_result:
            formatted_entry["error_message"] = detection_result["error_message"]
            
        # Add confidence metrics, ensuring they are floats
        formatted_entry["owl_confidence"] = float(detection_result.get("owl_confidence", 0.0))
        formatted_entry["consecutive_owl_frames"] = int(detection_result.get("consecutive_owl_frames", 0))
        
        # Format confidence factors for consistency and proper serialization
        confidence_factors = detection_result.get("confidence_factors", {})
        formatted_entry["confidence_factors"] = format_confidence_factors(confidence_factors)

        logger.debug(f"Formatted detection results: {formatted_entry}")
        return formatted_entry

    except Exception as e:
        logger.error(f"Error formatting detection results: {e}")
        return {
            "camera": detection_result.get("camera", "Unknown"),
            "status": "Error",
            "error_message": str(e),
            "is_test": detection_result.get("is_test", False),
            "owl_confidence": 0.0,
            "consecutive_owl_frames": 0,
            "confidence_factors": {},
            "threshold_used": 60.0  # Default threshold
        }

if __name__ == "__main__":
    # Test the functionality
    try:
        logger.info("Testing Supabase logging functionality with confidence metrics...")

        # Test get_subscribers
        email_subscribers = get_subscribers(notification_type="email")
        logger.info(f"Found {len(email_subscribers)} email subscribers")

        sms_subscribers = get_subscribers(notification_type="sms")
        logger.info(f"Found {len(sms_subscribers)} SMS subscribers")

        # Test last alert time retrieval
        last_alert = get_last_alert_time("Owl In Box")
        if last_alert:
            logger.info(f"Last Owl In Box alert was sent at: {last_alert}")
        else:
            logger.info("No previous Owl In Box alerts found")

        # Test log upload with test data and confidence metrics
        test_detection = {
            "camera": "Test Camera",
            "status": "Owl In Box",
            "is_test": True,
            "is_owl_present": True,
            "motion_detected": True,
            "pixel_change": 25.5,
            "luminance_change": 30.2,
            "comparison_path": "https://example.com/test-comparison.jpg",
            "owl_confidence": 78.5,
            "consecutive_owl_frames": 3,
            "threshold_used": 60.0,
            "confidence_factors": {
                "shape_confidence": 35.0,
                "motion_confidence": 25.5,
                "temporal_confidence": 15.0,
                "camera_confidence": 3.0,
                "is_valid": True  # Boolean for testing
            }
        }

        # Format and send test data
        formatted_results = format_detection_results(test_detection)
        log_entry = push_log_to_supabase(
            formatted_results,
            lighting_condition="day",
            base_image_age=300
        )

        if log_entry:
            logger.info("Test log entry created successfully")
            logger.info(f"Log entry ID: {log_entry.get('id')}")
            logger.info(f"Confidence score: {log_entry.get('owl_confidence_score', 0.0)}")
            logger.info(f"Consecutive frames: {log_entry.get('consecutive_owl_frames', 0)}")
            
            # Test update_alert_status
            test_alert = create_alert_entry("Owl In Box", log_entry.get('id'))
            if test_alert:
                update_alert_status(
                    test_alert.get('id'),
                    owl_confidence_score=78.5,
                    consecutive_owl_frames=3,
                    confidence_breakdown="shape: 35.0%, motion: 25.5%, temporal: 15.0%, camera: 3.0%",
                    threshold_used=60.0
                )
                logger.info("Alert status updated successfully")
        else:
            logger.error("Failed to create test log entry")

        logger.info("Supabase logging test with confidence metrics complete")

    except Exception as e:
        logger.error(f"Supabase logging test failed: {e}")
        raise