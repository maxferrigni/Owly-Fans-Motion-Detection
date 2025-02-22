# File: push_to_supabase.py
# Purpose: Log owl detection data to Supabase database and manage subscribers

import os
import datetime
import supabase
from dotenv import load_dotenv

# Import utilities
from utilities.logging_utils import get_logger

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

def get_subscribers(notification_type=None, owl_location=None):
    """
    Get subscribers based on notification type and preferences.
    
    Args:
        notification_type (str, optional): Type of notification ("email" or "sms")
        owl_location (str, optional): Type of owl detection for filtering
        
    Returns:
        list: List of subscriber records
    """
    try:
        # Start with base query
        query = supabase_client.table("subscribers")
        
        # Filter based on notification type and valid contact info
        if notification_type == "sms":
            query = query.filter("sms_alerts", "eq", True).filter("phone", "neq", None)
        elif notification_type == "email":
            query = supabase_client.table("subscribers").select("*").filter("email_alerts", "eq", True).filter("email", "neq", None)
        
        # Execute query
        response = query.execute()
        
        if not hasattr(response, 'data'):
            logger.error("Failed to retrieve subscribers")
            return []
            
        subscribers = response.data
        logger.info(f"Retrieved {len(subscribers)} {notification_type} subscribers")
        return subscribers

    except Exception as e:
        logger.error(f"Error retrieving subscribers: {e}")
        return []

def get_last_alert_time(alert_type):
    """
    Get the timestamp of the last alert sent for a specific type.
    
    Args:
        alert_type (str): Type of alert to check ("Owl In Box", "Owl On Box", "Owl In Area")
        
    Returns:
        datetime or None: Timestamp of last alert or None if no previous alert
    """
    try:
        # Build query based on alert type
        query = supabase_client.table("owl_activity_log").select("created_at")
        
        if alert_type == "Owl In Box":
            query = supabase_client.table("alerts").select("*").filter("owl_in_box", "eq", True)
        elif alert_type == "Owl On Box":
            query = supabase_client.table("alerts").select("*").filter("owl_on_box", "eq", True)
        else:  # Owl In Area
            query = supabase_client.table("alerts").select("*").filter("owl_in_area", "eq", True)

        # Ensure we're filtering only alerts that have been sent
        query = query.filter("alert_sent", "eq", True)

        # Order results by `created_at` descending and get the most recent one
        query = query.order("created_at", desc=True).limit(1)

        # Execute the query and catch errors
        response = query.execute()

        if "error" in response:
            print(f"Supabase Query Error: {response['error']}")

        
        if response.data and len(response.data) > 0:
            return datetime.datetime.fromisoformat(response.data[0]['created_at'].replace('Z', '+00:00'))
        return None
        
    except Exception as e:
        logger.error(f"Error getting last alert time: {e}")
        return None

def push_log_to_supabase(log_data):
    """
    Push motion detection logs to Supabase database.
    
    Args:
        log_data (dict): Detection log data to be uploaded
    """
    try:
        if not log_data:
            logger.error("Attempted to push empty log entry")
            return
        
        logger.debug(f"Pushing log entry to Supabase: {log_data}")
        response = supabase_client.table("owl_activity_log").insert(log_data).execute()

        if hasattr(response, 'data') and response.data:
            logger.info("Successfully uploaded log to Supabase")
            logger.debug(f"Supabase response: {response.data}")
        elif hasattr(response, 'error') and response.error:
            logger.error(f"Failed to upload log. Error: {response.error}")
        else:
            logger.error(f"Unexpected API response: {response}")

    except Exception as e:
        logger.error(f"Error uploading log to Supabase: {e}")

def format_log_entry(
    owl_in_box, pixel_change_owl_in_box, luminance_change_owl_in_box, 
    owl_in_box_url, owl_in_box_image_comparison_url,
    owl_on_box, pixel_change_owl_on_box, luminance_change_owl_on_box, 
    owl_on_box_image_url, owl_on_box_image_comparison_url,
    owl_in_area, pixel_change_owl_in_area, luminance_change_owl_in_area, 
    owl_in_area_image_url, owl_in_area_image_comparison_url,
    alert_sent=False
):
    """
    Format the log entry for Supabase database.
    
    Returns:
        dict: Formatted log entry
    """
    try:
        log_entry = {
            "created_at": datetime.datetime.utcnow().isoformat(),
            "owl_in_box": owl_in_box,
            "pixel_change_owl_in_box": pixel_change_owl_in_box,
            "luminance_change_owl_in_box": luminance_change_owl_in_box,
            "owl_in_box_url": owl_in_box_url,
            "owl_in_box_image_comparison_url": owl_in_box_image_comparison_url,
            
            "owl_on_box": owl_on_box,
            "pixel_change_owl_on_box": pixel_change_owl_on_box,
            "luminance_change_owl_on_box": luminance_change_owl_on_box,
            "owl_on_box_image_url": owl_on_box_image_url,
            "owl_on_box_image_comparison_url": owl_on_box_image_comparison_url,
            
            "owl_in_area": owl_in_area,
            "pixel_change_owl_in_area": pixel_change_owl_in_area,
            "luminance_change_owl_in_area": luminance_change_owl_in_area,
            "owl_in_area_image_url": owl_in_area_image_url,
            "owl_in_area_image_comparison_url": owl_in_area_image_comparison_url,
            
            "alert_sent": alert_sent
        }
        
        logger.debug(f"Formatted log entry: {log_entry}")
        return log_entry
        
    except Exception as e:
        logger.error(f"Error formatting log entry: {e}")
        raise

# Example usage and testing
if __name__ == "__main__":
    try:
        logger.info("Testing Supabase connection...")
        
        # Test subscriber retrieval for both notification types
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
        
        # Test log upload with alert tracking
        sample_log = format_log_entry(
            owl_in_box=True, pixel_change_owl_in_box=5.2, 
            luminance_change_owl_in_box=12.3, 
            owl_in_box_url="example.com/owl1.jpg", 
            owl_in_box_image_comparison_url="example.com/owl_compare1.jpg",
            
            owl_on_box=False, pixel_change_owl_on_box=0.0, 
            luminance_change_owl_on_box=0.0, 
            owl_on_box_image_url="", 
            owl_on_box_image_comparison_url="",
            
            owl_in_area=True, pixel_change_owl_in_area=7.5, 
            luminance_change_owl_in_area=10.2, 
            owl_in_area_image_url="example.com/owl3.jpg", 
            owl_in_area_image_comparison_url="example.com/owl_compare3.jpg",
            
            alert_sent=True
        )
        
        push_log_to_supabase(sample_log)
        logger.info("Test complete")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise