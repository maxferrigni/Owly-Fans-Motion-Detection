# File: utilities/database_utils.py
# Purpose: Centralize database operations for the Owl Monitoring System

import os
from dotenv import load_dotenv
import supabase
from utilities.logging_utils import get_logger

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
        # Start with base query - always select first
        query = supabase_client.table("subscribers").select("*")
        
        # Filter by notification type if provided
        if notification_type:
            query = query.eq("notification_type", notification_type)
        
        # Filter by owl location preference if provided
        if owl_location:
            query = query.ilike("owl_locations", f"%{owl_location}%")
        
        # Execute the query
        response = query.execute()
        
        # Check if response has data and return
        if hasattr(response, 'data'):
            logger.info(f"Found {len(response.data)} subscribers for {notification_type} notifications")
            return response.data
        else:
            logger.warning("No data attribute in Supabase response")
            return []

    except Exception as e:
        logger.error(f"Error getting subscribers from Supabase: {e}")
        # Return empty list instead of None to avoid NoneType errors
        return []

def get_owl_activity_logs(limit=10, camera_name=None):
    """
    Get recent owl activity logs.
    
    Args:
        limit (int): Maximum number of logs to retrieve
        camera_name (str, optional): Filter by specific camera
        
    Returns:
        list: List of activity log records
    """
    try:
        # Start with base query - always select first
        query = supabase_client.table("owl_activity_log").select("*")
        
        # Filter by camera if provided
        if camera_name:
            query = query.eq("camera", camera_name)
        
        # Order by timestamp descending and limit results
        query = query.order("created_at", desc=True).limit(limit)
        
        # Execute query
        response = query.execute()
        
        # Check if response has data
        if hasattr(response, 'data'):
            return response.data
        else:
            logger.warning("No data attribute in Supabase response")
            return []
            
    except Exception as e:
        logger.error(f"Error getting owl activity logs: {e}")
        return []

def save_custom_threshold(camera_name, threshold_value):
    """
    Save a custom confidence threshold for a specific camera.
    
    Args:
        camera_name (str): Name of the camera
        threshold_value (float): The confidence threshold value
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if a record exists for this camera
        query = supabase_client.table("camera_settings").select("*").eq("camera_name", camera_name)
        response = query.execute()
        
        if hasattr(response, 'data') and len(response.data) > 0:
            # Update existing record
            update_data = {
                "owl_confidence_threshold": threshold_value,
                "last_updated": "now()"
            }
            
            supabase_client.table("camera_settings").update(update_data).eq("camera_name", camera_name).execute()
            logger.info(f"Updated confidence threshold for {camera_name} to {threshold_value}%")
        else:
            # Insert new record
            insert_data = {
                "camera_name": camera_name,
                "owl_confidence_threshold": threshold_value,
                "created_at": "now()",
                "last_updated": "now()"
            }
            
            supabase_client.table("camera_settings").insert(insert_data).execute()
            logger.info(f"Created new confidence threshold for {camera_name}: {threshold_value}%")
            
        return True
        
    except Exception as e:
        logger.error(f"Error saving custom threshold for {camera_name}: {e}")
        return False

def get_custom_thresholds():
    """
    Get all custom confidence thresholds stored in the database.
    
    Returns:
        dict: Camera name to threshold value mapping
    """
    try:
        # Query camera settings table
        response = supabase_client.table("camera_settings").select("*").execute()
        
        # Process results
        thresholds = {}
        if hasattr(response, 'data'):
            for row in response.data:
                if "camera_name" in row and "owl_confidence_threshold" in row:
                    thresholds[row["camera_name"]] = row["owl_confidence_threshold"]
                    
        return thresholds
        
    except Exception as e:
        logger.error(f"Error getting custom thresholds: {e}")
        return {}