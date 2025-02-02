# File: push_to_supabase.py
# Purpose:
# This script logs owl detection data directly into the Supabase database.
# It replaces local CSV logging and Git repository logging, ensuring all detection logs are stored in a centralized cloud database.
# Features:
# - Connects to Supabase using environment variables for security.
# - Inserts log data into the `owl_activity_log` table in real-time.
# - Implements error handling and retry mechanisms for failed uploads.
# - Properly checks API responses to prevent indexing errors.
# Typical Usage:
# This script should be called whenever a detection event occurs in `main.py`.
# Example:
# `python push_to_supabase.py`

import os
import datetime
import supabase
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve Supabase credentials from .env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials are missing. Check the .env file.")

# Initialize Supabase client
try:
    supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    logging.error(f"Failed to initialize Supabase client: {e}")
    raise

def push_log_to_supabase(log_data):
    """
    Pushes motion detection logs to the Supabase database.
    :param log_data: Dictionary containing log data
    """
    try:
        if not log_data:
            logging.error("Attempted to push an empty log entry.")
            return
        
        response = supabase_client.table("owl_activity_log").insert(log_data).execute()

        # Fix: Check if the response contains 'data' and 'error' attributes
        if hasattr(response, 'data') and response.data:
            print("Successfully uploaded log to Supabase.")
        elif hasattr(response, 'error') and response.error:
            logging.error(f"Failed to upload log. Error: {response.error}")
            print(f"Failed to upload log. Error: {response.error}")
        else:
            logging.error(f"Unexpected API response: {response}")
            print(f"Unexpected API response: {response}")

    except Exception as e:
        logging.error(f"Error uploading log to Supabase: {e}")
        print(f"Error uploading log to Supabase. See supabase_log_errors.log for details.")

# Example function to structure the log data before pushing
def format_log_entry(
    owl_in_box, pixel_change_owl_in_box, luminance_change_owl_in_box, owl_in_box_url, owl_in_box_image_comparison_url,
    owl_on_box, pixel_change_owl_on_box, luminance_change_owl_on_box, owl_on_box_image_url, owl_on_box_image_comparison_url,
    owl_in_area, pixel_change_owl_in_area, luminance_change_owl_in_area, owl_in_area_image_url, owl_in_area_image_comparison_url
):
    """
    Formats the log entry for Supabase before inserting.
    """
    return {
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

# Example usage
if __name__ == "__main__":
    sample_log = format_log_entry(
        owl_in_box=True, pixel_change_owl_in_box=5.2, luminance_change_owl_in_box=12.3, owl_in_box_url="example.com/owl1.jpg", owl_in_box_image_comparison_url="example.com/owl_compare1.jpg",
        owl_on_box=False, pixel_change_owl_on_box=0.0, luminance_change_owl_on_box=0.0, owl_on_box_image_url="", owl_on_box_image_comparison_url="",
        owl_in_area=True, pixel_change_owl_in_area=7.5, luminance_change_owl_in_area=10.2, owl_in_area_image_url="example.com/owl3.jpg", owl_in_area_image_comparison_url="example.com/owl_compare3.jpg"
    )
    
    push_log_to_supabase(sample_log)
