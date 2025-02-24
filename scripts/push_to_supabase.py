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

# Load environment variables from.env file
load_dotenv()

# Retrieve Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")

# Validate credentials
if not all([SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET]):
    error_msg = "Supabase credentials are missing. Check the.env file."
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
        last_alert = supabase_client.table('alerts') \
                                 .select('last_alert_time') \
                                 .eq('alert_type', alert_type) \
                                 .order('last_alert_time', desc=True) \
                                 .limit(1) \
                                 .execute().data

        # If an alert is found, return the last_alert_time
        if last_alert:
            return last_alert[0]['last_alert_time']
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
            last_alert_time = datetime.datetime.fromisoformat(last_alert_time)
            
            # Calculate time difference and check against cooldown
            time_diff = datetime.datetime.now(datetime.timezone.utc) - last_alert_time
            if time_diff < datetime.timedelta(minutes=cooldown_minutes):
                return False, {'last_alert_time': last_alert_time}
            else:
                return True, {'last_alert_time': last_alert_time}
        else:
            return True, None

    except Exception as e:
        logger.error(f"Error checking alert eligibility: {e}")
        return False, None

def create_alert_entry(alert_type, camera_name=None, activity_log_id=None):
    """
    Create a new alert entry in Supabase.

    Args:
        alert_type (str): Type of alert
        camera_name (str, optional): Name of the camera that triggered the alert
        activity_log_id (int, optional): ID of the related activity log entry

    Returns:
        dict or None: The created alert entry or None if creation failed
    """
    try:
        # Create a new alert entry in the alerts table
        new_alert = supabase_client.table('alerts').insert({
            'alert_type': alert_type,
            'camera_name': camera_name,
            'activity_log_id': activity_log_id,
            'last_alert_time': datetime.datetime.now(datetime.timezone.utc).isoformat()
        }).execute().data

        if new_alert:
            logger.info(f"Created new alert entry for {alert_type} (ID: {new_alert[0]['id']})")
            return new_alert[0]
        else:
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
        # Update the alert entry with additional information
        supabase_client.table('alerts').update({
            'email_count': email_count,
            'sms_count': sms_count,
            'previous_alert_id': previous_alert_id,
            'priority_override': priority_override
        }).eq('id', alert_id).execute()

        logger.info(f"Updated alert status for alert ID {alert_id}")

    except Exception as e:
        logger.error(f"Error updating alert status: {e}")

def push_log_to_supabase(detection_results, lighting_condition=None, base_image_age=None):
    """
    Push a log entry to the Supabase database.
    
    Args:
        detection_results (dict): Dictionary containing detection results
        lighting_condition (str, optional): Current lighting condition
        base_image_age (int, optional): Age of base image in seconds
        
    Returns:
        dict: The created log entry or None if failed
    """
    try:
        # Create timestamp in UTC
        timestamp = datetime.datetime.now(datetime.timezone.utc)

        # Format the log entry
        log_entry = {
            "timestamp": timestamp.isoformat(),
            "lighting_condition": lighting_condition,
            "base_image_age": base_image_age
        }

        # Add detection metrics if available
        if isinstance(detection_results, dict):
            log_entry.update({
                "camera_name": detection_results.get("camera"),
                "alert_type": detection_results.get("status"),
                "pixel_change": detection_results.get("pixel_change", 0.0),
                "luminance_change": detection_results.get("luminance_change", 0.0),
                "is_test": detection_results.get("is_test", False),
                "error_message": detection_results.get("error_message")
            })

            # Add detection images if available
            if "snapshot_path" in detection_results:
                log_entry["image_url"] = detection_results["snapshot_path"]
            if "comparison_path" in detection_results:
                log_entry["comparison_url"] = detection_results["comparison_path"]

        # Insert the log entry into the activity_log table
        response = supabase_client.table('activity_log').insert(log_entry).execute()
        
        if hasattr(response, 'data') and response.data:
            logger.info("Successfully uploaded log to Supabase")
            return response.data[0]
        else:
            logger.error("Failed to get response data from Supabase")
            return None

    except Exception as e:
        logger.error(f"Failed to upload log to Supabase: {e}")
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
        # Extract relevant information from the detection result
        camera_name = detection_result.get("camera")
        status = detection_result.get("status")
        error_message = detection_result.get("error_message")
        is_test = detection_result.get("is_test", False)
        
        # Create the log entry dictionary
        log_entry = {
            "camera": camera_name,
            "status": status,
            "error_message": error_message,
            "is_test": is_test,
            "pixel_change": detection_result.get("pixel_change", 0.0),
            "luminance_change": detection_result.get("luminance_change", 0.0),
            "snapshot_path": detection_result.get("snapshot_path", ""),
            "comparison_path": detection_result.get("comparison_path", "")
        }

        return log_entry

    except Exception as e:
        logger.error(f"Error formatting log entry: {e}")
        return {}

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
            "pixel_change": 25.5,
            "luminance_change": 30.2
        }

        # Test the new log push function
        log_entry = push_log_to_supabase(
            test_detection,
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