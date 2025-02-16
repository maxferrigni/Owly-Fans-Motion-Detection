# File: upload_images_to_supabase.py
# Purpose: Handle uploading motion detection images to Supabase Storage

import os
import datetime
import mimetypes
import supabase
from dotenv import load_dotenv

# Import utilities
from utilities.logging_utils import get_logger
from utilities.constants import SUPABASE_STORAGE

# Initialize logger
logger = get_logger()

# Load environment variables
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
    logger.info("Supabase storage client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {e}")
    raise

def upload_comparison_image(local_image_path, detection_type):
    """
    Upload a motion detection comparison image to Supabase Storage.
    
    Args:
        local_image_path (str): Path to the comparison image
        detection_type (str): Type of detection ("owl_in_box", "owl_on_box", "owl_in_area")
    
    Returns:
        str or None: Public URL of the uploaded image or None if failed
    """
    try:
        if not os.path.exists(local_image_path):
            logger.error(f"Comparison image not found: {local_image_path}")
            return None

        # Generate unique filename using timestamp
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        detection_type_clean = detection_type.lower().replace(" ", "_")
        filename = f"{detection_type_clean}_{timestamp}.jpg"
        
        # Create storage path with date-based structure
        current_date = datetime.datetime.utcnow()
        storage_path = f"{detection_type_clean}/{current_date.year}-{current_date.month:02d}/{current_date.day:02d}/{filename}"

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(local_image_path)
        if not mime_type:
            mime_type = "image/jpeg"
        
        logger.info(f"Uploading {detection_type} image: {filename}")
        logger.debug(f"Local path: {local_image_path}")
        logger.debug(f"Storage path: {storage_path}")

        # Upload image to Supabase Storage
        with open(local_image_path, "rb") as file:
            response = supabase_client.storage.from_(SUPABASE_STORAGE["owl_detections"]).upload(
                path=storage_path,
                file=file,
                file_options={"content-type": mime_type}
            )

        # Generate and return public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{storage_path}"
        logger.info(f"Image successfully uploaded: {public_url}")
        
        return public_url

    except Exception as e:
        logger.error(f"Error uploading image to Supabase: {e}")
        return None

def upload_base_image(local_image_path, camera_name, lighting_condition):
    """
    Upload a base image to Supabase Storage.
    
    Args:
        local_image_path (str): Path to the base image
        camera_name (str): Name of the camera
        lighting_condition (str): Current lighting condition
    
    Returns:
        str or None: Public URL of the uploaded image or None if failed
    """
    try:
        if not os.path.exists(local_image_path):
            logger.error(f"Base image not found: {local_image_path}")
            return None

        # Generate filename with timestamp
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"{camera_name.lower().replace(' ', '_')}_{lighting_condition}_base_{timestamp}.jpg"

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(local_image_path)
        if not mime_type:
            mime_type = "image/jpeg"
        
        logger.info(f"Uploading base image: {filename}")
        
        # Upload image to Supabase Storage
        with open(local_image_path, "rb") as file:
            response = supabase_client.storage.from_(SUPABASE_STORAGE["base_images"]).upload(
                path=filename,
                file=file,
                file_options={"content-type": mime_type}
            )

        # Generate and return public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{filename}"
        logger.info(f"Base image successfully uploaded: {public_url}")
        
        return public_url

    except Exception as e:
        logger.error(f"Error uploading base image to Supabase: {e}")
        return None

# Example usage and testing
if __name__ == "__main__":
    try:
        logger.info("Testing image upload functionality...")
        
        # Test comparison image upload
        test_comparison_path = "/path/to/test/comparison.jpg"
        if os.path.exists(test_comparison_path):
            url = upload_comparison_image(test_comparison_path, "owl_in_box")
            if url:
                logger.info("Comparison image upload test successful")
            else:
                logger.error("Comparison image upload test failed")
                
        # Test base image upload
        test_base_path = "/path/to/test/base.jpg"
        if os.path.exists(test_base_path):
            url = upload_base_image(test_base_path, "Upper Patio Camera", "day")
            if url:
                logger.info("Base image upload test successful")
            else:
                logger.error("Base image upload test failed")
                
    except Exception as e:
        logger.error(f"Upload tests failed: {e}")
        raise