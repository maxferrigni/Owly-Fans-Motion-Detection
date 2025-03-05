# File: upload_images_to_supabase.py
# Purpose: Handle uploading motion detection images to Supabase Storage
#
# March 4, 2025 Update - Version 1.1.0
# - Updated to use separate buckets for detections and base images
# - Added proper folder structure for owl_detections bucket
# - Enhanced metadata logging for images
# - Added support for all detection types including multiple owls

import os
import datetime
import mimetypes
import supabase
import pytz
from PIL import Image
from dotenv import load_dotenv

# Import utilities
from utilities.logging_utils import get_logger
from utilities.constants import (
    SUPABASE_STORAGE, 
    get_detection_folder, 
    ALERT_PRIORITIES
)

# Initialize logger
logger = get_logger()

# Load environment variables
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
        detection_type (str): Type of detection ("Owl In Box", "Owl On Box", "Owl In Area", etc.)
    
    Returns:
        str or None: Public URL of the uploaded image or None if failed
    """
    try:
        if not os.path.exists(local_image_path):
            logger.error(f"Comparison image not found: {local_image_path}")
            return None

        # Get the correct folder for this detection type
        detection_folder = get_detection_folder(detection_type)
        
        # Generate unique filename using timestamp
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        camera_name_clean = camera_name.lower().replace(" ", "_")
        filename = f"{camera_name_clean}_{timestamp}.jpg"
        
        # Storage path: organized by detection type folder
        storage_path = f"{detection_folder}/{filename}"

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(local_image_path)
        if not mime_type:
            mime_type = "image/jpeg"
        
        logger.info(f"Uploading {detection_type} image: {filename}")
        logger.debug(f"Local path: {local_image_path}")
        logger.debug(f"Storage path: {storage_path}")
        logger.debug(f"Using bucket: {SUPABASE_BUCKET_DETECTIONS}")

        # Upload image to Supabase Storage using the correct bucket
        with open(local_image_path, "rb") as file:
            response = supabase_client.storage.from_(SUPABASE_BUCKET_DETECTIONS).upload(
                path=storage_path,
                file=file,
                file_options={"content-type": mime_type}
            )

        # Generate and return public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET_DETECTIONS}/{storage_path}"
        logger.info(f"Image successfully uploaded to {detection_folder}: {public_url}")
        
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
        logger.debug(f"Using bucket: {SUPABASE_BUCKET_IMAGES}")
        
        # Upload image to Supabase Storage in the base_images bucket
        with open(local_image_path, "rb") as file:
            response = supabase_client.storage.from_(SUPABASE_BUCKET_IMAGES).upload(
                path=supabase_filename,
                file=file,
                file_options={"content-type": mime_type}
            )

        # Generate public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET_IMAGES}/{supabase_filename}"
        
        # Log base image metadata to Supabase
        log_base_image_to_supabase(local_image_path, camera_name, lighting_condition, public_url)
        
        logger.info(f"Base image successfully uploaded and logged: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"Error uploading base image to Supabase: {e}")
        return None

def ensure_storage_folders_exist():
    """
    Ensure all required folders exist in the Supabase storage buckets.
    Added in v1.1.0 to create the proper folder structure.
    
    Returns:
        bool: True if successful, False if any errors occurred
    """
    try:
        # Get all required folders from detection types
        required_folders = list(set([
            get_detection_folder(alert_type) 
            for alert_type in ALERT_PRIORITIES.keys()
        ]))
        
        success = True
        
        # Check each folder and create if it doesn't exist
        for folder in required_folders:
            try:
                # Try to list the folder to see if it exists
                response = supabase_client.storage.from_(SUPABASE_BUCKET_DETECTIONS).list(folder)
                logger.debug(f"Folder {folder} already exists in {SUPABASE_BUCKET_DETECTIONS}")
            except Exception:
                # If error, the folder likely doesn't exist, so create it
                try:
                    # Create an empty file to establish the folder
                    dummy_file = f"{folder}/.folder"
                    supabase_client.storage.from_(SUPABASE_BUCKET_DETECTIONS).upload(
                        path=dummy_file,
                        file=b"",  # Empty content
                        file_options={"content-type": "application/octet-stream"}
                    )
                    logger.info(f"Created folder {folder} in {SUPABASE_BUCKET_DETECTIONS}")
                except Exception as folder_err:
                    logger.error(f"Failed to create folder {folder}: {folder_err}")
                    success = False
                    
        return success
        
    except Exception as e:
        logger.error(f"Error ensuring storage folders: {e}")
        return False

def initialize_supabase_storage():
    """
    Initialize Supabase storage with required buckets and folders.
    Added in v1.1.0 to ensure proper bucket and folder structure.
    
    Returns:
        bool: True if successful, False if any errors occurred
    """
    try:
        # Check if buckets exist
        buckets_exist = True
        
        # Try to access each bucket
        try:
            supabase_client.storage.get_bucket(SUPABASE_BUCKET_DETECTIONS)
            logger.info(f"Bucket {SUPABASE_BUCKET_DETECTIONS} exists")
        except Exception:
            logger.error(f"Bucket {SUPABASE_BUCKET_DETECTIONS} does not exist")
            buckets_exist = False
            
        try:
            supabase_client.storage.get_bucket(SUPABASE_BUCKET_IMAGES)
            logger.info(f"Bucket {SUPABASE_BUCKET_IMAGES} exists")
        except Exception:
            logger.error(f"Bucket {SUPABASE_BUCKET_IMAGES} does not exist")
            buckets_exist = False
            
        # If buckets exist, ensure folders exist
        if buckets_exist:
            return ensure_storage_folders_exist()
        else:
            logger.error("Required buckets do not exist. Please create them in the Supabase dashboard.")
            return False
        
    except Exception as e:
        logger.error(f"Error initializing Supabase storage: {e}")
        return False

# Example usage and testing
if __name__ == "__main__":
    try:
        logger.info("Testing image upload functionality...")
        
        # Initialize storage structure
        initialize_supabase_storage()
        
        # Test comparison image upload for standard detection
        test_comparison_path = "/path/to/test/comparison.jpg"
        if os.path.exists(test_comparison_path):
            url = upload_comparison_image(test_comparison_path, "Test Camera", "Owl In Box")
            if url:
                logger.info("Comparison image upload test successful")
            else:
                logger.error("Comparison image upload test failed")
        
        # Test comparison image upload for multiple owls
        if os.path.exists(test_comparison_path):
            url = upload_comparison_image(test_comparison_path, "Test Camera", "Two Owls In Box")
            if url:
                logger.info("Multiple owl comparison image upload test successful")
            else:
                logger.error("Multiple owl comparison image upload test failed")
                
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