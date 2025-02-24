# File: utilities/push_to_supabase.py
# Purpose: Log owl detection data to Supabase database and manage subscribers

import os
import datetime
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
    priority_override=None
):
    """
    Update the status of an existing alert entry in Supabase.

    Args:
        alert_id (int): ID of the alert entry to update
        email_count (int, optional): Number of email notifications sent
        sms_count (int, optional): Number of SMS notifications sent
        previous_alert_id (int, optional): ID of the previous alert that was overridden
        priority_override (bool, optional): Whether this alert overrides a previous alert
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

        # Only update if we have data
        if update_data:
            supabase_client.table('alerts').update(update_data).eq('id', alert_id).execute()
            logger.info(f"Updated alert status for alert ID {alert_id}")
        else:
            logger.warning(f"No data provided to update alert ID {alert_id}")

    except Exception as e:
        logger.error(f"Error updating alert status: {e}")

def push_log_to_supabase(detection_results, lighting_condition=None, base_image_age=None):
    """
    Push detection results to the owl_activity_log table in Supabase.
    
    Args:
        detection_results (dict): Dictionary containing detection results
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

        # Get status (alert type) and validate
        alert_type = detection_results.get('status')
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
            
            # Initialize all boolean flags to false
            "owl_in_box": False,
            "owl_on_box": False,
            "owl_in_area": False
        }
        
        # Set the specific alert type to true if motion was detected
        motion_detected = detection_results.get('motion_detected', False)
        if field_prefix == "owl_in_box":
            log_entry["owl_in_box"] = motion_detected
        elif field_prefix == "owl_on_box":
            log_entry["owl_on_box"] = motion_detected
        elif field_prefix == "owl_in_area":
            log_entry["owl_in_area"] = motion_detected
        
        # Add metrics specific to this alert type
        pixel_change = float(detection_results.get('pixel_change', 0.0))
        luminance_change = float(detection_results.get('luminance_change', 0.0))
        
        log_entry[f"pixel_change_{field_prefix}"] = pixel_change
        log_entry[f"luminance_change_{field_prefix}"] = luminance_change
        
        # Add image URL if available
        if 'comparison_path' in detection_results:
            log_entry[f"{field_prefix}_image_comparison_url"] = detection_results['comparison_path']
        
        # Log the entry for debugging
        logger.debug(f"Prepared log entry for Supabase: {log_entry}")
        
        # Send to Supabase
        response = supabase_client.table('owl_activity_log').insert(log_entry).execute()
        
        if response.data and len(response.data) > 0:
            logger.info(f"Successfully uploaded {alert_type} data to owl_activity_log")
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
        motion_detected = detection_result.get("motion_detected", False)
        
        # Ensure numeric metrics are properly formatted
        formatted_entry = {
            "camera": camera,
            "status": status,
            "is_test": is_test,
            "motion_detected": motion_detected,
            "pixel_change": float(detection_result.get("pixel_change", 0.0)),
            "luminance_change": float(detection_result.get("luminance_change", 0.0))
        }
        
        # Add image paths if available
        if "snapshot_path" in detection_result:
            formatted_entry["snapshot_path"] = detection_result["snapshot_path"]
        if "comparison_path" in detection_result:
            formatted_entry["comparison_path"] = detection_result["comparison_path"]

        # Add error message if present
        if "error_message" in detection_result:
            formatted_entry["error_message"] = detection_result["error_message"]

        logger.debug(f"Formatted detection results: {formatted_entry}")
        return formatted_entry

    except Exception as e:
        logger.error(f"Error formatting detection results: {e}")
        return {
            "camera": detection_result.get("camera", "Unknown"),
            "status": "Error",
            "error_message": str(e),
            "is_test": detection_result.get("is_test", False)
        }

if __name__ == "__main__":
    # Test the functionality
    try:
        logger.info("Testing Supabase logging functionality...")

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

        # Test log upload with test data
        test_detection = {
            "camera": "Test Camera",
            "status": "Owl In Box",
            "is_test": True,
            "motion_detected": True,
            "pixel_change": 25.5,
            "luminance_change": 30.2,
            "comparison_path": "https://example.com/test-comparison.jpg"
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
        else:
            logger.error("Failed to create test log entry")

        logger.info("Supabase logging test complete")

    except Exception as e:
        logger.error(f"Supabase logging test failed: {e}")
        raise