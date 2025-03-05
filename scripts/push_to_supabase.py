# File: push_to_supabase.py
# Purpose: Log owl detection data with confidence metrics to Supabase database and manage subscribers
#
# March 4, 2025 Update - Version 1.1.0
# - Updated to support new alert priority system and multiple owl detection
# - Added image URL handling for alerts
# - Enhanced logging with detailed detection information
# - Added support for after action reporting

import os
import datetime
import json
import supabase
from dotenv import load_dotenv

# Import utilities
from utilities.logging_utils import get_logger
from utilities.constants import ALERT_PRIORITIES, SUPABASE_STORAGE, get_detection_folder

# Import from database_utils
from utilities.database_utils import get_subscribers, get_table_columns, check_column_exists

# Initialize logger
logger = get_logger()

# Load environment variables from .env file
load_dotenv()

# Retrieve Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET_DETECTIONS = os.getenv("SUPABASE_BUCKET_DETECTIONS", "owl_detections")
SUPABASE_BUCKET_IMAGES = os.getenv("SUPABASE_BUCKET_IMAGES", "base_images")

# Validate credentials
if not all([SUPABASE_URL, SUPABASE_KEY]):
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
        alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area", etc.)

    Returns:
        datetime or None: Last alert time or None if no alert found
    """
    try:
        # Check if the alerts table exists and has the required columns
        if not check_column_exists("alerts", "alert_type") or not check_column_exists("alerts", "alert_sent_at"):
            logger.warning("Required columns missing in alerts table")
            return None
            
        # Fetch the last alert time for the given alert_type
        response = supabase_client.table('alerts').select('alert_sent_at').eq('alert_type', alert_type).order('alert_sent_at', desc=True).limit(1).execute()
        
        if response and hasattr(response, 'data') and len(response.data) > 0:
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
            if isinstance(last_alert_time, str):
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
        # Check if alerts table exists with required columns
        if not check_column_exists("alerts", "alert_type"):
            logger.warning("Required columns missing in alerts table")
            return None
            
        # Set priority based on alert type - Updated in v1.1.0 to use ALERT_PRIORITIES
        priority = ALERT_PRIORITIES.get(alert_type, 1)  # Default to lowest priority
        
        # Set cooldown minutes based on priority (higher priority = shorter cooldown)
        # This is configured in alert_manager.py but we need a default here
        if priority >= 5:  # Highest priority (eggs/babies or two owls in box)
            base_cooldown_minutes = 10
        elif priority >= 4:  # High priority (multiple owls)
            base_cooldown_minutes = 15
        else:  # Standard priority
            base_cooldown_minutes = 30
        
        # Calculate cooldown end time
        now = datetime.datetime.now(datetime.timezone.utc)
        cooldown_ends_at = now + datetime.timedelta(minutes=base_cooldown_minutes)
        
        # Create new alert entry - using integers for boolean values to avoid serialization issues
        alert_data = {
            'alert_type': alert_type,
            'alert_priority': priority,
            'alert_sent': 1,  # Use 1 instead of True
            'alert_sent_at': now.isoformat(),
            'base_cooldown_minutes': base_cooldown_minutes,
            'cooldown_ends_at': cooldown_ends_at.isoformat(),
            'suppressed': 0  # Use 0 instead of False
        }
        
        # Add activity log ID if provided and the column exists
        if activity_log_id and check_column_exists("alerts", "owl_activity_log_id"):
            alert_data['owl_activity_log_id'] = activity_log_id

        # Insert into Supabase
        response = supabase_client.table('alerts').insert(alert_data).execute()
        
        if response and hasattr(response, 'data') and len(response.data) > 0:
            logger.info(f"Created new alert entry for {alert_type} (priority {priority})")
            return response.data[0]
        else:
            logger.error("Failed to create alert entry in Supabase")
            return None

    except Exception as e:
        logger.error(f"Error creating alert entry: {e}")
        return None

def update_alert_status(
    alert_id,
    email_recipients_count=None,
    sms_recipients_count=None,
    previous_alert_id=None,
    priority_override=None,
    owl_confidence_score=None,
    consecutive_owl_frames=None,
    confidence_breakdown=None,
    threshold_used=None,
    comparison_image_url=None  # Added in v1.1.0
):
    """
    Update the status of an existing alert entry in Supabase.

    Args:
        alert_id (int): ID of the alert entry to update
        email_recipients_count (int, optional): Number of email notifications sent
        sms_recipients_count (int, optional): Number of SMS notifications sent
        previous_alert_id (int, optional): ID of the previous alert that was overridden
        priority_override (bool, optional): Whether this alert overrides a previous alert
        owl_confidence_score (float, optional): Confidence score for the owl detection
        consecutive_owl_frames (int, optional): Number of consecutive frames with owl detection
        confidence_breakdown (str, optional): String representation of confidence factors
        threshold_used (float, optional): Confidence threshold that was applied
        comparison_image_url (str, optional): URL to the comparison image (added in v1.1.0)
    """
    try:
        # Build update data, checking each column exists before adding it
        update_data = {}
        
        if email_recipients_count is not None and check_column_exists("alerts", "email_recipients_count"):
            update_data['email_recipients_count'] = email_recipients_count
            
        if sms_recipients_count is not None and check_column_exists("alerts", "sms_recipients_count"):
            update_data['sms_recipients_count'] = sms_recipients_count
            
        if previous_alert_id is not None and check_column_exists("alerts", "previous_alert_id"):
            update_data['previous_alert_id'] = previous_alert_id
            
        if priority_override is not None and check_column_exists("alerts", "priority_override"):
            # Use integer for boolean to avoid serialization issues
            update_data['priority_override'] = 1 if priority_override else 0
            
        if owl_confidence_score is not None and check_column_exists("alerts", "owl_confidence_score"):
            update_data['owl_confidence_score'] = owl_confidence_score
            
        if consecutive_owl_frames is not None and check_column_exists("alerts", "consecutive_owl_frames"):
            update_data['consecutive_owl_frames'] = consecutive_owl_frames
            
        if confidence_breakdown is not None and check_column_exists("alerts", "confidence_breakdown"):
            update_data['confidence_breakdown'] = confidence_breakdown
            
        if threshold_used is not None and check_column_exists("alerts", "threshold_used"):
            update_data['threshold_used'] = threshold_used
            
        # Added in v1.1.0 - Store image URL with alert
        if comparison_image_url is not None and check_column_exists("alerts", "comparison_image_url"):
            update_data['comparison_image_url'] = comparison_image_url

        # Only update if we have data
        if update_data:
            response = supabase_client.table('alerts').update(update_data).eq('id', alert_id).execute()
            if response and hasattr(response, 'data'):
                logger.info(f"Updated alert status for alert ID {alert_id}")
            else:
                logger.warning(f"Failed to update alert status for alert ID {alert_id}")
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
    # If confidence_factors is None or not a dict, return empty dict
    if not confidence_factors or not isinstance(confidence_factors, dict):
        logger.warning(f"Invalid confidence_factors format: {type(confidence_factors)}")
        return {}
    
    # Create a clean dict with only floats
    clean_factors = {}
    
    # These are the factors we want to keep
    expected_factors = [
        "shape_confidence", 
        "motion_confidence", 
        "temporal_confidence", 
        "camera_confidence"
    ]
    
    try:
        for factor in expected_factors:
            if factor in confidence_factors:
                # Ensure it's a float
                value = confidence_factors[factor]
                if isinstance(value, (int, float)):
                    clean_factors[factor] = float(value)
                else:
                    # Try to convert to float if possible
                    try:
                        clean_factors[factor] = float(value)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert {factor}={value} to float")
        
        # Validate the result is JSON serializable
        json.dumps(clean_factors)
        return clean_factors
        
    except Exception as e:
        logger.error(f"Error formatting confidence factors: {e}")
        return {}

def generate_image_url(local_image_path, alert_type, camera_name=None):
    """
    Generate a proper Supabase URL for an image based on its alert type.
    New in v1.1.0 to ensure images have correct URLs.
    
    Args:
        local_image_path (str): Path to the local image file
        alert_type (str): Type of alert/detection 
        camera_name (str, optional): Name of the camera
        
    Returns:
        str or None: Public URL to the image or None if generation failed
    """
    try:
        if not local_image_path:
            return None
            
        # Get the detection folder for this alert type
        detection_folder = get_detection_folder(alert_type)
        
        # Generate a unique filename
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        camera_part = f"{camera_name.lower().replace(' ', '_')}_" if camera_name else ""
        filename = f"{camera_part}{timestamp}.jpg"
        
        # Construct the full path within the bucket
        storage_path = f"{detection_folder}/{filename}"
        
        # Generate the public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET_DETECTIONS}/{storage_path}"
        return public_url
        
    except Exception as e:
        logger.error(f"Error generating image URL: {e}")
        return None

def push_log_to_supabase(detection_results, lighting_condition=None, base_image_age=None):
    """
    Push detection results to the owl_activity_log table in Supabase.
    Checks for duplicates to prevent multiple uploads of the same data.
    Now includes confidence metrics and image URLs.
    
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
        
        # Validate alert type is in our priority list
        if alert_type not in ALERT_PRIORITIES:
            logger.warning(f"Alert type not in priority list: {alert_type}")
            # Still continue with upload but log warning
        
        # Get table columns to check which fields to include
        table_columns = get_table_columns("owl_activity_log")
        if not table_columns:
            logger.error("owl_activity_log table not found or has no columns")
            return None
            
        # Convert alert_type to snake_case field prefix
        field_prefix = alert_type.lower().replace(" ", "_")
        
        # Prepare the basic log entry, checking each field exists before adding
        log_entry = {}

        # Add environmental context if columns exist
        if "lighting_condition" in table_columns:
            log_entry["lighting_condition"] = lighting_condition
            
        if "base_image_age_seconds" in table_columns:
            log_entry["base_image_age_seconds"] = base_image_age
        
        # Initialize owl detection flags if columns exist - Use integers instead of booleans
        for owl_location in ["owl_in_box", "owl_on_box", "owl_in_area", "two_owls", "two_owls_in_box", "eggs_or_babies"]:
            if owl_location in table_columns:
                log_entry[owl_location] = 0  # Use 0 instead of False for JSON serialization
        
        # Set the specific alert type to 1 if owl was detected and column exists
        is_owl_present = detection_results.get('is_owl_present', False)
        if field_prefix in table_columns:
            log_entry[field_prefix] = 1 if is_owl_present else 0  # Use 1/0 instead of True/False
        
        # Add metrics specific to this alert type if columns exist
        pixel_change = float(detection_results.get('pixel_change', 0.0))
        luminance_change = float(detection_results.get('luminance_change', 0.0))
        
        pixel_col = f"pixel_change_{field_prefix}"
        if pixel_col in table_columns:
            log_entry[pixel_col] = pixel_change
            
        luminance_col = f"luminance_change_{field_prefix}"
        if luminance_col in table_columns:
            log_entry[luminance_col] = luminance_change
        
        # Add image URL if available and column exists - Updated in v1.1.0
        image_url_col = f"{field_prefix}_image_comparison_url"
        comparison_path = detection_results.get('comparison_path')
        comparison_image_url = detection_results.get('comparison_image_url')
        
        # If we don't have a URL but have a local path, generate a URL
        if not comparison_image_url and comparison_path:
            comparison_image_url = generate_image_url(comparison_path, alert_type, camera_name)
            
        # Store the URL if we have it and the column exists
        if comparison_image_url and image_url_col in table_columns:
            log_entry[image_url_col] = comparison_image_url
            
        # Make sure to also store it in detection_results for future use
        if comparison_image_url:
            detection_results['comparison_image_url'] = comparison_image_url
            
        # Add multiple owl detection fields if columns exist - New in v1.1.0
        if "multiple_owls" in detection_results and "multiple_owls" in table_columns:
            log_entry["multiple_owls"] = 1 if detection_results["multiple_owls"] else 0
            
        if "owl_count" in detection_results and "owl_count" in table_columns:
            log_entry["owl_count"] = detection_results["owl_count"]
            
        # Add eggs_or_babies field if available - New in v1.1.0
        if "eggs_or_babies" in detection_results and "eggs_or_babies" in table_columns:
            log_entry["eggs_or_babies"] = 1 if detection_results["eggs_or_babies"] else 0
            
        # Add confidence metrics if columns exist
        owl_confidence = float(detection_results.get('owl_confidence', 0.0))
        consecutive_frames = int(detection_results.get('consecutive_owl_frames', 0))
        
        if "owl_confidence_score" in table_columns:
            log_entry["owl_confidence_score"] = owl_confidence
            
        if "consecutive_owl_frames" in table_columns:
            log_entry["consecutive_owl_frames"] = consecutive_frames
        
        # Add priority level if column exists - New in v1.1.0
        if "alert_priority" in table_columns:
            log_entry["alert_priority"] = ALERT_PRIORITIES.get(alert_type, 1)
        
        # Get threshold value if available and column exists
        if 'threshold_used' in detection_results and "confidence_threshold_used" in table_columns:
            log_entry["confidence_threshold_used"] = float(detection_results.get('threshold_used', 0.0))
            
        # Handle confidence factors separately if column exists
        confidence_factors = detection_results.get('confidence_factors', {})
        if confidence_factors and "confidence_factors" in table_columns:
            # Format the confidence factors to ensure they're serializable
            formatted_factors = format_confidence_factors(confidence_factors)
            
            # Convert to JSON string to ensure it's serializable
            try:
                if formatted_factors:
                    log_entry["confidence_factors"] = json.dumps(formatted_factors)
            except Exception as json_err:
                logger.error(f"Error serializing confidence factors: {json_err}")
                # Don't add this field if it can't be serialized
        
        # Only proceed if we have something to log
        if not log_entry:
            logger.warning("No valid columns to log to owl_activity_log")
            return None
            
        # Log the entry for debugging
        logger.debug(f"Prepared log entry for Supabase: {log_entry}")
        
        # Ensure everything is JSON serializable by pre-validating
        try:
            json.dumps(log_entry)
        except TypeError as e:
            # Find the problematic fields and fix them
            logger.warning(f"JSON serialization issue: {e}")
            for key, value in list(log_entry.items()):
                try:
                    json.dumps({key: value})
                except TypeError:
                    logger.warning(f"Converting non-serializable field {key} to string")
                    if isinstance(value, bool):
                        log_entry[key] = 1 if value else 0
                    else:
                        log_entry[key] = str(value)
        
        # Send to Supabase - using insert with correct method to handle all data types
        response = supabase_client.table('owl_activity_log').insert(log_entry).execute()
        
        if response and hasattr(response, 'data') and len(response.data) > 0:
            # Get the priority level for better logging
            priority_level = ALERT_PRIORITIES.get(alert_type, 1)
            logger.info(
                f"Successfully uploaded {alert_type} data to owl_activity_log "
                f"with {owl_confidence:.1f}% confidence, {consecutive_frames} consecutive frames "
                f"(Priority: {priority_level})"
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
        logger.error(f"Failed to upload log to Supabase: {e}")
        return None

def format_detection_results(detection_result):
    """
    Format detection results into a dictionary suitable for logging to Supabase.
    Updated in v1.1.0 to support multiple owls and image URLs.
    
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
        
        # Ensure numeric metrics are properly formatted
        formatted_entry = {
            "camera": camera,
            "status": status,
            "is_test": 1 if is_test else 0,  # Use integers for booleans
            "is_owl_present": 1 if is_owl_present else 0,  # Use integers for booleans
            "pixel_change": float(detection_result.get("pixel_change", 0.0)),
            "luminance_change": float(detection_result.get("luminance_change", 0.0)),
            "timestamp": detection_result.get("timestamp", datetime.datetime.now().isoformat())
        }
        
        # Add image paths if available
        if "snapshot_path" in detection_result:
            formatted_entry["snapshot_path"] = detection_result["snapshot_path"]
        if "comparison_path" in detection_result:
            formatted_entry["comparison_path"] = detection_result["comparison_path"]
        # Add image URL if available - New in v1.1.0
        if "comparison_image_url" in detection_result:
            formatted_entry["comparison_image_url"] = detection_result["comparison_image_url"]

        # Add error message if present
        if "error_message" in detection_result:
            formatted_entry["error_message"] = detection_result["error_message"]
            
        # Add confidence metrics
        formatted_entry["owl_confidence"] = float(detection_result.get("owl_confidence", 0.0))
        formatted_entry["consecutive_owl_frames"] = int(detection_result.get("consecutive_owl_frames", 0))
        
        # If threshold was used for detection, include it
        if "threshold_used" in detection_result:
            formatted_entry["threshold_used"] = float(detection_result["threshold_used"])
        
        # Format confidence factors for consistency using our dedicated function
        confidence_factors = detection_result.get("confidence_factors", {})
        formatted_entry["confidence_factors"] = format_confidence_factors(confidence_factors)
        
        # Add multiple owl detection fields if present - New in v1.1.0
        if "multiple_owls" in detection_result:
            formatted_entry["multiple_owls"] = detection_result["multiple_owls"]
            
        if "owl_count" in detection_result:
            formatted_entry["owl_count"] = detection_result["owl_count"]
            
        # Add eggs or babies detection if present - New in v1.1.0
        if "eggs_or_babies" in detection_result:
            formatted_entry["eggs_or_babies"] = detection_result["eggs_or_babies"]

        logger.debug(f"Formatted detection results: {formatted_entry}")
        return formatted_entry

    except Exception as e:
        logger.error(f"Error formatting detection results: {e}")
        return {
            "camera": detection_result.get("camera", "Unknown"),
            "status": "Error",
            "error_message": str(e),
            "is_test": 0,  # Use integers for booleans
            "owl_confidence": 0.0,
            "consecutive_owl_frames": 0,
            "confidence_factors": {}
        }

def get_alert_statistics(days=1):
    """
    Get statistics about alerts from the database for the after action report.
    New in v1.1.0 to support after action reports.
    
    Args:
        days (int): Number of days to look back
        
    Returns:
        dict: Dictionary with alert statistics
    """
    try:
        # Calculate the start time
        start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        start_time_str = start_time.isoformat()
        
        # Get column info
        table_columns = get_table_columns("owl_activity_log")
        if not table_columns:
            logger.error("Could not get columns for owl_activity_log")
            return {}
            
        # Check which alert types we can query
        alert_types = []
        for alert_type in ALERT_PRIORITIES.keys():
            field_name = alert_type.lower().replace(" ", "_")
            if field_name in table_columns:
                alert_types.append((alert_type, field_name))
        
        # Initialize statistics
        stats = {
            "period_start": start_time_str,
            "period_end": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "total_alerts": 0,
            "alerts_by_type": {},
            "average_confidence": {}
        }
        
        # Get counts for each alert type
        for alert_type, field_name in alert_types:
            try:
                # Query for count of this alert type
                query = f"select count(*) from owl_activity_log where {field_name} = 1 and created_at > '{start_time_str}'"
                response = supabase_client.rpc('execute_sql', {'query': query}).execute()
                
                if response and hasattr(response, 'data') and len(response.data) > 0:
                    count = response.data[0].get('count', 0)
                    stats["alerts_by_type"][alert_type] = count
                    stats["total_alerts"] += count
                    
                # Get average confidence if the column exists
                if "owl_confidence_score" in table_columns:
                    avg_query = f"select avg(owl_confidence_score) from owl_activity_log where {field_name} = 1 and created_at > '{start_time_str}'"
                    avg_response = supabase_client.rpc('execute_sql', {'query': avg_query}).execute()
                    
                    if avg_response and hasattr(avg_response, 'data') and len(avg_response.data) > 0:
                        avg = avg_response.data[0].get('avg', 0)
                        if avg:
                            stats["average_confidence"][alert_type] = float(avg)
                
            except Exception as e:
                logger.error(f"Error getting statistics for {alert_type}: {e}")
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting alert statistics: {e}")
        return {}

if __name__ == "__main__":
    try:
        # Basic configuration for testing
        logger.info("Testing Supabase logging functionality with confidence metrics...")

        # Test multiple owl detection
        test_detection_multiple = {
            "camera": "Test Camera",
            "status": "Two Owls In Box",
            "is_test": True,
            "is_owl_present": True,
            "multiple_owls": True,
            "owl_count": 2,
            "pixel_change": 30.5,
            "luminance_change": 35.2,
            "owl_confidence": 85.5,
            "consecutive_owl_frames": 3,
            "confidence_factors": {
                "shape_confidence": 35.0,
                "motion_confidence": 30.5,
                "temporal_confidence": 15.0,
                "camera_confidence": 5.0
            },
            "comparison_path": "/path/to/local/image.jpg"
        }
        
        # Format and test upload
        formatted_multiple = format_detection_results(test_detection_multiple)
        
        # Don't actually upload in test mode, just verify formatting
        logger.info(f"Formatted multiple owl detection: {formatted_multiple}")
        
        # Test statistics retrieval for after action report
        stats = get_alert_statistics(days=7)  # Get stats for last week
        logger.info(f"Alert statistics: {stats}")
        
        logger.info("Supabase push test complete")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise