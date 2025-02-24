# File: upload_images_to_supabase.py
# Purpose: Handle uploading motion detection images to Supabase Storage

import os
import datetime
import mimetypes
import supabase
import pytz
from PIL import Image
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

def get_average_luminance(image_path):
    """
    Calculate average luminance of an image.
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        float: Average luminance value
    """
    try:
        with Image.open(image_path) as img:
            # Convert to grayscale and calculate average
            gray_img = img.convert('L')
            return sum(gray_img.getdata()) / (gray_img.width * gray_img.height)
    except Exception as e:
        logger.error(f"Error calculating luminance: {e}")
        return 0.0

def log_base_image_to_supabase(local_path, camera_name, lighting_condition, supabase_url):
    """
    Log base image metadata to Supabase base_images_log table.
    
    Args:
        local_path (str): Local path to the base image
        camera_name (str): Name of the camera
        lighting_condition (str): Current lighting condition
        supabase_url (str): URL of the uploaded base image
    """
    try:
        # Get current time in Pacific timezone
        pacific = pytz.timezone('America/Los_Angeles')
        current_time = datetime.datetime.now(pacific)
        
        # Calculate average luminance
        light_level = get_average_luminance(local_path)
        
        # Prepare log entry
        log_entry = {
            "created_at": current_time.isoformat(),
            "camera_name": camera_name,
            "lighting_condition": lighting_condition,
            "base_image_url": supabase_url,
            "light_level": light_level,
            "capture_time": current_time.strftime('%H:%M:%S'),
            "capture_date": current_time.strftime('%Y-%m-%d'),
            "notes": f"Base image captured during {lighting_condition} conditions"
        }
        
        # Insert into Supabase
        response = supabase_client.table("base_images_log").insert(log_entry).execute()
        
        if hasattr(response, 'data') and response.data and len(response.data) > 0:
            logger.info(f"Base image logged successfully for {camera_name}")
        else:
            logger.error("Failed to log base image to Supabase")
            
    except Exception as e:
        logger.error(f"Error logging base image: {e}")

def upload_comparison_image(local_image_path, camera_name, detection_type):
    """
    Upload a motion detection comparison image to Supabase Storage.
    
    Args:
        local_image_path (str): Path to the comparison image
        camera_name (str): Name of the camera
        detection_type (str): Type of detection ("Owl In Box", "Owl On Box", "Owl In Area")
    
    Returns:
        str or None: Public URL of the uploaded image or None if failed
    """
    try:
        if not os.path.exists(local_image_path):
            logger.error(f"Comparison image not found: {local_image_path}")
            return None

        # Format detection type for storage folder path
        detection_type_clean = detection_type.lower().replace(" ", "_")
        
        # Generate unique filename using timestamp
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        camera_name_clean = camera_name.lower().replace(" ", "_")
        filename = f"{camera_name_clean}_{timestamp}.jpg"
        
        # Storage path: organized by detection type folder
        storage_path = f"{detection_type_clean}/{filename}"

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

def upload_base_image(local_image_path, supabase_filename, camera_name, lighting_condition):
    """
    Upload a base image to Supabase Storage and log its metadata.
    
    Args:
        local_image_path (str): Path to the base image
        supabase_filename (str): Filename to use in Supabase
        camera_name (str): Name of the camera
        lighting_condition (str): Current lighting condition
    
    Returns:
        str or None: Public URL of the uploaded image or None if failed
    """
    try:
        if not os.path.exists(local_image_path):
            logger.error(f"Base image not found: {local_image_path}")
            return None

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(local_image_path)
        if not mime_type:
            mime_type = "image/jpeg"
        
        logger.info(f"Uploading base image: {supabase_filename}")
        
        # Upload image to Supabase Storage - no subfolder structure
        with open(local_image_path, "rb") as file:
            response = supabase_client.storage.from_(SUPABASE_STORAGE["base_images"]).upload(
                path=supabase_filename,
                file=file,
                file_options={"content-type": mime_type}
            )

        # Generate public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{supabase_filename}"
        
        # Log base image metadata to Supabase
        log_base_image_to_supabase(local_image_path, camera_name, lighting_condition, public_url)
        
        logger.info(f"Base image successfully uploaded and logged: {public_url}")
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
            url = upload_comparison_image(test_comparison_path, "Test Camera", "Owl In Box")
            if url:
                logger.info("Comparison image upload test successful")
            else:
                logger.error("Comparison image upload test failed")
                
        # Test base image upload
        test_base_path = "/path/to/test/base.jpg"
        if os.path.exists(test_base_path):
            # Use standardized naming format
            camera_name = "test_camera"
            lighting_condition = "day"
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
            test_filename = f"{camera_name}_{lighting_condition}_base_{timestamp}.jpg"
            
            url = upload_base_image(test_base_path, test_filename, "Test Camera", "day")
            if url:
                logger.info("Base image upload test successful")
            else:
                logger.error("Base image upload test failed")
                
    except Exception as e:
        logger.error(f"Upload tests failed: {e}")
        raise