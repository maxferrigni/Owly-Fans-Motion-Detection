# File: push_to_supabase.py
# Purpose: Log owl detection data to Supabase database

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
if not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_BUCKET:
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
    owl_in_area_image_url, owl_in_area_image_comparison_url
):
    """
    Format the log entry for Supabase database.
    
    Args:
        owl_in_box (bool): Detection status for owl in box
        pixel_change_owl_in_box (float): Pixel change for box camera
        luminance_change_owl_in_box (float): Luminance change for box camera
        owl_in_box_url (str): URL of box camera image
        owl_in_box_image_comparison_url (str): URL of box camera comparison
        [... similar for other cameras ...]
    
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
        
        # Create sample log entry
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
            owl_in_area_image_comparison_url="example.com/owl_compare3.jpg"
        )
        
        push_log_to_supabase(sample_log)
        logger.info("Test complete")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise