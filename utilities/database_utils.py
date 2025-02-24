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
        # Start with base query
        query = supabase_client.table("subscribers")
        
        # Filter by notification type if provided
        if notification_type:
            query = query.eq("notification_type", notification_type)
        
        # Filter by owl location preference if provided
        if owl_location:
            query = query.ilike("owl_locations", f"%{owl_location}%")
        
        # Execute the query and return the data
        data = query.execute().data
        return data

    except Exception as e:
        logger.error(f"Error getting subscribers from Supabase: {e}")
        return